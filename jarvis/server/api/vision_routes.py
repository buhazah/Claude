"""Vision routes: analyze a screenshot / image the desktop app captured."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..db import User
from ..schemas import VisionIn
from ..security import get_current_user
from ..vision.analyze import VisionNotConfigured, analyze_image

router = APIRouter(prefix="/api/vision", tags=["vision"])


@router.get("/config")
async def vision_config(_: User = Depends(get_current_user)):
    return {"available": bool(settings.anthropic_api_key or settings.openai_api_key)}


@router.post("/analyze")
async def analyze(body: VisionIn, _: User = Depends(get_current_user)):
    if not body.image or len(body.image) > 12_000_000:  # ~9MB image cap
        raise HTTPException(status_code=400, detail="Missing or oversized image")
    try:
        text = await analyze_image(body.image, body.prompt or "")
        return {"text": text}
    except VisionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=f"Vision model error: {detail}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach vision model: {exc}")
