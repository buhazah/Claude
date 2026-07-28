"""Durable memory store.

Recall is two-phase:

1. **Fetch candidates** — dialect-specific, and the only place the two backends
   differ. Postgres uses a pgvector ANN scan unioned with a lexical match, so
   the database does the narrowing. SQLite pulls a bounded, recency-ordered
   window.
2. **Rank** — ``jarvis.memory.ranking``, identical for every store.

Splitting it this way means adding a backend can change performance but cannot
change which memory surfaces first.
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.memory import ranking
from jarvis.memory.embeddings import Embedder, HashingEmbedder
from jarvis.memory.models import (
    Memory,
    MemoryKind,
    MemoryTier,
    Recall,
    categorize,
    salience_for,
    tier_for,
)
from jarvis.persistence.db import Database
from jarvis.persistence.models import MemoryRow

log = structlog.get_logger(__name__)

# How many rows the database narrows to before Python ranks them. Wide enough
# that a lexical-only match still reaches the ranker, narrow enough to stay cheap.
CANDIDATE_MULTIPLIER = 8
MIN_CANDIDATES = 60


def _to_memory(row: MemoryRow) -> Memory:
    memory = Memory(
        id=row.id,
        content=row.content,
        kind=MemoryKind(row.kind),
        tier=MemoryTier(row.tier),
        scope=row.scope,
        tags=list(row.tags or []),
        source=row.source,
        salience=row.salience,
        created_at=row.created_at,
        last_accessed_at=row.last_accessed_at,
        access_count=row.access_count,
        superseded_by=row.superseded_by,
    )
    memory.embedding = row.embedding
    return memory


class SqlMemoryStore:
    """``MemoryStore`` backed by SQLite or Postgres."""

    def __init__(
        self,
        database: Database,
        *,
        embedder: Embedder | None = None,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._db = database
        self._embedder = embedder or HashingEmbedder()
        self._bus = bus
        self._clock = clock

    async def remember(
        self,
        content: str,
        *,
        kind: MemoryKind | None = None,
        scope: str = "global",
        tags: list[str] | None = None,
        source: str | None = None,
        salience: float | None = None,
    ) -> Memory:
        content = content.strip()
        if not content:
            raise ValueError("cannot remember empty content")

        resolved_kind = kind or categorize(content)
        memory = Memory(
            content=content,
            kind=resolved_kind,
            tier=tier_for(resolved_kind),
            scope=scope,
            tags=tags or [],
            source=source,
            salience=salience if salience is not None else salience_for(resolved_kind, content),
            created_at=self._clock.now(),
        )
        memory.embedding = (await self._embedder.embed([content]))[0]

        async with self._db.session() as session:
            session.add(
                MemoryRow(
                    id=memory.id,
                    content=memory.content,
                    kind=memory.kind.value,
                    tier=memory.tier.value,
                    scope=memory.scope,
                    tags=memory.tags,
                    source=memory.source,
                    salience=memory.salience,
                    created_at=memory.created_at,
                    access_count=0,
                    embedding=memory.embedding,
                )
            )
            await session.commit()

        if self._bus:
            self._bus.publish(
                "memory.written",
                {
                    "id": memory.id,
                    "kind": memory.kind.value,
                    "scope": memory.scope,
                    "salience": memory.salience,
                    "preview": content[:120],
                },
            )
        return memory

    async def get(self, memory_id: str) -> Memory | None:
        async with self._db.session() as session:
            row = await session.get(MemoryRow, memory_id)
            return _to_memory(row) if row else None

    async def forget(self, memory_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.get(MemoryRow, memory_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
        if self._bus:
            self._bus.publish("memory.forgotten", {"id": memory_id})
        return True

    async def all(
        self, *, scope: str | None = None, kind: MemoryKind | None = None, limit: int = 200
    ) -> list[Memory]:
        statement = (
            select(MemoryRow)
            .where(MemoryRow.superseded_by.is_(None))
            .order_by(MemoryRow.created_at.desc(), MemoryRow.id.desc())
            .limit(limit)
        )
        if scope is not None:
            statement = statement.where(MemoryRow.scope == scope)
        if kind is not None:
            statement = statement.where(MemoryRow.kind == kind.value)

        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [_to_memory(row) for row in rows]

    async def count(self) -> int:
        async with self._db.session() as session:
            result = await session.execute(select(func.count()).select_from(MemoryRow))
            return int(result.scalar_one())

    def _base_filter(self, statement, scope: str | None, kinds: list[MemoryKind] | None):  # type: ignore[no-untyped-def]
        statement = statement.where(MemoryRow.superseded_by.is_(None))
        if scope is not None:
            # An agent sees its own scope plus anything global.
            statement = statement.where(MemoryRow.scope.in_([scope, "global"]))
        if kinds:
            statement = statement.where(MemoryRow.kind.in_([k.value for k in kinds]))
        return statement

    async def _candidates(
        self,
        query: str,
        query_vector: list[float],
        *,
        scope: str | None,
        kinds: list[MemoryKind] | None,
        want: int,
    ) -> list[MemoryRow]:
        """Narrow the table to a candidate set for the ranker."""
        async with self._db.session() as session:
            if self._db.is_postgres:
                # Vector neighbours, plus rows that match a query term outright.
                # The union matters: an exact identifier can sit far away in
                # embedding space and would otherwise never reach the ranker.
                vector_hits = (
                    (
                        await session.execute(
                            self._base_filter(select(MemoryRow), scope, kinds)
                            .order_by(MemoryRow.embedding.cosine_distance(query_vector))
                            .limit(want)
                        )
                    )
                    .scalars()
                    .all()
                )

                terms = [term for term in ranking.tokenize(query) if len(term) > 2][:8]
                lexical_hits: list[MemoryRow] = []
                if terms:
                    lexical_hits = list(
                        (
                            await session.execute(
                                self._base_filter(select(MemoryRow), scope, kinds)
                                .where(or_(*[MemoryRow.content.ilike(f"%{t}%") for t in terms]))
                                .limit(want)
                            )
                        )
                        .scalars()
                        .all()
                    )

                merged = {row.id: row for row in [*vector_hits, *lexical_hits]}
                return list(merged.values())

            # SQLite: no ANN index, so take a bounded recent window and let the
            # ranker do the work. Correct, and fast at local-first data volumes.
            return list(
                (
                    await session.execute(
                        self._base_filter(select(MemoryRow), scope, kinds)
                        .order_by(MemoryRow.created_at.desc())
                        .limit(max(want * 4, 500))
                    )
                )
                .scalars()
                .all()
            )

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        scope: str | None = None,
        kinds: list[MemoryKind] | None = None,
        min_score: float = 0.05,
    ) -> list[Recall]:
        query_vector = (await self._embedder.embed([query]))[0]
        want = max(limit * CANDIDATE_MULTIPLIER, MIN_CANDIDATES)

        rows = await self._candidates(query, query_vector, scope=scope, kinds=kinds, want=want)
        if not rows:
            return []

        recalls = ranking.rank(
            [_to_memory(row) for row in rows],
            query=query,
            query_vector=query_vector,
            now=self._clock.now(),
            limit=limit,
            min_score=min_score,
        )

        if recalls:
            await self._mark_accessed([r.memory.id for r in recalls])
            for recall in recalls:
                recall.memory.touch(self._clock.now())

        if self._bus:
            self._bus.publish("memory.recalled", {"query": query[:120], "hits": len(recalls)})
        return recalls

    async def _mark_accessed(self, ids: list[str]) -> None:
        async with self._db.session() as session:
            await session.execute(
                update(MemoryRow)
                .where(MemoryRow.id.in_(ids))
                .values(
                    access_count=MemoryRow.access_count + 1,
                    last_accessed_at=self._clock.now(),
                )
            )
            await session.commit()

    async def supersede(self, old_id: str, new_content: str, **kwargs: object) -> Memory:
        """Replace a stale memory, keeping the original for audit."""
        replacement = await self.remember(new_content, **kwargs)  # type: ignore[arg-type]
        async with self._db.session() as session:
            await session.execute(
                update(MemoryRow).where(MemoryRow.id == old_id).values(superseded_by=replacement.id)
            )
            await session.commit()
        return replacement

    async def upsert_many(self, memories: list[Memory]) -> int:
        """Bulk import, used by knowledge ingestion. Postgres path is a real upsert."""
        if not memories:
            return 0
        payload = [
            {
                "id": m.id,
                "content": m.content,
                "kind": m.kind.value,
                "tier": m.tier.value,
                "scope": m.scope,
                "tags": m.tags,
                "source": m.source,
                "salience": m.salience,
                "created_at": m.created_at or self._clock.now(),
                "access_count": 0,
                "embedding": m.embedding,
            }
            for m in memories
        ]
        async with self._db.session() as session:
            if self._db.is_postgres:
                statement = pg_insert(MemoryRow).values(payload)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[MemoryRow.id],
                        set_={"content": statement.excluded.content},
                    )
                )
            else:
                await session.execute(insert(MemoryRow), payload)
            await session.commit()
        return len(payload)
