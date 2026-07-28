"""Append-only audit log.

Distinct from the event bus on purpose. The bus is best-effort observability —
bounded queues, dropped events, at-most-once. The audit log is the opposite:
every consequential action is written durably before it happens, and nothing
ever updates or deletes a row.

Entries are hash-chained. Each row's hash covers the previous row's hash, so
removing or editing history breaks the chain and ``verify`` says so. That does
not stop a determined attacker with database access from rewriting the whole
chain, but it does make silent, partial tampering detectable — which is the
realistic threat for a system that runs shell commands on your behalf.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

import structlog
from sqlalchemy import select

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.ids import new_id
from jarvis.persistence.db import Database
from jarvis.persistence.models import AuditRow

log = structlog.get_logger(__name__)

GENESIS = "0" * 64


def entry_hash(previous: str, entry: dict[str, Any]) -> str:
    payload = json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{previous}{payload}".encode()).hexdigest()


class AuditLog(Protocol):
    async def record(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        run_id: str | None = None,
        actor: str = "jarvis",
        approved: bool = False,
    ) -> str: ...

    async def entries(self, *, limit: int = 100) -> list[dict[str, Any]]: ...

    async def verify(self) -> tuple[bool, str | None]: ...


class NullAuditLog:
    """Used when no database is configured. Records nothing, and says so."""

    async def record(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        run_id: str | None = None,
        actor: str = "jarvis",
        approved: bool = False,
    ) -> str:
        return ""

    async def entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return []

    async def verify(self) -> tuple[bool, str | None]:
        return True, None


class SqlAuditLog:
    """Durable, hash-chained audit log."""

    def __init__(self, database: Database, clock: Clock = SYSTEM_CLOCK) -> None:
        self._db = database
        self._clock = clock

    async def _tip(self) -> str:
        """Hash of the most recent entry, or the genesis value."""
        async with self._db.session() as session:
            row = (
                await session.execute(select(AuditRow).order_by(AuditRow.id.desc()).limit(1))
            ).scalar_one_or_none()
            return str(row.payload.get("_hash", GENESIS)) if row else GENESIS

    async def record(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        run_id: str | None = None,
        actor: str = "jarvis",
        approved: bool = False,
    ) -> str:
        entry_id = new_id("aud")
        at = self._clock.now()
        body = {
            "id": entry_id,
            "at": at.isoformat(),
            "topic": topic,
            "run_id": run_id,
            "actor": actor,
            "approved": approved,
            "payload": payload,
        }
        chained = {**body, "_hash": entry_hash(await self._tip(), body)}

        async with self._db.session() as session:
            session.add(
                AuditRow(
                    id=entry_id,
                    at=at,
                    topic=topic,
                    run_id=run_id,
                    actor=actor,
                    payload=chained,
                    approved=approved,
                )
            )
            await session.commit()
        return entry_id

    async def entries(self, *, limit: int = 100) -> list[dict[str, Any]]:
        async with self._db.session() as session:
            rows = (
                (await session.execute(select(AuditRow).order_by(AuditRow.id.desc()).limit(limit)))
                .scalars()
                .all()
            )
        return [
            {
                "id": row.id,
                "at": row.at,
                "topic": row.topic,
                "run_id": row.run_id,
                "actor": row.actor,
                "approved": row.approved,
                # The stored column is the chained envelope; callers want the
                # event they recorded, not Jarvis's bookkeeping around it.
                "payload": (row.payload or {}).get("payload", {}),
                "hash": (row.payload or {}).get("_hash"),
            }
            for row in rows
        ]

    async def verify(self) -> tuple[bool, str | None]:
        """Re-walk the chain. Returns ``(ok, first_broken_id)``."""
        async with self._db.session() as session:
            rows = (
                (await session.execute(select(AuditRow).order_by(AuditRow.id.asc())))
                .scalars()
                .all()
            )

        previous = GENESIS
        for row in rows:
            stored = dict(row.payload or {})
            claimed = stored.pop("_hash", None)
            if entry_hash(previous, stored) != claimed:
                return False, row.id
            previous = str(claimed)
        return True, None
