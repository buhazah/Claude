"""The computer port, and a deterministic offline implementation.

Same pattern as the LLM and speech layers (ADR 0001): a narrow protocol, a real
adapter, and an offline one that makes the subsystem testable and demoable with
no browser and no network.

``ScriptedComputer`` is not a mock. It is a tiny in-memory site — pages with
links, buttons and fields — which is what lets the *wall* be tested against
real navigation, real form entry and real committing clicks. Testing a
permission boundary against a mock that answers however the test likes proves
nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import structlog

from jarvis.computer.models import Action, ActionKind, ActionResult, Element, Snapshot

log = structlog.get_logger(__name__)


class Computer(Protocol):
    """Something Jarvis can look at and act on."""

    name: str

    def is_available(self) -> bool: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def observe(self) -> Snapshot: ...

    async def act(self, action: Action) -> ActionResult: ...


@dataclass
class Page:
    """One page of the scripted site."""

    url: str
    title: str = ""
    text: str = ""
    elements: list[Element] = field(default_factory=list)
    # ref → url, for links and buttons that navigate.
    links: dict[str, str] = field(default_factory=dict)


class ScriptedComputer:
    """A tiny in-memory site, for offline runs and for testing the wall."""

    name = "scripted"

    def __init__(self, pages: dict[str, Page] | None = None, *, start_url: str = "about:blank"):
        self.pages = pages or {}
        self.url = start_url
        self.history: list[str] = []
        # Every action that actually executed. The wall's job is to keep
        # refused actions out of here, so tests assert on it directly.
        self.performed: list[Action] = []
        self.started = False

    def is_available(self) -> bool:
        return True

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    def _page(self) -> Page:
        return self.pages.get(self.url, Page(url=self.url, title="Not found", text=""))

    async def observe(self) -> Snapshot:
        page = self._page()
        return Snapshot(
            url=self.url,
            title=page.title,
            text=page.text,
            elements=list(page.elements),
            screenshot=b"PNG" + self.url.encode(),
        )

    async def act(self, action: Action) -> ActionResult:
        page = self._page()
        detail = ""

        match action.kind:
            case ActionKind.NAVIGATE:
                self.history.append(self.url)
                self.url = action.url
            case ActionKind.BACK:
                if self.history:
                    self.url = self.history.pop()
            case ActionKind.CLICK:
                if target := page.links.get(action.ref):
                    self.history.append(self.url)
                    self.url = target
                detail = f"clicked {action.ref}"
            case ActionKind.TYPE | ActionKind.SELECT:
                for index, element in enumerate(page.elements):
                    if element.ref == action.ref:
                        from dataclasses import replace

                        page.elements[index] = replace(element, value=action.text)
                detail = f"entered {len(action.text)} characters"
            case _:
                detail = action.kind.value

        self.performed.append(action)
        return ActionResult(action=action, ok=True, snapshot=await self.observe(), detail=detail)


class UnavailableComputer:
    """The default when no driver is installed.

    Refusing loudly beats pretending: an agent told "the browser is not
    available" can say so, where one handed a silently empty page will invent
    what it saw.
    """

    name = "none"

    def is_available(self) -> bool:
        return False

    async def start(self) -> None:
        raise RuntimeError("no computer driver installed — install playwright to enable browsing")

    async def stop(self) -> None:
        return None

    async def observe(self) -> Snapshot:
        raise RuntimeError("no computer driver installed")

    async def act(self, action: Action) -> ActionResult:
        raise RuntimeError("no computer driver installed")
