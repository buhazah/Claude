"""Knowledge storage and retrieval.

Documents live in their own tables rather than in memory, because they are a
different thing: memory is what Jarvis learned, knowledge is what it was given.
Conflating them would let a 400-page PDF drown out a recorded decision.

Retrieval, however, uses **the same ranker as memory** (ADR 0004). A chunk is
scored on lexical overlap, semantic similarity and recency exactly as a memory
is, so "why did that surface?" has one answer across the whole system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import structlog
from sqlalchemy import delete, func, or_, select

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.knowledge.models import Chunk, Citation, Document, SourceKind
from jarvis.memory import ranking
from jarvis.memory.embeddings import Embedder, HashingEmbedder
from jarvis.memory.models import Memory, MemoryKind
from jarvis.persistence.db import Database
from jarvis.persistence.models import ChunkRow, DocumentRow

log = structlog.get_logger(__name__)

CANDIDATE_MULTIPLIER = 8
MIN_CANDIDATES = 60
SNIPPET_CHARS = 400


class KnowledgeStore(Protocol):
    """Spelled out in full, so a store missing half the contract fails to type."""

    async def add(self, document: Document, chunks: list[Chunk]) -> Document: ...

    async def search(
        self,
        query: str,
        *,
        limit: int = 6,
        scope: str | None = None,
        document_id: str | None = None,
        min_score: float = 0.05,
    ) -> list[Citation]: ...

    async def documents(
        self, *, scope: str | None = None, kind: SourceKind | None = None, limit: int = 100
    ) -> list[Document]: ...

    async def get(self, document_id: str) -> Document | None: ...

    async def remove(self, document_id: str) -> bool: ...

    async def count(self) -> int: ...

    async def find_by_fingerprint(self, fingerprint: str) -> Document | None: ...


def _as_memory(chunk: Chunk, document: Document) -> Memory:
    """Adapt a chunk so the shared ranker can score it.

    Documents are not memories, but ranking them differently would give the
    system two answers to "why did that surface?". The adapter is the seam that
    lets one ranker serve both without merging the stores.
    """
    memory = Memory(
        id=chunk.id,
        content=chunk.content,
        kind=MemoryKind.DOCUMENT,
        scope=document.scope,
        salience=0.6,
        created_at=document.created_at,
    )
    memory.embedding = chunk.embedding
    return memory


class InMemoryKnowledgeStore:
    """Reference implementation, used in dev and tests."""

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, list[Chunk]] = {}
        self._embedder = embedder or HashingEmbedder()
        self._bus = bus
        self._clock = clock

    async def add(self, document: Document, chunks: list[Chunk]) -> Document:
        document.created_at = document.created_at or self._clock.now()
        document.chunk_count = len(chunks)
        vectors = await self._embedder.embed([c.content for c in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.document_id = document.id
            chunk.embedding = vector

        self._documents[document.id] = document
        self._chunks[document.id] = chunks
        if self._bus:
            self._bus.publish(
                "knowledge.ingested",
                {
                    "id": document.id,
                    "title": document.title,
                    "kind": document.kind.value,
                    "chunks": len(chunks),
                },
            )
        return document

    async def get(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    async def find_by_fingerprint(self, fingerprint: str) -> Document | None:
        return next((d for d in self._documents.values() if d.fingerprint == fingerprint), None)

    async def documents(
        self, *, scope: str | None = None, kind: SourceKind | None = None, limit: int = 100
    ) -> list[Document]:
        found = [
            d
            for d in self._documents.values()
            if (scope is None or d.scope == scope) and (kind is None or d.kind == kind)
        ]
        found.sort(key=lambda d: (d.created_at or self._clock.now(), d.id), reverse=True)
        return found[:limit]

    async def remove(self, document_id: str) -> bool:
        self._chunks.pop(document_id, None)
        removed = self._documents.pop(document_id, None) is not None
        if removed and self._bus:
            self._bus.publish("knowledge.removed", {"id": document_id})
        return removed

    async def count(self) -> int:
        return len(self._documents)

    async def search(
        self,
        query: str,
        *,
        limit: int = 6,
        scope: str | None = None,
        document_id: str | None = None,
        min_score: float = 0.05,
    ) -> list[Citation]:
        if not self._chunks:
            return []

        vector = (await self._embedder.embed([query]))[0]
        pairs: list[tuple[Chunk, Document]] = [
            (chunk, document)
            for document_key, chunks in self._chunks.items()
            if (document := self._documents.get(document_key)) is not None
            and (document_id is None or document.id == document_id)
            and (scope is None or document.scope in (scope, "global"))
            for chunk in chunks
        ]
        return _rank_to_citations(
            pairs, query=query, vector=vector, now=self._clock.now(), limit=limit, floor=min_score
        )


def _rank_to_citations(
    pairs: list[tuple[Chunk, Document]],
    *,
    query: str,
    vector: list[float],
    now: datetime,
    limit: int,
    floor: float,
) -> list[Citation]:
    by_id = {chunk.id: (chunk, document) for chunk, document in pairs}
    recalls = ranking.rank(
        [_as_memory(chunk, document) for chunk, document in pairs],
        query=query,
        query_vector=vector,
        now=now,
        limit=limit,
        min_score=floor,
    )

    citations: list[Citation] = []
    for recall in recalls:
        chunk, document = by_id[recall.memory.id]
        citations.append(
            Citation(
                document_id=document.id,
                document_title=document.title,
                source=document.source,
                locator=chunk.locator,
                snippet=chunk.content[:SNIPPET_CHARS],
                score=recall.score,
                signals={
                    "lexical": recall.lexical,
                    "semantic": recall.semantic,
                    "recency": recall.recency,
                },
            )
        )
    return citations


class SqlKnowledgeStore:
    """Durable knowledge, with the same two-phase retrieval as memory."""

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

    async def add(self, document: Document, chunks: list[Chunk]) -> Document:
        document.created_at = document.created_at or self._clock.now()
        document.chunk_count = len(chunks)
        vectors = await self._embedder.embed([c.content for c in chunks]) if chunks else []

        async with self._db.session() as session:
            session.add(
                DocumentRow(
                    id=document.id,
                    title=document.title,
                    source=document.source,
                    kind=document.kind.value,
                    scope=document.scope,
                    doc_metadata=document.metadata,
                    chunk_count=len(chunks),
                    bytes=document.bytes,
                    fingerprint=document.fingerprint,
                    created_at=document.created_at,
                )
            )
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.document_id = document.id
                chunk.embedding = vector
                session.add(
                    ChunkRow(
                        id=chunk.id,
                        document_id=document.id,
                        content=chunk.content,
                        locator=chunk.locator,
                        position=chunk.position,
                        tokens=chunk.tokens,
                        embedding=vector,
                    )
                )
            await session.commit()

        if self._bus:
            self._bus.publish(
                "knowledge.ingested",
                {
                    "id": document.id,
                    "title": document.title,
                    "kind": document.kind.value,
                    "chunks": len(chunks),
                },
            )
        return document

    async def get(self, document_id: str) -> Document | None:
        async with self._db.session() as session:
            row = await session.get(DocumentRow, document_id)
            return _to_document(row) if row else None

    async def find_by_fingerprint(self, fingerprint: str) -> Document | None:
        async with self._db.session() as session:
            row = (
                await session.execute(
                    select(DocumentRow).where(DocumentRow.fingerprint == fingerprint).limit(1)
                )
            ).scalar_one_or_none()
            return _to_document(row) if row else None

    async def documents(
        self, *, scope: str | None = None, kind: SourceKind | None = None, limit: int = 100
    ) -> list[Document]:
        statement = (
            select(DocumentRow)
            .order_by(DocumentRow.created_at.desc(), DocumentRow.id.desc())
            .limit(limit)
        )
        if scope is not None:
            statement = statement.where(DocumentRow.scope == scope)
        if kind is not None:
            statement = statement.where(DocumentRow.kind == kind.value)

        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [_to_document(row) for row in rows]

    async def remove(self, document_id: str) -> bool:
        async with self._db.session() as session:
            row = await session.get(DocumentRow, document_id)
            if row is None:
                return False
            await session.execute(delete(ChunkRow).where(ChunkRow.document_id == document_id))
            await session.delete(row)
            await session.commit()
        if self._bus:
            self._bus.publish("knowledge.removed", {"id": document_id})
        return True

    async def count(self) -> int:
        async with self._db.session() as session:
            result = await session.execute(select(func.count()).select_from(DocumentRow))
            return int(result.scalar_one())

    async def search(
        self,
        query: str,
        *,
        limit: int = 6,
        scope: str | None = None,
        document_id: str | None = None,
        min_score: float = 0.05,
    ) -> list[Citation]:
        vector = (await self._embedder.embed([query]))[0]
        want = max(limit * CANDIDATE_MULTIPLIER, MIN_CANDIDATES)

        async with self._db.session() as session:
            base = select(ChunkRow, DocumentRow).join(
                DocumentRow, ChunkRow.document_id == DocumentRow.id
            )
            if document_id is not None:
                base = base.where(DocumentRow.id == document_id)
            if scope is not None:
                base = base.where(DocumentRow.scope.in_([scope, "global"]))

            if self._db.is_postgres:
                # ANN neighbours ∪ lexical hits, for the same reason as memory:
                # an exact identifier can sit far away in embedding space.
                rows = list(
                    (
                        await session.execute(
                            base.order_by(ChunkRow.embedding.cosine_distance(vector)).limit(want)
                        )
                    ).all()
                )
                terms = [t for t in ranking.tokenize(query) if len(t) > 2][:8]
                if terms:
                    rows += list(
                        (
                            await session.execute(
                                base.where(
                                    or_(*[ChunkRow.content.ilike(f"%{t}%") for t in terms])
                                ).limit(want)
                            )
                        ).all()
                    )
            else:
                rows = list((await session.execute(base.limit(max(want * 4, 500)))).all())

        seen: dict[str, tuple[Chunk, Document]] = {}
        for chunk_row, document_row in rows:
            if chunk_row.id not in seen:
                seen[chunk_row.id] = (_to_chunk(chunk_row), _to_document(document_row))

        if not seen:
            return []
        return _rank_to_citations(
            list(seen.values()),
            query=query,
            vector=vector,
            now=self._clock.now(),
            limit=limit,
            floor=min_score,
        )


def _to_document(row: DocumentRow) -> Document:
    return Document(
        id=row.id,
        title=row.title,
        source=row.source,
        kind=SourceKind(row.kind),
        scope=row.scope,
        metadata=dict(row.doc_metadata or {}),
        chunk_count=row.chunk_count,
        bytes=row.bytes,
        created_at=row.created_at,
        fingerprint=row.fingerprint or "",
    )


def _to_chunk(row: ChunkRow) -> Chunk:
    chunk = Chunk(
        id=row.id,
        document_id=row.document_id,
        content=row.content,
        locator=row.locator or "",
        position=row.position,
        tokens=row.tokens,
    )
    chunk.embedding = row.embedding
    return chunk
