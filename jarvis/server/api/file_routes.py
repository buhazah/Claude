"""File routes: upload a document or image and get its content back so the
next chat message can be answered against it."""
from __future__ import annotations

import base64

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..db import User
from ..files.download import verify
from ..files.extract import extract_text, is_image
from ..security import get_current_user
from ..vision.analyze import VisionNotConfigured, analyze_image

router = APIRouter(prefix="/api/files", tags=["files"])

MAX_UPLOAD = 20 * 1024 * 1024  # 20 MB


@router.get("/download/{name}")
async def download(name: str, t: str = ""):
    # Auth is the signed token in `t` (so a plain browser link works).
    if not verify(name, t):
        raise HTTPException(status_code=403, detail="Invalid or expired download link")
    path = (settings.sandbox_dir / name).resolve()
    root = settings.sandbox_dir.resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=name)


@router.post("/analyze")
async def analyze_file(
    file: UploadFile,
    prompt: str = Form(default=""),
    _: User = Depends(get_current_user),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="File exceeds 20MB limit")
    name = file.filename or "upload"

    if is_image(name, file.content_type or ""):
        # Rich description so later questions can be answered from it.
        media = file.content_type or "image/png"
        data_url = f"data:{media};base64,{base64.b64encode(data).decode()}"
        vprompt = prompt.strip() or (
            "Describe this image in thorough detail, including any visible text, "
            "so questions about it can be answered from your description."
        )
        try:
            text = await analyze_image(data_url, vprompt)
        except VisionNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Vision model error: {exc}")
        return {"name": name, "kind": "image", "text": text}

    return {"name": name, "kind": "document", "text": extract_text(data, name)}
