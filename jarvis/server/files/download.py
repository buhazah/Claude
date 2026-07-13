"""Signed, expiring download links so a plain browser <a> can fetch a
generated file without a bearer token."""
from __future__ import annotations

import hashlib
import hmac
import time

from ..config import settings


def sign(name: str, ttl: int = 86400) -> str:
    exp = int(time.time()) + ttl
    sig = hmac.new(settings.secret_key.encode(), f"{name}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}"


def verify(name: str, token: str) -> bool:
    try:
        exp, sig = token.split(".")
        if int(exp) < time.time():
            return False
        expected = hmac.new(settings.secret_key.encode(), f"{name}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False
