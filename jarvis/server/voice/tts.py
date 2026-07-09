"""Voice: ElevenLabs text-to-speech with streaming, plus a pluggable STT
interface (OpenAI Whisper when configured).

TTS returns MP3 bytes; the API layer streams them to the browser. If no
ElevenLabs key is configured, synthesize() raises a clear error the API
turns into a 503 so the UI can fall back to browser SpeechSynthesis.
"""
from __future__ import annotations

import httpx

from ..config import settings


class VoiceNotConfigured(RuntimeError):
    pass


async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """Return MP3 audio bytes for `text` using ElevenLabs."""
    if not settings.elevenlabs_api_key:
        raise VoiceNotConfigured("ELEVENLABS_API_KEY is not set")
    voice = voice_id or settings.elevenlabs_voice_id
    if not voice:
        raise VoiceNotConfigured("No ElevenLabs voice ID configured")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "content-type": "application/json",
                "accept": "audio/mpeg",
            },
            json={
                "text": text[:5000],
                "model_id": settings.elevenlabs_model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.2},
            },
        )
        resp.raise_for_status()
        return resp.content


async def stream_synthesize(text: str, voice_id: str | None = None):
    """Yield MP3 chunks as they arrive from ElevenLabs streaming endpoint."""
    if not settings.elevenlabs_api_key:
        raise VoiceNotConfigured("ELEVENLABS_API_KEY is not set")
    voice = voice_id or settings.elevenlabs_voice_id
    if not voice:
        raise VoiceNotConfigured("No ElevenLabs voice ID configured")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "content-type": "application/json",
                "accept": "audio/mpeg",
            },
            json={
                "text": text[:5000],
                "model_id": settings.elevenlabs_model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
            },
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk


async def transcribe(audio: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio to text via OpenAI Whisper when configured.

    The browser's built-in Web Speech API handles STT client-side in the
    default deployment; this server path is for when a key is present.
    """
    if not settings.openai_api_key:
        raise VoiceNotConfigured(
            "Server-side transcription needs OPENAI_API_KEY; "
            "the UI uses the browser Web Speech API otherwise."
        )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"authorization": f"Bearer {settings.openai_api_key}"},
            files={"file": (filename, audio, "application/octet-stream")},
            data={"model": "whisper-1"},
        )
        resp.raise_for_status()
        return resp.json().get("text", "")
