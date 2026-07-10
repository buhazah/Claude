"""Symmetric encryption for stored OAuth tokens.

The Fernet key is derived from JARVIS_SECRET_KEY, so tokens at rest in the
database are unreadable without it. Set a stable JARVIS_SECRET_KEY in
production or stored tokens become undecryptable after a key rotation
(users simply reconnect if that happens).
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings

_key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
_fernet = Fernet(_key)


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""
