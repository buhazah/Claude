"""Authentication, authorization, rate limiting, and audit logging.

Tokens are HMAC-signed JWTs implemented with the standard library so the
security-critical path has zero third-party dependencies. Passwords use
PBKDF2-HMAC-SHA256 with per-user salts and constant-time comparison.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import AuditLog, RefreshToken, SessionLocal, User, get_session, utcnow

PBKDF2_ITERATIONS = 390_000

# Role hierarchy: any role listed later includes the permissions of earlier ones.
ROLE_LEVELS = {"viewer": 0, "member": 1, "owner": 2}


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------- tokens

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_access_token(user_id: str, role: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(
        json.dumps(
            {
                "sub": user_id,
                "role": role,
                "iat": int(time.time()),
                "exp": int(time.time()) + settings.access_token_minutes * 60,
            }
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = _b64(hmac.new(settings.secret_key.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = _b64(
            hmac.new(settings.secret_key.encode(), signing_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(payload))
        if claims.get("exp", 0) < time.time():
            raise ValueError("expired")
        return claims
    except ValueError:
        raise
    except Exception as exc:  # malformed structure
        raise ValueError("malformed token") from exc


def new_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is persisted."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


async def store_refresh_token(session: AsyncSession, user_id: str, token_hash: str) -> None:
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    await session.commit()


async def redeem_refresh_token(session: AsyncSession, raw: str) -> User | None:
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    row = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None or row.expires_at < utcnow():
        return None
    # Rotate: a refresh token is single-use.
    row.revoked = True
    user = await session.get(User, row.user_id)
    await session.commit()
    if user is None or not user.is_active:
        return None
    return user


# ------------------------------------------------------------- rate limiting

class RateLimiter:
    """Sliding-window in-memory limiter keyed by client identity."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            return False
        window.append(now)
        return True


rate_limiter = RateLimiter(settings.rate_limit_per_minute)


async def enforce_rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    if not rate_limiter.check(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again shortly.",
        )


# --------------------------------------------------------------- audit trail

async def audit(action: str, user_id: str | None = None, ip: str = "", **detail) -> None:
    async with SessionLocal() as session:
        session.add(AuditLog(user_id=user_id, action=action, detail=detail, ip=ip))
        await session.commit()


# ------------------------------------------------------------- dependencies

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    await enforce_rate_limit(request)
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    user = await session.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    return user


def require_role(minimum: str):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVELS.get(user.role, -1) < ROLE_LEVELS[minimum]:
            raise HTTPException(status_code=403, detail=f"Requires {minimum} role")
        return user

    return _dep
