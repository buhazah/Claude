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
from jarvis.observability.audit import AuditLog
from jarvis.security.vault import Vault
from jarvis.tools.approvals import ApprovalBroker, ApprovalState

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
    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        grants: list[Grant] | None = None,
        approvals: ApprovalBroker | None = None,
        audit: AuditLog | None = None,
        vault: Vault | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._bus = bus
        self._grants = grants if grants is not None else [Grant("*", Permission.SAFE)]
        self._approvals = approvals
        self._audit = audit
        self._vault = vault

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

    async def authorise(
        self,
        tool: Tool,
        arguments: dict[str, Any],
        *,
        run_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        """Check the grant, and park for a human decision when one is required.

        ``check`` answers "is this allowed by policy"; this answers "is it
        allowed *now*". Splitting them keeps the synchronous policy question
        usable on its own — the UI calls it to show what an agent could do
        without triggering an approval request.
        """
        try:
            self.check(tool)
            return
        except ApprovalRequiredError:
            if self._approvals is None:
                raise  # no broker configured: refuse rather than assume consent

        approval = await self._approvals.request(
            tool=tool.name, arguments=arguments, run_id=run_id, agent_id=agent_id
        )
        if approval.state is not ApprovalState.APPROVED:
            if self._audit:
                await self._audit.record(
                    "tool.refused",
                    {"tool": tool.name, "arguments": arguments, "state": approval.state.value},
                    run_id=run_id,
                    approved=False,
                )
            raise PermissionDeniedError(
                f"tool '{tool.name}' was {approval.state.value}"
                + (f": {approval.reason}" if approval.reason else "")
            )

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        run_id: str | None = None,
        agent_id: str | None = None,
    ) -> Any:
        tool = self.get(name)
        await self.authorise(tool, arguments, run_id=run_id, agent_id=agent_id)

        # The model never holds a secret; it names one. References are resolved
        # here, *after* authorisation and the audit write below, so the log and
        # the approval prompt both record `${vault:stripe}` rather than the key
        # itself — which is what makes the audit trail safe to keep.
        call_arguments = arguments
        if self._vault is not None:
            call_arguments = await self._vault.resolve(arguments)

        if self._audit and tool.permission >= Permission.SENSITIVE:
            # Recorded *before* execution, so the log can never hold an action
            # whose authorisation is missing.
            await self._audit.record(
                "tool.invoked",
                {"tool": name, "arguments": arguments, "permission": tool.permission.name},
                run_id=run_id,
                approved=True,
            )
        if self._bus:
            self._bus.publish(
                "tool.called",
                {"tool": name, "permission": tool.permission.name, "arguments": arguments},
                run_id=run_id,
            )
        try:
            result = tool.fn(**call_arguments)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            # Error messages are the most common leak path of all: an HTTP
            # client quoting the header it failed to send puts the key in the
            # log without anyone writing a line that logs a key.
            message = str(exc)
            if self._vault is not None:
                message = self._vault.redact(message)
            if self._bus:
                self._bus.publish("tool.failed", {"tool": name, "error": message}, run_id=run_id)
            raise
        if self._bus:
            preview = str(result)[:200]
            if self._vault is not None:
                preview = self._vault.redact(preview)
            self._bus.publish(
                "tool.succeeded", {"tool": name, "result_preview": preview}, run_id=run_id
            )
        return result
