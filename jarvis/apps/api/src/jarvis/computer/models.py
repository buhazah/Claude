"""What Jarvis sees and does when it drives a computer.

The action space is **named elements, not coordinates** (ADR 0009). A snapshot
enumerates the interactive elements on screen with a stable per-snapshot ref, a
role, and an accessible name; actions target a ref. That choice is what makes
an approval prompt readable — "click «Place order — $2,480» on
checkout.example.com" is a decision a human can actually make, where
"click (412, 388)" is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from jarvis.kernel.ids import new_id


class ActionKind(StrEnum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    PRESS = "press"
    SELECT = "select"
    SCROLL = "scroll"
    BACK = "back"
    WAIT = "wait"


@dataclass(slots=True, frozen=True)
class Element:
    """One interactive thing on screen."""

    ref: str
    role: str
    name: str
    value: str = ""
    enabled: bool = True
    # True for password and payment-shaped inputs. The model never types into
    # these — not "with approval", never (ADR 0009).
    secret: bool = False

    def describe(self) -> str:
        label = self.name or self.value or self.ref
        return f"{self.role} «{label}»"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "role": self.role,
            "name": self.name,
            "value": self.value,
            "enabled": self.enabled,
            "secret": self.secret,
        }


@dataclass(slots=True)
class Snapshot:
    """One observation of the screen."""

    url: str = "about:blank"
    title: str = ""
    text: str = ""
    elements: list[Element] = field(default_factory=list)
    screenshot: bytes | None = None
    at: datetime | None = None

    def find(self, ref: str) -> Element | None:
        return next((e for e in self.elements if e.ref == ref), None)

    @property
    def host(self) -> str:
        """The host, or "" for about:blank and other host-less URLs."""
        _, _, rest = self.url.partition("://")
        if not rest:
            return ""
        authority = rest.split("/", 1)[0]
        # Strip credentials and port: "user@evil.com:8080" is host evil.com.
        return authority.rpartition("@")[2].split(":", 1)[0].lower()

    def to_dict(self, *, with_elements: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "has_screenshot": self.screenshot is not None,
        }
        if with_elements:
            payload["elements"] = [e.to_dict() for e in self.elements]
        return payload


@dataclass(slots=True)
class Action:
    """One thing to do."""

    kind: ActionKind
    ref: str = ""
    text: str = ""
    url: str = ""
    key: str = ""
    amount: int = 0
    id: str = field(default_factory=lambda: new_id("act"))

    def signature(self) -> tuple[str, ...]:
        """Identity for loop detection — the *intent*, not the attempt id."""
        return (self.kind.value, self.ref, self.text, self.url, self.key, str(self.amount))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "ref": self.ref,
            "text": self.text,
            "url": self.url,
            "key": self.key,
            "amount": self.amount,
        }


@dataclass(slots=True)
class ActionResult:
    """What happened, and what the screen looks like now."""

    action: Action
    ok: bool
    snapshot: Snapshot
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "ok": self.ok,
            "detail": self.detail,
            "page": self.snapshot.to_dict(),
        }
