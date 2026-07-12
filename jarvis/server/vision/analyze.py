"""Screen / image understanding via a vision-capable model.

Used by the desktop app's "look at my screen" feature: it captures a
screenshot and asks JARVIS what it sees / for feedback. Anthropic (Claude)
is preferred; OpenAI is a fallback. Both are multimodal.
"""
from __future__ import annotations

import base64

import httpx

from ..config import settings

# A cheap, fast multimodal model is plenty for screen commentary.
ANTHROPIC_VISION_MODEL = "claude-haiku-4-5-20251001"
OPENAI_VISION_MODEL = "gpt-4o-mini"

DEFAULT_PROMPT = (
    "You are JARVIS looking at the user's screen. In 2-4 sentences, say what's "
    "on screen and offer one genuinely useful, specific observation or next step. "
    "Be concise and direct."
)


class VisionNotConfigured(RuntimeError):
    pass


def parse_data_url(image: str) -> tuple[str, str]:
    """Return (media_type, base64_data) from a data URL or raw base64."""
    if image.startswith("data:"):
        header, _, data = image.partition(",")
        media_type = header[5:].split(";")[0] or "image/png"
        return media_type, data
    return "image/png", image


async def analyze_image(image: str, prompt: str = "", max_tokens: int = 600) -> str:
    media_type, data = parse_data_url(image)
    prompt = prompt.strip() or DEFAULT_PROMPT

    if settings.anthropic_api_key:
        body = {
            "model": ANTHROPIC_VISION_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks).strip()

    if settings.openai_api_key:
        body = {
            "model": OPENAI_VISION_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"authorization": f"Bearer {settings.openai_api_key}"},
                json=body,
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    raise VisionNotConfigured(
        "Screen vision needs an Anthropic or OpenAI API key configured."
    )
