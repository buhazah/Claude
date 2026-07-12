"""Computer-use routes: gated 'next action' oracle for the desktop app.

Disabled unless JARVIS_ENABLE_COMPUTER_USE=true. Even then, the server only
returns the *next* action for the client to execute under the user's
supervision — it never controls anything itself.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..computer.loop import ComputerUseError, computer_step
from ..config import settings
from ..db import User
from ..security import get_current_user

router = APIRouter(prefix="/api/computer", tags=["computer"])


class StepIn(BaseModel):
    messages: list[dict] = Field(description="Anthropic-format running history (incl. screenshots)")
    width: int = Field(ge=100, le=8000)
    height: int = Field(ge=100, le=8000)


@router.get("/config")
async def computer_config(_: User = Depends(get_current_user)):
    return {
        "enabled": settings.enable_computer_use,
        "model": settings.computer_use_model if settings.enable_computer_use else "",
        "max_steps": settings.computer_use_max_steps,
    }


@router.post("/step")
async def step(body: StepIn, user: User = Depends(get_current_user)):
    # This is the most powerful capability: globally gated AND owner-only.
    if not settings.enable_computer_use:
        raise HTTPException(
            status_code=403,
            detail="Computer control is disabled. Set JARVIS_ENABLE_COMPUTER_USE=true to enable it.",
        )
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Computer control requires the owner account.")
    if len(body.messages) > settings.computer_use_max_steps * 4 + 8:
        raise HTTPException(status_code=400, detail="Conversation too long; stop and restart the task.")
    try:
        return await computer_step(body.messages, body.width, body.height)
    except ComputerUseError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
