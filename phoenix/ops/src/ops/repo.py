"""Queries. Thin, boring, and all in one place."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ops.models import Client, Evidence, Interaction, Task


def clients(db: Session, *, status: str | None = None) -> Sequence[Client]:
    stmt = select(Client).order_by(Client.name)
    if status:
        stmt = stmt.where(Client.status == status)
    return db.scalars(stmt).all()


def client(db: Session, client_id: int) -> Client | None:
    return db.get(Client, client_id)


def interactions(db: Session, *, client_id: int | None = None, limit: int = 200):
    stmt = select(Interaction).order_by(Interaction.occurred_at.desc()).limit(limit)
    if client_id is not None:
        stmt = stmt.where(Interaction.client_id == client_id)
    return db.scalars(stmt).all()


def evidence(
    db: Session, *, client_id: int | None = None, kind: str | None = None, limit: int = 500
) -> Sequence[Evidence]:
    stmt = select(Evidence).order_by(Evidence.created_at.desc()).limit(limit)
    if client_id is not None:
        stmt = stmt.where(Evidence.client_id == client_id)
    if kind:
        stmt = stmt.where(Evidence.kind == kind)
    return db.scalars(stmt).all()


def tasks(db: Session, *, client_id: int | None = None, open_only: bool = False):
    stmt = select(Task).order_by(Task.due_on.is_(None), Task.due_on, Task.id)
    if client_id is not None:
        stmt = stmt.where(Task.client_id == client_id)
    if open_only:
        stmt = stmt.where(Task.done_at.is_(None))
    return db.scalars(stmt).all()


def timeline(db: Session, client_id: int) -> list[tuple[datetime, str, object]]:
    """Everything that happened to one client, newest first.

    Interactions, evidence and completed tasks merged into one stream — because
    "what has actually happened with this account" is the question asked before
    every client call, and three separate lists do not answer it.
    """
    events: list[tuple[datetime, str, object]] = []
    for i in interactions(db, client_id=client_id, limit=500):
        events.append((i.occurred_at, "interaction", i))
    for e in evidence(db, client_id=client_id):
        events.append((e.created_at, "evidence", e))
    for t in tasks(db, client_id=client_id):
        when = t.done_at or t.created_at
        events.append((when, "task", t))
    events.sort(key=lambda row: row[0], reverse=True)
    return events


def search(db: Session, query: str, limit: int = 50) -> dict[str, list]:
    """One box across everything. `LIKE` is enough at this size."""
    q = query.strip()
    if not q:
        return {"clients": [], "interactions": [], "evidence": [], "tasks": []}
    like = f"%{q}%"
    return {
        "clients": list(
            db.scalars(
                select(Client)
                .where(or_(Client.name.ilike(like), Client.notes.ilike(like)))
                .limit(limit)
            ).all()
        ),
        "interactions": list(
            db.scalars(
                select(Interaction)
                .where(or_(Interaction.summary.ilike(like), Interaction.verbatim.ilike(like)))
                .order_by(Interaction.occurred_at.desc())
                .limit(limit)
            ).all()
        ),
        "evidence": list(
            db.scalars(
                select(Evidence)
                .where(or_(Evidence.verbatim.ilike(like), Evidence.note.ilike(like)))
                .order_by(Evidence.created_at.desc())
                .limit(limit)
            ).all()
        ),
        "tasks": list(
            db.scalars(
                select(Task)
                .where(or_(Task.title.ilike(like), Task.detail.ilike(like)))
                .limit(limit)
            ).all()
        ),
    }


def evidence_rows(db: Session, kind: str | None = None) -> list[tuple[int, int, str, str]]:
    """Shaped for `patterns.cluster`."""
    return [(e.id, e.client_id, e.kind, e.verbatim) for e in evidence(db, kind=kind, limit=2000)]


def client_names(db: Session) -> dict[int, str]:
    return {c.id: c.name for c in db.scalars(select(Client)).all()}
