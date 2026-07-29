"""Wake-word detection over a transcript stream.

Detection runs on *text*, not audio. A dedicated acoustic wake model is lower
power and works before recognition starts, and belongs on the device — but the
matching rules are the same either way, and putting them here means they can be
tested exactly rather than approximated.

Two mistakes this exists to avoid:

* **Triggering on a mention.** "I was telling Jarvis about it" is not a summons.
  The wake word must lead the utterance.
* **Missing a near-miss.** Recognisers routinely return "Jervis", "Harvis" or
  "Arvis"; rejecting those makes the assistant feel broken, so variants within
  one edit are accepted.

The threshold is deliberately tight. Edit distance over spelling is a crude
proxy for phonetic similarity — it accepts "Jervis" but not "Travis", which is
phonetically closer than its spelling suggests. Widening it to catch those would
also accept genuinely different words, and a false wake (Jarvis interrupting a
conversation it was not part of) is worse than a missed one the user can repeat.
Proper phonetic matching belongs in a device-side acoustic model, which is where
wake detection ultimately runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_WAKE_WORDS = ("jarvis", "hey jarvis")
# One substitution in a short word is a recogniser slip; two is a different word.
MAX_EDITS = 1
_WORD_RE = re.compile(r"[a-z']+")


def _edit_distance(a: str, b: str, *, limit: int) -> int:
    """Levenshtein distance, abandoned once it exceeds ``limit``."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


@dataclass(slots=True)
class WakeResult:
    detected: bool
    matched: str = ""
    # What followed the wake word — usually the actual request, so a user can
    # say "Jarvis, what's on today" in one breath.
    remainder: str = ""


class WakeWordDetector:
    def __init__(
        self, words: tuple[str, ...] = DEFAULT_WAKE_WORDS, *, max_edits: int = MAX_EDITS
    ) -> None:
        # Longest first, so "hey jarvis" wins over "jarvis".
        self._words = tuple(sorted((w.lower() for w in words), key=len, reverse=True))
        self._max_edits = max_edits

    def detect(self, transcript: str) -> WakeResult:
        tokens = _WORD_RE.findall(transcript.lower())
        if not tokens:
            return WakeResult(False)

        for phrase in self._words:
            parts = phrase.split()
            if len(tokens) < len(parts):
                continue
            # Only the start of the utterance counts: a wake word in the middle
            # is someone talking *about* Jarvis, not to it.
            head = tokens[: len(parts)]
            if all(
                _edit_distance(spoken, expected, limit=self._max_edits) <= self._max_edits
                for spoken, expected in zip(head, parts, strict=True)
            ):
                remainder = " ".join(tokens[len(parts) :]).strip(" ,.")
                return WakeResult(True, matched=phrase, remainder=remainder)

        return WakeResult(False)
