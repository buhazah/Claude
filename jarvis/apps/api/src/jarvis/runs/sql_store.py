"""Durable run storage.

A run is mutated many times while it executes — a step starts, a step ends, a
token arrives — and read rarely. Awaiting the database on every mutation would
put IO on the streaming hot path for no benefit, so the split is:

* **mutation is synchronous and in-memory** — ``create``, ``start_step``,
  ``end_step``, ``finish`` operate on the ``Run`` object;
* **persistence is explicit and awaited** — ``persist`` writes the whole run at
  meaningful checkpoints (creation, and completion).

The in-memory store implements the same interface with a no-op ``persist``,
which is why the runtime is identical in both deployments.
"""

from __future__ import annotations

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.persistence.db import Database
from jarvis.persistence.models import RunRow, StepRow
from jarvis.runs.models import Run, RunState, RunStore, Step, StepKind

log = structlog.get_logger(__name__)


def _to_run(row: RunRow) -> Run:
    return Run(
        id=row.id,
        request=row.request,
        agent_id=row.agent_id,
        state=RunState(row.state),
        output=row.output or "",
        error=row.error,
        created_at=row.created_at,
        ended_at=row.ended_at,
        routing=list(row.routing or []),
        steps=[
            Step(
                id=step.id,
                kind=StepKind(step.kind),
                label=step.label,
                state=RunState(step.state),
                detail=dict(step.detail or {}),
                started_at=step.started_at,
                ended_at=step.ended_at,
                cost_usd=step.cost_usd,
                tokens=step.tokens,
            )
            for step in row.steps
        ],
    )


class SqlRunStore(RunStore):
    """``RunStore`` backed by SQLite or Postgres."""

    def __init__(self, database: Database, clock: Clock = SYSTEM_CLOCK) -> None:
        super().__init__(clock=clock)
        self._db = database

    async def persist(self, run: Run) -> None:
        """Upsert the run and replace its steps.

        Steps are rewritten wholesale rather than diffed: a run has a handful of
        them, and "the rows match the object" is a much easier invariant to hold
        than an incremental sync.
        """
        values = {
            "id": run.id,
            "request": run.request,
            "agent_id": run.agent_id,
            "state": run.state.value,
            "output": run.output,
            "error": run.error,
            "routing": run.routing,
            "created_at": run.created_at or self._clock.now(),
            "ended_at": run.ended_at,
        }

        async with self._db.session() as session:
            if self._db.is_postgres:
                statement = pg_insert(RunRow).values(**values)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[RunRow.id],
                        set_={
                            key: statement.excluded[key]
                            for key in ("state", "output", "error", "routing", "ended_at")
                        },
                    )
                )
            else:
                existing = await session.get(RunRow, run.id)
                if existing is None:
                    session.add(RunRow(**values))
                else:
                    for key, value in values.items():
                        setattr(existing, key, value)

            await session.execute(delete(StepRow).where(StepRow.run_id == run.id))
            for position, step in enumerate(run.steps):
                session.add(
                    StepRow(
                        id=step.id,
                        run_id=run.id,
                        position=position,
                        kind=step.kind.value,
                        label=step.label,
                        state=step.state.value,
                        detail=step.detail,
                        started_at=step.started_at,
                        ended_at=step.ended_at,
                        cost_usd=step.cost_usd,
                        tokens=step.tokens,
                    )
                )
            await session.commit()

    async def get(self, run_id: str) -> Run | None:
        # An in-flight run is not in the database yet, so check memory first —
        # otherwise the UI cannot follow a run while it is still streaming.
        if live := self._runs.get(run_id):
            return live
        async with self._db.session() as session:
            row = await session.get(RunRow, run_id)
            return _to_run(row) if row else None

    async def list(self, *, limit: int = 50, agent_id: str | None = None) -> list[Run]:
        # Ids embed a microsecond timestamp, so they break created_at ties
        # deterministically without needing a separate counter column.
        statement = select(RunRow).order_by(RunRow.created_at.desc(), RunRow.id.desc()).limit(limit)
        if agent_id is not None:
            statement = statement.where(RunRow.agent_id == agent_id)

        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        persisted = [_to_run(row) for row in rows]

        # Merge in runs that have not reached a checkpoint yet, newest first.
        known = {run.id for run in persisted}
        live = [
            run
            for run in reversed(list(self._runs.values()))
            if run.id not in known and (agent_id is None or run.agent_id == agent_id)
        ]
        return [*live, *persisted][:limit]
