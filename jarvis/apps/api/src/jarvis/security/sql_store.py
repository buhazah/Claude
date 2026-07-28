"""Durable backing for the vault, approvals and generated documents.

All three were in-memory through M9 and flagged as such at every milestone.
They sit behind Protocols that were written for exactly this swap, so nothing
above them changes.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import delete, select

from jarvis.agents.spec import AgentMetrics
from jarvis.documents.models import Document
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.persistence.db import Database
from jarvis.persistence.models import (
    AgentMetricsRow,
    ApprovalRow,
    GeneratedDocumentRow,
    SecretRow,
)
from jarvis.tools.approvals import Approval, ApprovalState

log = structlog.get_logger(__name__)


class SqlSecretStore:
    """Ciphertext in a table. The key stays in the environment, never here."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def put(self, name: str, blob: bytes) -> None:
        async with self._db.session() as session:
            existing = await session.get(SecretRow, name)
            if existing is None:
                session.add(SecretRow(name=name, blob=blob))
            else:
                existing.blob = blob
            await session.commit()

    async def get(self, name: str) -> bytes | None:
        async with self._db.session() as session:
            row = await session.get(SecretRow, name)
            return bytes(row.blob) if row else None

    async def names(self) -> list[str]:
        async with self._db.session() as session:
            rows = await session.scalars(select(SecretRow.name).order_by(SecretRow.name))
            return list(rows)

    async def delete(self, name: str) -> bool:
        async with self._db.session() as session:
            result = await session.execute(delete(SecretRow).where(SecretRow.name == name))
            await session.commit()
            return bool(result.rowcount)  # type: ignore[attr-defined]


class SqlApprovalJournal:
    """The decision record, kept across restarts."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def save(self, approval: Approval) -> None:
        async with self._db.session() as session:
            row = await session.get(ApprovalRow, approval.id)
            values = {
                "tool": approval.tool,
                "arguments": approval.arguments,
                "run_id": approval.run_id,
                "agent_id": approval.agent_id,
                "state": approval.state.value,
                "reason": approval.reason,
                "requested_at": approval.requested_at,
                "decided_at": approval.decided_at,
            }
            if row is None:
                session.add(ApprovalRow(id=approval.id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            await session.commit()

    async def load(self, *, limit: int = 200) -> list[Approval]:
        async with self._db.session() as session:
            rows = await session.scalars(
                select(ApprovalRow).order_by(ApprovalRow.requested_at.desc()).limit(limit)
            )
            return [
                Approval(
                    id=r.id,
                    tool=r.tool,
                    arguments=r.arguments,
                    run_id=r.run_id,
                    agent_id=r.agent_id,
                    requested_at=r.requested_at,
                    state=ApprovalState(r.state),
                    reason=r.reason,
                    decided_at=r.decided_at,
                )
                for r in reversed(list(rows))
            ]


class SqlDocumentStore:
    """Generated documents. The body is a JSON blob: it is written once,
    read whole, and never queried by its parts."""

    def __init__(self, database: Database, *, clock: Clock = SYSTEM_CLOCK) -> None:
        self._db = database
        self._clock = clock

    async def save(self, document: Document) -> Document:
        async with self._db.session() as session:
            row = await session.get(GeneratedDocumentRow, document.id)
            body: dict[str, Any] = document.model_dump(mode="json")
            if row is None:
                session.add(
                    GeneratedDocumentRow(
                        id=document.id,
                        title=document.title,
                        kind=document.kind.value,
                        mode=document.mode,
                        state=document.state.value,
                        body=body,
                        created_at=document.created_at or self._clock.now(),
                    )
                )
            else:
                row.title, row.state, row.body = document.title, document.state.value, body
            await session.commit()
        return document

    async def get(self, document_id: str) -> Document | None:
        async with self._db.session() as session:
            row = await session.get(GeneratedDocumentRow, document_id)
            return Document.model_validate(row.body) if row else None

    async def list(self, *, limit: int = 50, mode: str | None = None) -> list[Document]:
        async with self._db.session() as session:
            query = select(GeneratedDocumentRow).order_by(GeneratedDocumentRow.created_at.desc())
            if mode:
                query = query.where(GeneratedDocumentRow.mode == mode)
            rows = await session.scalars(query.limit(limit))
            return [Document.model_validate(r.body) for r in rows]

    async def delete(self, document_id: str) -> bool:
        async with self._db.session() as session:
            result = await session.execute(
                delete(GeneratedDocumentRow).where(GeneratedDocumentRow.id == document_id)
            )
            await session.commit()
            return bool(result.rowcount)  # type: ignore[attr-defined]


class SqlAgentMetricsStore:
    """Per-agent track record, durable so routing keeps what it learned."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def save(self, agent_id: str, metrics: AgentMetrics) -> None:
        async with self._db.session() as session:
            row = await session.get(AgentMetricsRow, agent_id)
            if row is None:
                row = AgentMetricsRow(agent_id=agent_id)
                session.add(row)
            row.runs = metrics.runs
            row.successes = metrics.successes
            row.failures = metrics.failures
            row.total_latency_ms = metrics.total_latency_ms
            row.total_cost_usd = metrics.total_cost_usd
            row.total_tokens = metrics.total_tokens
            row.recent_latencies_ms = list(metrics.recent_latencies_ms)
            await session.commit()

    async def load(self) -> dict[str, AgentMetrics]:
        async with self._db.session() as session:
            rows = await session.scalars(select(AgentMetricsRow))
            return {
                r.agent_id: AgentMetrics(
                    runs=r.runs,
                    successes=r.successes,
                    failures=r.failures,
                    total_latency_ms=r.total_latency_ms,
                    total_cost_usd=r.total_cost_usd,
                    total_tokens=r.total_tokens,
                    recent_latencies_ms=list(r.recent_latencies_ms or []),
                )
                for r in rows
            }
