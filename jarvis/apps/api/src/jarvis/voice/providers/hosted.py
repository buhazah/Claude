"""Hosted speech adapters (OpenAI-compatible).

The same wire format is spoken by OpenAI and several others, so one adapter
with a configurable base URL covers them. Both fall back rather than fail: a
speech provider outage should degrade voice to text, not break the session.

These are **not exercised against a live service in this repository's tests** —
there is no audio hardware or API key in CI. Their contract is pinned by the
protocol tests against a mock transport; the offline adapters are what the
session tests run on.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import structlog

from jarvis.voice.models import SpeechChunk, TranscriptSegment

log = structlog.get_logger(__name__)

CHUNK_BYTES = 8192


class HostedTranscriber:
    """Whisper-style transcription over HTTP."""

    name = "hosted-stt"

    def __init__(
        self,
        api_key: str | None,
        *,
        model: str = "whisper-1",
        base_url: str = "https://api.openai.com/v1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = client

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def transcribe(self, audio: bytes, *, mime: str = "audio/webm") -> TranscriptSegment:
        """Transcribe one utterance. Returns an empty segment on failure."""
        client = self._client or httpx.AsyncClient(timeout=60.0)
        owns = self._client is None
        try:
            response = await client.post(
                f"{self._base_url}/audio/transcriptions",
                headers={"authorization": f"Bearer {self._api_key}"},
                files={"file": ("speech.webm", audio, mime)},
                data={"model": self._model},
            )
            response.raise_for_status()
            return TranscriptSegment(response.json().get("text", "").strip(), final=True)
        except Exception as exc:
            log.warning("transcription_failed", error=str(exc))
            return TranscriptSegment("", final=True, confidence=0.0)
        finally:
            if owns:
                await client.aclose()

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]:
        """Buffer an utterance, then transcribe it.

        Chunk-level streaming needs a realtime socket API; this adapter is the
        simple path, and the session does not care which it is given.
        """
        buffer = bytearray()
        async for chunk in audio:
            buffer.extend(chunk)
        if buffer:
            yield await self.transcribe(bytes(buffer))


class HostedSpeaker:
    """Streaming text-to-speech over HTTP."""

    name = "hosted-tts"

    def __init__(
        self,
        api_key: str | None,
        *,
        model: str = "tts-1",
        voice: str = "alloy",
        base_url: str = "https://api.openai.com/v1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._base_url = base_url.rstrip("/")
        self._client = client

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def synthesise(self, text: str) -> AsyncIterator[SpeechChunk]:
        client = self._client or httpx.AsyncClient(timeout=60.0)
        owns = self._client is None
        index = 0
        try:
            async with client.stream(
                "POST",
                f"{self._base_url}/audio/speech",
                headers={"authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "voice": self._voice,
                    "input": text,
                    "response_format": "mp3",
                },
            ) as response:
                response.raise_for_status()
                async for audio in response.aiter_bytes(CHUNK_BYTES):
                    # The text rides with the first frame only: a byte range of
                    # mp3 does not correspond to a slice of the input string,
                    # and pretending otherwise would corrupt what a turn records
                    # as spoken.
                    yield SpeechChunk(audio=audio, text=text if index == 0 else "", index=index)
                    index += 1
        except Exception as exc:
            log.warning("synthesis_failed", error=str(exc))
        finally:
            if owns:
                await client.aclose()
        yield SpeechChunk(done=True, text=text)
