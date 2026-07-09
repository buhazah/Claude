"""Voice routes: text-to-speech (streaming MP3) and server-side transcription."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..config import settings
from ..db import User
from ..schemas import VoiceIn
from ..security import get_current_user
from ..voice.tts import VoiceNotConfigured, stream_synthesize, transcribe

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
    try:
        async def audio():
            async for chunk in stream_synthesize(body.text, body.voice_id):
                yield chunk

        return StreamingResponse(audio(), media_type="audio/mpeg")
    except VoiceNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))


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
