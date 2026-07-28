"""Runs: the durable record of every unit of work.

A run is what the UI's timeline renders, what the cost ledger sums, and what a
resumed workflow reads to know where it stopped. Because every agent execution
produces one, observability is a property of the system rather than a feature
someone has to remember to instrument.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.ids import new_id


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED)


class StepKind(StrEnum):
    AGENT = "agent"
    TOOL = "tool"
    MODEL = "model"
    APPROVAL = "approval"
    MEMORY = "memory"
    NOTE = "note"


class Step(BaseModel):
    id: str = Field(default_factory=lambda: new_id("stp"))
    kind: StepKind
    label: str
    state: RunState = RunState.RUNNING
    detail: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    cost_usd: float = 0.0
    tokens: int = 0

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds() * 1000
        return 0.0


class Run(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    request: str
    agent_id: str
    state: RunState = RunState.PENDING
    steps: list[Step] = Field(default_factory=list)
    output: str = ""
    error: str | None = None
    created_at: datetime | None = None
    ended_at: datetime | None = None
    routing: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return round(sum(s.cost_usd for s in self.steps), 6)

    @property
    def tokens(self) -> int:
        return sum(s.tokens for s in self.steps)

    @property
    def duration_ms(self) -> float:
        if self.created_at and self.ended_at:
            return (self.ended_at - self.created_at).total_seconds() * 1000
        return 0.0


class RunStore:
    """In-process run storage, and the base every durable store extends.

    Mutation (``create``, ``start_step``, ``end_step``, ``finish``) is
    synchronous because it only touches the ``Run`` object — putting IO on the
    streaming path would buy nothing. Durability is the separate, awaited
    ``persist`` call, which is a no-op here and a write in ``SqlRunStore``.
    """

    def __init__(self, clock: Clock = SYSTEM_CLOCK, *, capacity: int = 1000) -> None:
        self._runs: dict[str, Run] = {}
        self._clock = clock
        self._capacity = capacity

    def create(self, *, request: str, agent_id: str) -> Run:
        run = Run(request=request, agent_id=agent_id, created_at=self._clock.now())
        self._runs[run.id] = run
        self._evict()
        return run

    def _evict(self) -> None:
        while len(self._runs) > self._capacity:
            self._runs.pop(next(iter(self._runs)))

    async def persist(self, run: Run) -> None:
        """Checkpoint a run. Nothing to do when the store *is* memory."""

    async def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    async def list(self, *, limit: int = 50, agent_id: str | None = None) -> list[Run]:
        # Insertion order, reversed. Ids and timestamps only resolve to the
        # millisecond, so neither orders runs created in the same tick.
        runs = [r for r in self._runs.values() if agent_id is None or r.agent_id == agent_id]
        runs.reverse()
        return runs[:limit]

    def start_step(self, run: Run, kind: StepKind, label: str, **detail: Any) -> Step:
        step = Step(kind=kind, label=label, detail=detail, started_at=self._clock.now())
        run.steps.append(step)
        return step

    def end_step(
        self,
        step: Step,
        *,
        state: RunState = RunState.SUCCEEDED,
        cost_usd: float = 0.0,
        tokens: int = 0,
        **detail: Any,
    ) -> None:
        step.state = state
        step.ended_at = self._clock.now()
        step.cost_usd = cost_usd
        step.tokens = tokens
        step.detail.update(detail)

    def finish(
        self, run: Run, *, state: RunState, output: str = "", error: str | None = None
    ) -> Run:
        run.state = state
        run.output = output
        run.error = error
        run.ended_at = self._clock.now()
        return run
