"""Splitting a token stream into speakable units.

The single biggest lever on perceived voice latency: do not wait for the model
to finish. Speak the first sentence while the rest is still generating, and the
reply starts in a few hundred milliseconds instead of several seconds.

That requires deciding, from a partial stream, when enough has arrived to be
worth speaking. The rules:

* **A sentence boundary is a unit**, but not every full stop is one — "Dr.",
  "e.g." and "3.5" must not split, because a fragment spoken alone sounds wrong
  and cannot be un-said.
* **A long clause is a unit too.** Waiting for a full stop that never comes
  produces a long silence, so a comma or a clause break past a threshold flushes.
* **Never emit a unit so short it sounds clipped.** Below a floor, wait.
"""

from __future__ import annotations

import re

# Past this many characters without a sentence end, flush on the next clause
# break rather than letting the user sit in silence.
CLAUSE_FLUSH_AFTER = 140
MIN_UNIT_CHARS = 12

_SENTENCE_END = re.compile(r"[.!?]['\")\]]?\s")
_CLAUSE_BREAK = re.compile(r"[,;:]\s")

# Trailing dots that are not sentence ends.
_ABBREVIATIONS = frozenset(
    {
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "prof.",
        "sr.",
        "jr.",
        "st.",
        "e.g.",
        "i.e.",
        "etc.",
        "vs.",
        "approx.",
        "no.",
        "fig.",
    }
)


def _ends_mid_thought(text: str) -> bool:
    """True when a trailing '.' belongs to an abbreviation or a number."""
    stripped = text.rstrip()
    if not stripped.endswith("."):
        return False
    tail = stripped.split()[-1].lower() if stripped.split() else ""
    if tail in _ABBREVIATIONS:
        return True
    # "3." or "3.5" — a decimal, not a sentence.
    return bool(re.search(r"\d\.$", stripped))


class SpeechSegmenter:
    """Accumulates tokens and yields text worth speaking."""

    def __init__(
        self,
        *,
        clause_flush_after: int = CLAUSE_FLUSH_AFTER,
        min_chars: int = MIN_UNIT_CHARS,
    ) -> None:
        self._buffer = ""
        self._clause_flush_after = clause_flush_after
        self._min_chars = min_chars

    @property
    def pending(self) -> str:
        return self._buffer

    def push(self, token: str) -> list[str]:
        """Add a token; return any units that are now ready to speak."""
        self._buffer += token
        ready: list[str] = []

        while True:
            unit = self._take()
            if unit is None:
                break
            ready.append(unit)
        return ready

    def _take(self) -> str | None:
        if len(self._buffer) < self._min_chars:
            return None

        for match in _SENTENCE_END.finditer(self._buffer):
            end = match.end()
            candidate = self._buffer[:end]
            if _ends_mid_thought(candidate):
                continue  # "Dr. " is not the end of anything
            if len(candidate.strip()) < self._min_chars:
                continue
            self._buffer = self._buffer[end:]
            return candidate.strip()

        if len(self._buffer) >= self._clause_flush_after:
            # No sentence end in sight; break at the last clause boundary so
            # the pause lands somewhere a listener expects one.
            breaks = list(_CLAUSE_BREAK.finditer(self._buffer))
            if breaks:
                end = breaks[-1].end()
                unit = self._buffer[:end].strip()
                self._buffer = self._buffer[end:]
                return unit
        return None

    def flush(self) -> str | None:
        """Emit whatever is left, at the end of a reply."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining or None
