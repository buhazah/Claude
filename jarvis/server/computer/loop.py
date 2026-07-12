"""Claude 'computer use' — one stateless step of the control loop.

The server is only the brain + API key: given the running Anthropic-format
message history (which includes screenshots the client captured), it asks
Claude for the next GUI action(s) using the computer tool and returns the
assistant message. The **client** (the desktop app) owns the screen and the
mouse/keyboard and executes the returned actions locally, then sends back a
new screenshot as a tool_result and calls again.

This split means the server never touches the user's input devices, and the
API key never reaches the desktop.
"""
from __future__ import annotations

import httpx

from ..config import settings

API = "https://api.anthropic.com/v1/messages"

SYSTEM = (
    "You are JARVIS operating the user's computer to accomplish a goal. You see "
    "screenshots and control the mouse and keyboard via the computer tool. Work "
    "in small, verifiable steps: take a screenshot, decide one action, then "
    "check the result. Be careful and precise. Never take destructive or "
    "irreversible actions (deleting files, sending messages, making purchases, "
    "changing security settings) without the user's explicit instruction. When "
    "the goal is complete, stop and briefly summarize what you did."
)


class ComputerUseError(RuntimeError):
    pass


async def computer_step(messages: list[dict], width: int, height: int, max_tokens: int = 1024) -> dict:
    """Return Claude's raw assistant message (content blocks + stop_reason)."""
    if not settings.anthropic_api_key:
        raise ComputerUseError("Computer use requires ANTHROPIC_API_KEY.")
    tools = [{
        "type": settings.computer_use_tool,
        "name": "computer",
        "display_width_px": int(width),
        "display_height_px": int(height),
        "display_number": 1,
    }]
    body = {
        "model": settings.computer_use_model,
        "max_tokens": max_tokens,
        "system": SYSTEM,
        "tools": tools,
        "messages": messages,
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": settings.computer_use_beta,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(API, headers=headers, json=body)
    if resp.status_code != 200:
        raise ComputerUseError(f"Anthropic {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return {
        "content": data.get("content", []),
        "stop_reason": data.get("stop_reason"),
        "usage": data.get("usage", {}),
    }
