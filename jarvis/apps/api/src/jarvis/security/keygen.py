"""Generate a vault key.

    python -m jarvis.security.keygen

Printed to stdout and nowhere else — not written to a file, not logged. Where
it goes next is a decision the operator should have to make deliberately.
"""

from __future__ import annotations

from jarvis.security.vault import new_key

if __name__ == "__main__":  # pragma: no cover - a one-line CLI
    print(new_key())
