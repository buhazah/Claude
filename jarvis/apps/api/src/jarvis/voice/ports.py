"""Speech ports, with deterministic offline implementations.

Same pattern as the LLM layer (ADR 0001): a narrow protocol, a real adapter,
and an offline one that makes the whole subsystem testable and demoable with no
API key and no microphone. The offline transcriber turns injected text into
partial-then-final segments exactly as a streaming recogniser would, which is
what lets the barge-in state machine be tested properly rather than mocked.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

import structlog

from jarvis.voice.models import SpeechChunk, TranscriptSegment

log = structlog.get_logger(__name__)


class Transcriber(Protocol):
    """Audio in, transcript segments out."""

    name: str

    def is_available(self) -> bool: ...

    def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]: ...


class Speaker(Protocol):
    """Text in, audio out. Streams, so playback can start on the first sentence."""

    name: str

    def is_available(self) -> bool: ...

    def synthesise(self, text: str) -> AsyncIterator[SpeechChunk]: ...


class ScriptedTranscriber:
    """A transcriber driven by injected text instead of a microphone.

    Not a mock: it is how the server-side session is exercised when speech
    recognition happens in the browser, which is the default configuration.
    Text arrives over the socket already recognised.
    """

    name = "scripted"

    def __init__(self, *, partial_delay: float = 0.0) -> None:
        self._queue: asyncio.Queue[TranscriptSegment | None] = asyncio.Queue()
        self._partial_delay = partial_delay

    def is_available(self) -> bool:
        return True

    async def say(self, text: str, *, final: bool = True) -> None:
        """Inject recognised speech, as a recogniser would emit it."""
        words = text.split()
        # Partials first, so anything downstream must cope with a transcript
        # that changes under it — which is the real behaviour.
        for size in range(1, len(words)):
            await self._queue.put(TranscriptSegment(" ".join(words[:size]), final=False))
            if self._partial_delay:
                await asyncio.sleep(self._partial_delay)
        await self._queue.put(TranscriptSegment(text, final=final))

    async def close(self) -> None:
        await self._queue.put(None)

    async def stream(
        self, audio: AsyncIterator[bytes] | None = None
    ) -> AsyncIterator[TranscriptSegment]:
        while True:
            segment = await self._queue.get()
            if segment is None:
                return
            yield segment


class SilentSpeaker:
    """Produces timed, silent audio frames.

    Deterministic and dependency-free, but *paced*: a chunk per unit of text at
    a plausible speaking rate. That matters, because barge-in is a race — an
    instantaneous speaker would make every interruption test pass trivially.
    """

    name = "silent"

    # Roughly conversational: ~14 characters per second of speech.
    CHARS_PER_SECOND = 14.0
    FRAME_CHARS = 40

    def __init__(self, *, realtime: bool = False) -> None:
        self.realtime = realtime

    def is_available(self) -> bool:
        return True

    async def synthesise(self, text: str) -> AsyncIterator[SpeechChunk]:
        for index in range(0, max(len(text), 1), self.FRAME_CHARS):
            piece = text[index : index + self.FRAME_CHARS]
            if self.realtime:
                await asyncio.sleep(len(piece) / self.CHARS_PER_SECOND)
            else:
                await asyncio.sleep(0)  # still yields, so a cancel can land
            yield SpeechChunk(
                audio=b"\x00" * len(piece) * 2, text=piece, index=index // self.FRAME_CHARS
            )
        yield SpeechChunk(done=True, text=text)
