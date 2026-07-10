"""Generic OAuth 2.0 (authorization-code) support for account integrations.

Providers are declared once in PROVIDERS. The flow:
  1. authorize_url()  -> user consents at the provider
  2. exchange_code()  -> we get access + refresh tokens, store them encrypted
  3. get_access_token() -> connected tools call this; auto-refreshes when expired

`state` is an HMAC-signed token binding the flow to a user, so the callback
(which carries no auth header) can be trusted.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import Connection, SessionLocal, utcnow
from .crypto import decrypt, encrypt


@dataclass
class Provider:
    key: str
    name: str
    authorize_url: str
    token_url: str
    scopes: list[str]
    client_id: str
    client_secret: str
    extra_authorize: dict = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def _providers() -> dict[str, Provider]:
    google_scopes_cal = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ]
    gmail_scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ]
    return {
        "google": Provider(
            "google", "Google Calendar",
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            google_scopes_cal, settings.google_client_id, settings.google_client_secret,
            {"access_type": "offline", "prompt": "consent"},
        ),
        "gmail": Provider(
            "gmail", "Gmail",
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            gmail_scopes, settings.google_client_id, settings.google_client_secret,
            {"access_type": "offline", "prompt": "consent"},
        ),
        "spotify": Provider(
            "spotify", "Spotify",
            "https://accounts.spotify.com/authorize",
            "https://accounts.spotify.com/api/token",
            ["user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing"],
            settings.spotify_client_id, settings.spotify_client_secret,
        ),
    }


PROVIDERS = _providers()


class OAuthError(RuntimeError):
    pass


# ------------------------------------------------------------- state signing

def sign_state(user_id: str, provider: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"u": user_id, "p": provider, "t": int(time.time())}).encode()
    ).rstrip(b"=").decode()
    sig = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def verify_state(state: str) -> tuple[str, str]:
    try:
        payload, sig = state.split(".")
        expected = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            raise OAuthError("bad state signature")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(time.time()) - data["t"] > 900:
            raise OAuthError("state expired")
        return data["u"], data["p"]
    except OAuthError:
        raise
    except Exception as exc:
        raise OAuthError(f"invalid state: {exc}")


# ------------------------------------------------------------- flow helpers

def authorize_url(provider_key: str, redirect_uri: str, state: str) -> str:
    p = PROVIDERS[provider_key]
    params = {
        "client_id": p.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(p.scopes),
        "state": state,
        **p.extra_authorize,
    }
    return f"{p.authorize_url}?{urlencode(params)}"


async def exchange_code(provider_key: str, code: str, redirect_uri: str) -> dict:
    p = PROVIDERS[provider_key]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": p.client_id,
        "client_secret": p.client_secret,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(p.token_url, data=data, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise OAuthError(f"token exchange failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


async def _refresh(p: Provider, refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            p.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": p.client_id,
                "client_secret": p.client_secret,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise OAuthError(f"token refresh failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()


async def store_tokens(
    session: AsyncSession, user_id: str, provider_key: str, tokens: dict, account_label: str = ""
) -> Connection:
    existing = (
        await session.execute(
            select(Connection).where(
                Connection.user_id == user_id, Connection.provider == provider_key
            )
        )
    ).scalar_one_or_none()
    expires_at = None
    if tokens.get("expires_in"):
        expires_at = utcnow() + timedelta(seconds=int(tokens["expires_in"]) - 60)
    conn = existing or Connection(user_id=user_id, provider=provider_key)
    conn.access_token = encrypt(tokens.get("access_token", ""))
    if tokens.get("refresh_token"):
        conn.refresh_token = encrypt(tokens["refresh_token"])
    conn.expires_at = expires_at
    conn.scopes = tokens.get("scope", " ".join(PROVIDERS[provider_key].scopes))
    if account_label:
        conn.account_label = account_label
    if existing is None:
        session.add(conn)
    await session.commit()
    return conn


async def get_access_token(user_id: str, provider_key: str) -> str:
    """Return a valid access token for the user, refreshing if needed."""
    p = PROVIDERS.get(provider_key)
    if p is None:
        raise OAuthError(f"unknown provider {provider_key}")
    async with SessionLocal() as session:
        conn = (
            await session.execute(
                select(Connection).where(
                    Connection.user_id == user_id, Connection.provider == provider_key
                )
            )
        ).scalar_one_or_none()
        if conn is None:
            raise OAuthError(f"{p.name} is not connected")
        if conn.expires_at and conn.expires_at <= utcnow():
            refresh = decrypt(conn.refresh_token)
            if not refresh:
                raise OAuthError(f"{p.name} session expired — please reconnect")
            tokens = await _refresh(p, refresh)
            conn = await store_tokens(session, user_id, provider_key, tokens)
        return decrypt(conn.access_token)
