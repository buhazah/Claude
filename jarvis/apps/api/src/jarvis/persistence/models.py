"""Relational schema.

One schema serves both deployments. The only dialect-specific piece is the
embedding column: on Postgres it is a real ``vector`` that pgvector can index,
on SQLite it is JSON. ``EmbeddingVector`` below hides that difference so every
query above this layer is written once.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

EMBEDDING_DIMENSIONS = 256


class Base(DeclarativeBase):
    pass


# JSONB on Postgres (indexable, typed); plain JSON on SQLite.
JsonColumn = JSON().with_variant(JSONB(), "postgresql")


class EmbeddingVector(TypeDecorator[list[float]]):
    """A vector column that becomes ``pgvector.Vector`` on Postgres.

    pgvector is imported lazily and only for the Postgres dialect, so a
    local-first install needs neither the extension nor the Python package.
    """

    impl = Text
    cache_ok = True

    class comparator_factory(TypeDecorator.Comparator[list[float]]):
        """Re-expose pgvector's distance operators.

        A ``TypeDecorator`` does not inherit the comparator of the type it
        wraps, so ``column.cosine_distance(...)`` would not exist even though
        the underlying column really is a ``vector``. Declaring the operator
        here restores it without giving up the dialect-swapping the decorator
        is there for.
        """

        def cosine_distance(self, other: list[float]) -> Any:
            return self.op("<=>", return_type=Float)(other)

        def l2_distance(self, other: list[float]) -> Any:
            return self.op("<->", return_type=Float)(other)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(EMBEDDING_DIMENSIONS))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[float] | None, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps([round(v, 6) for v in value])

    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return list(json.loads(value))


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MemoryRow(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JsonColumn, default=list)
    source: Mapped[str | None] = mapped_column(String(255))
    salience: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector)
    # Superseded rows are kept for audit but excluded from recall.
    superseded_by: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        # The hot path is "live memories in this scope, newest first".
        Index("ix_memories_scope_live", "scope", "superseded_by", "created_at"),
    )


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)
    routing: Mapped[list[dict[str, Any]]] = mapped_column(JsonColumn, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list[StepRow]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="StepRow.position",
        lazy="selectin",
    )


class StepRow(Base):
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped[RunRow] = relationship(back_populates="steps")


class DocumentRow(Base):
    """An ingested source. Chunks hang off it and die with it."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    # Content hash, so re-ingesting an unchanged source is a no-op rather than
    # a second copy that skews retrieval toward whatever was ingested twice.
    fingerprint: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class ChunkRow(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Where inside the document: "p. 4", "slide 2", "Sheet1!1:40", "lines 1-80".
    locator: Mapped[str] = mapped_column(String(255), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector)


class AgentMetricsRow(Base):
    """Per-agent performance, durable across restarts so routing keeps learning."""

    __tablename__ = "agent_metrics"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    runs: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    recent_latencies_ms: Mapped[list[float]] = mapped_column(JsonColumn, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditRow(Base):
    """Append-only record of consequential actions. Never updated, never deleted."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    topic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), default="jarvis")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
