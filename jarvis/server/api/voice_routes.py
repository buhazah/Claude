"""Voice routes: text-to-speech and server-side transcription."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from ..config import settings
from ..db import User
from ..schemas import VoiceIn
from ..security import get_current_user
from ..voice.tts import VoiceNotConfigured, synthesize, transcribe

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/config")
async def voice_config(_: User = Depends(get_current_user)):
    return {
        "tts_available": bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id),
        "stt_server_available": bool(settings.openai_api_key),
        "voice_id": settings.elevenlabs_voice_id,
    }


@router.post("/tts")
async def text_to_speech(body: VoiceIn, _: User = Depends(get_current_user)):
    # Non-streaming so provider errors (bad key, unknown voice, quota) surface
    # as real HTTP errors the client can show, instead of a truncated stream.
    try:
        audio = await synthesize(body.text, body.voice_id)
        return Response(content=audio, media_type="audio/mpeg")
    except VoiceNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response is not None else str(exc)
        code = exc.response.status_code if exc.response is not None else "?"
        raise HTTPException(status_code=502, detail=f"ElevenLabs returned {code}: {detail}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach ElevenLabs: {exc}")


@router.post("/transcribe")
async def speech_to_text(file: UploadFile, _: User = Depends(get_current_user)):
    audio = await file.read()
    if len(audio) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio exceeds 25MB limit")
    try:
        text = await transcribe(audio, file.filename or "audio.webm")
        return {"text": text}
    except VoiceNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
