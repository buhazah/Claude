"""Human-in-the-loop approvals.

A `DANGEROUS` tool does not fail and it does not silently proceed — it
*suspends*. The run parks, an ``approval.requested`` event goes out, and the
call resumes the moment a human decides. That keeps the streaming connection
open, so the user sees "waiting on you" rather than an error they have to
re-drive from scratch.

Three properties this deliberately has:

* **Denial is a normal outcome**, not an exception path — the model is told the
  tool was refused and carries on with that knowledge.
* **Timeout is denial.** An approval nobody answers must never become an
  approval by default; unattended runs fail closed.
* **The decision is recorded before the tool runs**, so the audit log cannot
  contain an action whose authorisation is missing.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.errors import NotFoundError
from jarvis.kernel.ids import new_id

log = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_S = 300.0


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(slots=True)
class Approval:
    id: str
    tool: str
    arguments: dict[str, Any]
    run_id: str | None
    agent_id: str | None
    requested_at: str
    state: ApprovalState = ApprovalState.PENDING
    reason: str | None = None
    decided_at: str | None = None
    _gate: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "arguments": self.arguments,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "state": self.state.value,
            "reason": self.reason,
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
        }


class ApprovalBroker:
    """Holds pending approvals and unblocks the callers waiting on them."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._bus = bus
        self._clock = clock
        self._timeout_s = timeout_s
        self._approvals: dict[str, Approval] = {}

    def pending(self) -> list[Approval]:
        return [a for a in self._approvals.values() if a.state is ApprovalState.PENDING]

    def all(self, *, limit: int = 50) -> list[Approval]:
        return list(reversed(list(self._approvals.values())))[:limit]

    def get(self, approval_id: str) -> Approval:
        try:
            return self._approvals[approval_id]
        except KeyError:
            raise NotFoundError(f"unknown approval: {approval_id}") from None

    def create(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        run_id: str | None = None,
        agent_id: str | None = None,
    ) -> Approval:
        """Register a pending approval without waiting on it.

        This is what a workflow uses. A workflow may wait overnight for a
        decision, so it records what it needs and *returns* — nothing is held
        open, and the decision can arrive in a different process tomorrow.
        ``request`` below is the interactive variant, for a chat turn where
        somebody is watching the stream.
        """
        approval = Approval(
            id=new_id("apr"),
            tool=tool,
            arguments=arguments,
            run_id=run_id,
            agent_id=agent_id,
            requested_at=self._clock.now().isoformat(),
        )
        self._approvals[approval.id] = approval
        if self._bus:
            self._bus.publish("approval.requested", approval.to_dict(), run_id=run_id)
        log.info("approval_requested", approval=approval.id, tool=tool)
        return approval

    async def request(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        run_id: str | None = None,
        agent_id: str | None = None,
        timeout_s: float | None = None,
    ) -> Approval:
        """Park until a human decides, or the request expires."""
        approval = self.create(tool=tool, arguments=arguments, run_id=run_id, agent_id=agent_id)
        try:
            await asyncio.wait_for(approval._gate.wait(), timeout=timeout_s or self._timeout_s)
        except TimeoutError:
            # Fail closed. An unanswered approval is a denial, never a grant.
            approval.state = ApprovalState.EXPIRED
            approval.reason = "no decision before timeout"
            approval.decided_at = self._clock.now().isoformat()
            if self._bus:
                self._bus.publish("approval.expired", approval.to_dict(), run_id=run_id)
            log.warning("approval_expired", approval=approval.id, tool=tool)

        return approval

    def resolve(self, approval_id: str, *, approved: bool, reason: str | None = None) -> Approval:
        """Record a human decision and release whoever is waiting on it."""
        approval = self.get(approval_id)
        if approval.state is not ApprovalState.PENDING:
            # Deciding twice must not flip an already-executed action.
            return approval

        approval.state = ApprovalState.APPROVED if approved else ApprovalState.DENIED
        approval.reason = reason
        approval.decided_at = self._clock.now().isoformat()
        approval._gate.set()

        if self._bus:
            self._bus.publish(
                "approval.approved" if approved else "approval.denied",
                approval.to_dict(),
                run_id=approval.run_id,
            )
        log.info("approval_resolved", approval=approval.id, approved=approved)
        return approval
