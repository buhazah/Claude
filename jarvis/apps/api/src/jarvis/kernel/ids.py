"""Sortable, prefixed identifiers.

Ids are lexicographically sortable by creation time, which means a plain
``ORDER BY id`` is a chronological ordering in any store we back onto.
"""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32, no i/l/o/u


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        out.append(_ALPHABET[rem])
    return "".join(reversed(out))


def new_id(prefix: str) -> str:
    """Return a new sortable id such as ``run_01j9x...``."""
    timestamp = _encode(int(time.time() * 1000), 10)
    randomness = _encode(int.from_bytes(os.urandom(10), "big"), 16)
    return f"{prefix}_{timestamp}{randomness}"
