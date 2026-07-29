"""The secrets vault.

Encryption is the easy part. The hard part is that a secret leaks through
everything *except* the store: a log line, an event payload, an audit entry, a
run step, an HTTP tool echoing the request it just made, an error message
quoting the header it failed to send. A vault that encrypts at rest and then
hands the plaintext to a model, which puts it in an answer that gets written to
memory, has protected nothing.

So this module is two things:

**A store.** AES-256-GCM, one key, authenticated so a tampered ciphertext fails
loudly instead of decrypting to garbage. Each secret gets a fresh nonce; the
name is authenticated as associated data, so a ciphertext cannot be moved from
one name to another.

**A redactor.** Every known secret value is scrubbed from any string on its way
to a log, an event, or the audit log. This is the part that actually keeps
secrets out of the record, and it is deliberately dumb: substring replacement
over the live secret set, applied at the boundary rather than trusted to every
call site.

The model never sees a secret. It names one — `${vault:stripe_key}` — and the
tool registry resolves the reference at call time, *after* the audit log has
recorded the unresolved form. That is what makes the audit log safe to keep and
still worth reading.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = structlog.get_logger(__name__)

NONCE_BYTES = 12
KEY_BYTES = 32
MIN_REDACTABLE = 6

# `${vault:name}` — deliberately unlike anything a model writes by accident,
# and easy to spot in an audit log.
REFERENCE = re.compile(r"\$\{vault:([A-Za-z0-9_.-]{1,64})\}")

REDACTED = "«redacted»"


class SecretNotFoundError(KeyError):
    """A reference named a secret that is not in the vault."""


class VaultLockedError(RuntimeError):
    """No key is configured, so nothing can be read or written."""


def derive_key(material: str) -> bytes:
    """Turn configuration into a key.

    A base64 32-byte key is used directly. Anything else is treated as a
    passphrase and stretched with scrypt — weakly salted by necessity, since
    there is nowhere to keep a salt that the key itself does not already
    protect. A real deployment sets a proper key; a passphrase is a convenience
    that says so in the log.
    """
    try:
        raw = base64.urlsafe_b64decode(material + "=" * (-len(material) % 4))
        if len(raw) == KEY_BYTES:
            return raw
    except Exception:
        pass

    log.warning("vault_key_derived_from_passphrase", advice="set a base64 32-byte key")
    return hashlib.scrypt(
        material.encode(), salt=b"jarvis.vault.v1", n=2**14, r=8, p=1, dklen=KEY_BYTES
    )


def new_key() -> str:
    """A fresh key, in the form the configuration expects."""
    return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode().rstrip("=")


@dataclass(slots=True, frozen=True)
class SecretInfo:
    """Everything about a secret except the secret.

    Returned by every listing path, so there is no shape of the API that hands
    a plaintext back by accident.
    """

    name: str
    hint: str
    length: int
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hint": self.hint,
            "length": self.length,
            "created_at": self.created_at,
        }


def hint_for(value: str) -> str:
    """A few characters, enough to tell two keys apart and not enough to use."""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:3]}…{value[-2:]}"


class SecretStore(Protocol):
    """Where ciphertext lives. The vault owns the crypto; this owns the bytes."""

    async def put(self, name: str, blob: bytes) -> None: ...

    async def get(self, name: str) -> bytes | None: ...

    async def names(self) -> list[str]: ...

    async def delete(self, name: str) -> bool: ...


class InMemorySecretStore:
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def put(self, name: str, blob: bytes) -> None:
        self._blobs[name] = blob

    async def get(self, name: str) -> bytes | None:
        return self._blobs.get(name)

    async def names(self) -> list[str]:
        return sorted(self._blobs)

    async def delete(self, name: str) -> bool:
        return self._blobs.pop(name, None) is not None


@dataclass
class Vault:
    """Encrypted secrets, and the redactor that keeps them out of the record."""

    store: SecretStore = field(default_factory=InMemorySecretStore)
    key: bytes | None = None
    # Plaintexts held for redaction. This is the deliberate trade: to scrub a
    # secret from a log line we must be able to recognise it, which means
    # holding it in memory. The alternative — redacting nothing — leaks far
    # more, far more often.
    _live: dict[str, str] = field(default_factory=dict, repr=False)
    _meta: dict[str, SecretInfo] = field(default_factory=dict, repr=False)

    @property
    def locked(self) -> bool:
        return self.key is None

    def _cipher(self) -> AESGCM:
        if self.key is None:
            raise VaultLockedError("no vault key configured — set JARVIS_VAULT_KEY")
        return AESGCM(self.key)

    async def put(self, name: str, value: str, *, at: str = "") -> SecretInfo:
        if not name or REFERENCE.search(name):
            raise ValueError(f"invalid secret name: {name!r}")
        nonce = os.urandom(NONCE_BYTES)
        # The name is authenticated, not encrypted: a ciphertext moved to a
        # different name must fail to decrypt rather than silently work.
        sealed = self._cipher().encrypt(nonce, value.encode(), name.encode())
        await self.store.put(name, nonce + sealed)

        info = SecretInfo(name=name, hint=hint_for(value), length=len(value), created_at=at)
        self._live[name] = value
        self._meta[name] = info
        log.info("secret_stored", name=name, length=len(value))
        return info

    async def get(self, name: str) -> str:
        if name in self._live:
            return self._live[name]
        blob = await self.store.get(name)
        if blob is None:
            raise SecretNotFoundError(name)
        try:
            value = self._cipher().decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], name.encode())
        except InvalidTag as exc:
            # Either the key changed or the ciphertext was edited. Both are
            # worth failing loudly for; neither should return plausible bytes.
            raise VaultLockedError(f"secret {name!r} could not be decrypted") from exc
        plaintext = value.decode()
        self._live[name] = plaintext
        return plaintext

    async def load(self) -> int:
        """Decrypt everything into memory, so redaction can see it.

        Called at boot. A secret nobody has read yet cannot be redacted, which
        is exactly the case where it is most likely to appear in a log.
        """
        if self.locked:
            return 0
        loaded = 0
        for name in await self.store.names():
            try:
                value = await self.get(name)
            except VaultLockedError as exc:
                log.warning("secret_unreadable", name=name, error=str(exc))
                continue
            self._meta.setdefault(name, SecretInfo(name, hint_for(value), len(value)))
            loaded += 1
        return loaded

    async def names(self) -> list[SecretInfo]:
        names = await self.store.names()
        return [self._meta.get(n, SecretInfo(n, "•••", 0)) for n in names]

    async def delete(self, name: str) -> bool:
        self._live.pop(name, None)
        self._meta.pop(name, None)
        return await self.store.delete(name)

    # ── Resolution ────────────────────────────────────────────────────────────

    def has_reference(self, value: Any) -> bool:
        return isinstance(value, str) and bool(REFERENCE.search(value))

    async def resolve(self, value: Any) -> Any:
        """Replace `${vault:name}` references with their values.

        Applied to tool arguments at call time, after the audit log has already
        recorded the unresolved form. An unknown name raises rather than
        substituting empty string — a request that silently loses its
        credential fails in a much more confusing place.
        """
        if isinstance(value, str):
            names = REFERENCE.findall(value)
            if not names:
                return value
            resolved = value
            for name in names:
                resolved = resolved.replace(f"${{vault:{name}}}", await self.get(name))
            return resolved
        if isinstance(value, dict):
            return {k: await self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [await self.resolve(v) for v in value]
        return value

    # ── Redaction ─────────────────────────────────────────────────────────────

    def redact(self, value: Any) -> Any:
        """Scrub every known secret from anything on its way out.

        Deliberately dumb — substring replacement over the live secret set,
        applied at the boundary. Trusting each call site to remember is how
        secrets end up in logs.
        """
        secrets = [s for s in self._live.values() if len(s) >= MIN_REDACTABLE]
        if not secrets:
            return value
        return _scrub(value, secrets)


def _scrub(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, str):
        for secret in secrets:
            if secret in value:
                value = value.replace(secret, REDACTED)
        return value
    if isinstance(value, dict):
        return {k: _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, secrets) for v in value]
    if isinstance(value, tuple):
        return tuple(_scrub(v, secrets) for v in value)
    return value
