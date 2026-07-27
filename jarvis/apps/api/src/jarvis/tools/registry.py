"""Tool registry and the permission wall.

Every capability Jarvis has in the world — shell, browser, email, deploys —
arrives through here, which makes this the single place where "should this be
allowed" is answered. Tiers are deliberately coarse; a tier is a *promise about
blast radius*, not a category:

``SAFE``       read-only, reversible, no side effects outside Jarvis.
``SENSITIVE``  touches real data or costs money; runs, but is audit-logged.
``DANGEROUS``  irreversible or outward-facing; requires explicit approval.

Permission grants are data checked at call time, never ambient authority, so
an agent cannot widen its own reach by reasoning about it.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.errors import ApprovalRequiredError, NotFoundError, PermissionDeniedError
from jarvis.llm.base import ToolSchema

log = structlog.get_logger(__name__)

ToolFn = Callable[..., Any | Awaitable[Any]]


class Permission(IntEnum):
    SAFE = 0
    SENSITIVE = 1
    DANGEROUS = 2


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    fn: ToolFn
    parameters: dict[str, Any] = field(default_factory=dict)
    permission: Permission = Permission.SAFE
    namespace: str = "core"

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.parameters or {"type": "object", "properties": {}},
        )


@dataclass(slots=True)
class Grant:
    """An explicit, scoped permission. Absence of a grant is a denial."""

    tool: str  # exact name, or "namespace.*", or "*"
    max_permission: Permission = Permission.SAFE
    auto_approve: bool = False

    def covers(self, tool: Tool) -> bool:
        if self.tool == "*":
            return True
        if self.tool.endswith(".*"):
            return tool.namespace == self.tool[:-2]
        return self.tool == tool.name


class ToolRegistry:
    def __init__(self, *, bus: EventBus | None = None, grants: list[Grant] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._bus = bus
        self._grants = grants if grants is not None else [Grant("*", Permission.SAFE)]

    def register(
        self,
        name: str,
        description: str,
        fn: ToolFn,
        *,
        parameters: dict[str, Any] | None = None,
        permission: Permission = Permission.SAFE,
        namespace: str = "core",
    ) -> Tool:
        tool = Tool(
            name=name,
            description=description,
            fn=fn,
            parameters=parameters or {"type": "object", "properties": {}},
            permission=permission,
            namespace=namespace,
        )
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise NotFoundError(f"unknown tool: {name}") from None

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas_for(self, names: tuple[str, ...] | list[str]) -> list[ToolSchema]:
        """Provider-ready schemas for an agent's allowlist, skipping unknowns.

        Unknown names are skipped rather than raising: an agent spec may list a
        tool whose connector is not installed yet, and that should degrade the
        agent's reach, not break the request.
        """
        return [self._tools[n].schema() for n in names if n in self._tools]

    def check(self, tool: Tool) -> Grant:
        """Return the grant authorising this call, or raise."""
        applicable = [g for g in self._grants if g.covers(tool)]
        if not applicable:
            raise PermissionDeniedError(f"no grant covers tool '{tool.name}'")
        best = max(applicable, key=lambda g: (g.max_permission, g.auto_approve))
        if tool.permission > best.max_permission:
            raise PermissionDeniedError(
                f"tool '{tool.name}' requires {tool.permission.name}, "
                f"granted {best.max_permission.name}"
            )
        if tool.permission is Permission.DANGEROUS and not best.auto_approve:
            raise ApprovalRequiredError(
                f"tool '{tool.name}' needs explicit approval", tool=tool.name
            )
        return best

    async def invoke(
        self, name: str, arguments: dict[str, Any], *, run_id: str | None = None
    ) -> Any:
        tool = self.get(name)
        self.check(tool)
        if self._bus:
            self._bus.publish(
                "tool.called",
                {"tool": name, "permission": tool.permission.name, "arguments": arguments},
                run_id=run_id,
            )
        try:
            result = tool.fn(**arguments)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            if self._bus:
                self._bus.publish("tool.failed", {"tool": name, "error": str(exc)}, run_id=run_id)
            raise
        if self._bus:
            self._bus.publish(
                "tool.succeeded", {"tool": name, "result_preview": str(result)[:200]}, run_id=run_id
            )
        return result
