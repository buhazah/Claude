"""Voice session state.

Voice is not a pipeline with a microphone at one end and a speaker at the
other. It is a **state machine with one hard rule**: the user may interrupt at
any moment, and interrupting must stop everything downstream — the speech, and
the generation producing it.

The subtle part is what the conversation remembers afterwards. If Jarvis is cut
off mid-sentence, the history must record *what the user actually heard*, not
what the model happened to generate. Otherwise the next turn is reasoning about
a conversation that did not occur, and the user is told "as I said" about
something they never heard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from jarvis.kernel.ids import new_id


class VoiceState(StrEnum):
    IDLE = "idle"  # not listening
    WAITING_FOR_WAKE = "waiting_for_wake"  # listening only for the wake word
    LISTENING = "listening"  # capturing the user's speech
    THINKING = "thinking"  # generating a reply
    SPEAKING = "speaking"  # playing the reply
    ENDED = "ended"


@dataclass(slots=True)
class TranscriptSegment:
    """A piece of recognised speech.

    ``final`` distinguishes a stable transcript from a live guess. Acting on a
    partial is what makes a voice assistant answer the wrong question.
    """

    text: str
    final: bool = False
    confidence: float = 1.0
    at: str = ""


@dataclass(slots=True)
class SpeechChunk:
    """One piece of synthesised audio, plus the text it renders."""

    audio: bytes = b""
    text: str = ""
    index: int = 0
    done: bool = False


@dataclass(slots=True)
class VoiceEvent:
    """What the client is told. Mirrors the bus, but scoped to one session."""

    type: str  # state | partial | transcript | token | speech | interrupted | error
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text, **self.data}


@dataclass(slots=True)
class Turn:
    """One exchange, recording what was *heard* rather than what was produced."""

    id: str = field(default_factory=lambda: new_id("vtn"))
    user: str = ""
    spoken: str = ""  # what was actually played before any interruption
    generated: str = ""  # everything the model produced
    interrupted: bool = False

    @property
    def truncated(self) -> bool:
        """True when the user heard less than the model said."""
        return self.interrupted and len(self.spoken) < len(self.generated)
