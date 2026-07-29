"""Computer control, as tools an agent can call.

These are thin: every one of them funnels into :meth:`ComputerSession.act`,
which owns the wall. A tool that reached the driver directly would be a hole in
it, so none of them do.

The registry tier here is the *floor* — driving a browser is at least
``SENSITIVE``, and never silently ``SAFE``. The per-target escalation the
registry cannot see (this click commits money; that field is a password) is the
session's job, because it depends on the page.
"""

from __future__ import annotations

from typing import Any

from jarvis.computer.models import Action, ActionKind
from jarvis.computer.session import ComputerSession
from jarvis.tools.registry import Permission, ToolRegistry

NAMESPACE = "computer"


def register_computer_tools(registry: ToolRegistry, session: ComputerSession) -> None:
    async def _act(kind: ActionKind, **kwargs: Any) -> dict[str, Any]:
        result = await session.act(Action(kind=kind, **kwargs))
        return {"ok": result.ok, "detail": result.detail, "screen": session.context_for_model()}

    async def browser_open(url: str) -> dict[str, Any]:
        if not session.snapshot.url or session.snapshot.url == "about:blank":
            await session.start()
        return await _act(ActionKind.NAVIGATE, url=url)

    async def browser_look() -> dict[str, Any]:
        await session.observe()
        return {"screen": session.context_for_model()}

    async def browser_click(ref: str) -> dict[str, Any]:
        return await _act(ActionKind.CLICK, ref=ref)

    async def browser_type(ref: str, text: str) -> dict[str, Any]:
        return await _act(ActionKind.TYPE, ref=ref, text=text)

    async def browser_press(ref: str, key: str) -> dict[str, Any]:
        return await _act(ActionKind.PRESS, ref=ref, key=key)

    async def browser_select(ref: str, option: str) -> dict[str, Any]:
        return await _act(ActionKind.SELECT, ref=ref, text=option)

    async def browser_scroll(amount: int = 600) -> dict[str, Any]:
        return await _act(ActionKind.SCROLL, amount=amount)

    async def browser_back() -> dict[str, Any]:
        return await _act(ActionKind.BACK)

    ref_param = {
        "ref": {
            "type": "string",
            "description": "Element ref from the last observation, e.g. 'e4'",
        }
    }

    registry.register(
        "browser_open",
        "Open a URL in the browser and describe the resulting page. "
        "Navigating away from allowlisted sites requires the user's approval.",
        browser_open,
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        permission=Permission.SENSITIVE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_look",
        "Re-read the current page: its URL, title, interactive elements and text. "
        "Do this after anything that may have changed the page.",
        browser_look,
        permission=Permission.SAFE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_click",
        "Click an element by ref. Clicks that commit something — pay, delete, send, "
        "confirm — are put to the user first.",
        browser_click,
        parameters={"type": "object", "properties": ref_param, "required": ["ref"]},
        permission=Permission.SENSITIVE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_type",
        "Type text into a field by ref. Password and payment fields are refused: "
        "ask the user to fill those themselves.",
        browser_type,
        parameters={
            "type": "object",
            "properties": {**ref_param, "text": {"type": "string"}},
            "required": ["ref", "text"],
        },
        permission=Permission.SENSITIVE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_press",
        "Press a key (e.g. 'Enter') while an element is focused.",
        browser_press,
        parameters={
            "type": "object",
            "properties": {**ref_param, "key": {"type": "string"}},
            "required": ["ref", "key"],
        },
        permission=Permission.SENSITIVE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_select",
        "Choose an option in a dropdown by its visible label.",
        browser_select,
        parameters={
            "type": "object",
            "properties": {**ref_param, "option": {"type": "string"}},
            "required": ["ref", "option"],
        },
        permission=Permission.SENSITIVE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_scroll",
        "Scroll the page. Positive scrolls down, negative up.",
        browser_scroll,
        parameters={
            "type": "object",
            "properties": {"amount": {"type": "integer", "default": 600}},
        },
        permission=Permission.SAFE,
        namespace=NAMESPACE,
    )
    registry.register(
        "browser_back",
        "Go back to the previous page.",
        browser_back,
        permission=Permission.SAFE,
        namespace=NAMESPACE,
    )
