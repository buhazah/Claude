"""Workflow and run storage.

The run store is the load-bearing half: it is what makes suspension durable.
Everything the engine needs to continue — cursor, context, records — round-trips
through here, so a workflow waiting on an approval is a row, not a coroutine.
"""

from __future__ import annotations

from typing import Protocol

import structlog
from sqlalchemy import select

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.persistence.db import Database
from jarvis.persistence.models import TriggerRow, WorkflowRow, WorkflowRunRow
from jarvis.workflows.models import (
    Trigger,
    TriggerKind,
    Workflow,
    WorkflowRun,
    WorkflowRunState,
)

log = structlog.get_logger(__name__)


class WorkflowStore(Protocol):
    async def save(self, workflow: Workflow) -> Workflow: ...

    async def get(self, workflow_id: str) -> Workflow | None: ...

    async def all(self) -> list[Workflow]: ...

    async def remove(self, workflow_id: str) -> bool: ...

    async def save_run(self, run: WorkflowRun) -> WorkflowRun: ...

    async def get_run(self, run_id: str) -> WorkflowRun | None: ...

    async def runs(
        self, *, workflow_id: str | None = None, limit: int = 50
    ) -> list[WorkflowRun]: ...

    async def suspended_runs(self) -> list[WorkflowRun]: ...

    async def save_trigger(self, trigger: Trigger) -> Trigger: ...

    async def triggers(self) -> list[Trigger]: ...

    async def remove_trigger(self, trigger_id: str) -> bool: ...


class InMemoryWorkflowStore:
    def __init__(self, clock: Clock = SYSTEM_CLOCK) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._runs: dict[str, WorkflowRun] = {}
        self._triggers: dict[str, Trigger] = {}
        self._clock = clock

    async def save(self, workflow: Workflow) -> Workflow:
        workflow.created_at = workflow.created_at or self._clock.now()
        self._workflows[workflow.id] = workflow.model_copy(deep=True)
        return workflow

    async def get(self, workflow_id: str) -> Workflow | None:
        stored = self._workflows.get(workflow_id)
        return stored.model_copy(deep=True) if stored else None

    async def all(self) -> list[Workflow]:
        return [w.model_copy(deep=True) for w in self._workflows.values()]

    async def remove(self, workflow_id: str) -> bool:
        return self._workflows.pop(workflow_id, None) is not None

    async def save_run(self, run: WorkflowRun) -> WorkflowRun:
        # Copied in and out, because the SQL store round-trips through JSON and
        # therefore hands back detached objects. Returning live references here
        # would make the two backends behave differently — a caller could
        # observe engine mutations without re-reading, or corrupt stored state
        # by mutating what it was given.
        self._runs[run.id] = run.model_copy(deep=True)
        return run

    async def get_run(self, run_id: str) -> WorkflowRun | None:
        stored = self._runs.get(run_id)
        return stored.model_copy(deep=True) if stored else None

    async def runs(self, *, workflow_id: str | None = None, limit: int = 50) -> list[WorkflowRun]:
        found = [
            r.model_copy(deep=True)
            for r in self._runs.values()
            if workflow_id is None or r.workflow_id == workflow_id
        ]
        found.reverse()
        return found[:limit]

    async def suspended_runs(self) -> list[WorkflowRun]:
        return [
            r.model_copy(deep=True)
            for r in self._runs.values()
            if r.state is WorkflowRunState.AWAITING_APPROVAL
        ]

    async def save_trigger(self, trigger: Trigger) -> Trigger:
        self._triggers[trigger.id] = trigger.model_copy(deep=True)
        return trigger

    async def triggers(self) -> list[Trigger]:
        return [t.model_copy(deep=True) for t in self._triggers.values()]

    async def remove_trigger(self, trigger_id: str) -> bool:
        return self._triggers.pop(trigger_id, None) is not None


class SqlWorkflowStore:
    """Durable workflows, runs and triggers."""

    def __init__(self, database: Database, clock: Clock = SYSTEM_CLOCK) -> None:
        self._db = database
        self._clock = clock

    async def save(self, workflow: Workflow) -> Workflow:
        workflow.created_at = workflow.created_at or self._clock.now()
        async with self._db.session() as session:
            row = await session.get(WorkflowRow, workflow.id)
            payload = workflow.model_dump(mode="json")
            if row is None:
                session.add(
                    WorkflowRow(
                        id=workflow.id,
                        name=workflow.name,
                        description=workflow.description,
                        enabled=workflow.enabled,
                        definition=payload,
                        created_at=workflow.created_at,
                    )
                )
            else:
                row.name = workflow.name
                row.description = workflow.description
                row.enabled = workflow.enabled
                row.definition = payload
            await session.commit()
        return workflow

    async def get(self, workflow_id: str) -> Workflow | None:
        async with self._db.session() as session:
            row = await session.get(WorkflowRow, workflow_id)
            return Workflow.model_validate(row.definition) if row else None

    async def all(self) -> list[Workflow]:
        async with self._db.session() as session:
            rows = (
                (await session.execute(select(WorkflowRow).order_by(WorkflowRow.id.desc())))
                .scalars()
                .all()
            )
        return [Workflow.model_validate(row.definition) for row in rows]

    async def remove(self, workflow_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.get(WorkflowRow, workflow_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
        return True

    async def save_run(self, run: WorkflowRun) -> WorkflowRun:
        async with self._db.session() as session:
            row = await session.get(WorkflowRunRow, run.id)
            payload = run.model_dump(mode="json")
            if row is None:
                session.add(
                    WorkflowRunRow(
                        id=run.id,
                        workflow_id=run.workflow_id,
                        state=run.state.value,
                        cursor=run.cursor,
                        awaiting_approval_id=run.awaiting_approval_id,
                        snapshot=payload,
                        created_at=run.created_at or self._clock.now(),
                        ended_at=run.ended_at,
                    )
                )
            else:
                row.state = run.state.value
                row.cursor = run.cursor
                row.awaiting_approval_id = run.awaiting_approval_id
                row.snapshot = payload
                row.ended_at = run.ended_at
            await session.commit()
        return run

    async def get_run(self, run_id: str) -> WorkflowRun | None:
        async with self._db.session() as session:
            row = await session.get(WorkflowRunRow, run_id)
            return WorkflowRun.model_validate(row.snapshot) if row else None

    async def runs(self, *, workflow_id: str | None = None, limit: int = 50) -> list[WorkflowRun]:
        statement = (
            select(WorkflowRunRow)
            .order_by(WorkflowRunRow.created_at.desc(), WorkflowRunRow.id.desc())
            .limit(limit)
        )
        if workflow_id is not None:
            statement = statement.where(WorkflowRunRow.workflow_id == workflow_id)
        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [WorkflowRun.model_validate(row.snapshot) for row in rows]

    async def suspended_runs(self) -> list[WorkflowRun]:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(WorkflowRunRow).where(
                            WorkflowRunRow.state == WorkflowRunState.AWAITING_APPROVAL.value
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [WorkflowRun.model_validate(row.snapshot) for row in rows]

    async def save_trigger(self, trigger: Trigger) -> Trigger:
        async with self._db.session() as session:
            row = await session.get(TriggerRow, trigger.id)
            payload = trigger.model_dump(mode="json")
            if row is None:
                session.add(
                    TriggerRow(
                        id=trigger.id,
                        workflow_id=trigger.workflow_id,
                        kind=trigger.kind.value,
                        enabled=trigger.enabled,
                        definition=payload,
                        last_fired_at=trigger.last_fired_at,
                    )
                )
            else:
                row.enabled = trigger.enabled
                row.definition = payload
                row.last_fired_at = trigger.last_fired_at
            await session.commit()
        return trigger

    async def triggers(self) -> list[Trigger]:
        async with self._db.session() as session:
            rows = (await session.execute(select(TriggerRow))).scalars().all()
        return [Trigger.model_validate(row.definition) for row in rows]

    async def remove_trigger(self, trigger_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.get(TriggerRow, trigger_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
        return True


__all__ = [
    "InMemoryWorkflowStore",
    "SqlWorkflowStore",
    "Trigger",
    "TriggerKind",
    "WorkflowStore",
]
