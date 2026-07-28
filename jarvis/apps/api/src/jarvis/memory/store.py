"""Memory store: the port, and the in-process implementation behind it.

Recall blends three signals rather than relying on vectors alone, because each
fails differently: lexical matching nails proper nouns and identifiers that
embeddings blur, semantic similarity catches paraphrase, and recency decay
keeps stale facts from outranking current ones. Salience then weights the
whole, so a recorded decision outranks small talk that happens to match.

That blend lives in ``jarvis.memory.ranking`` and is shared with the SQL store,
so recall order cannot depend on which backend happens to be deployed.
"""

from __future__ import annotations

from typing import Protocol

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.memory import ranking
from jarvis.memory.embeddings import Embedder, HashingEmbedder
from jarvis.memory.models import (
    Memory,
    MemoryKind,
    Recall,
    categorize,
    salience_for,
    tier_for,
)

log = structlog.get_logger(__name__)


class MemoryStore(Protocol):
    """What the runtime needs from memory, regardless of where it is stored.

    Spelled out in full rather than with ``**kwargs``: a loose protocol would
    type-check against a store missing half the arguments, and the whole point
    of the port is that the backends are interchangeable.
    """

    async def remember(
        self,
        content: str,
        *,
        kind: MemoryKind | None = None,
        scope: str = "global",
        tags: list[str] | None = None,
        source: str | None = None,
        salience: float | None = None,
    ) -> Memory: ...

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        scope: str | None = None,
        kinds: list[MemoryKind] | None = None,
        min_score: float = 0.05,
    ) -> list[Recall]: ...

    async def get(self, memory_id: str) -> Memory | None: ...

    async def forget(self, memory_id: str) -> bool: ...

    async def all(
        self, *, scope: str | None = None, kind: MemoryKind | None = None, limit: int = 200
    ) -> list[Memory]: ...

    async def count(self) -> int: ...

    async def supersede(self, old_id: str, new_content: str, **kwargs: object) -> Memory: ...


class InMemoryStore:
    """Reference implementation. Used in dev, tests, and fully-local mode."""

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._items: dict[str, Memory] = {}
        self._embedder = embedder or HashingEmbedder()
        self._bus = bus
        self._clock = clock

    def __len__(self) -> int:
        return len(self._items)

    async def count(self) -> int:
        return len(self._items)

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
        self._items[memory.id] = memory

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
        return self._items.get(memory_id)

    async def forget(self, memory_id: str) -> bool:
        removed = self._items.pop(memory_id, None) is not None
        if removed and self._bus:
            self._bus.publish("memory.forgotten", {"id": memory_id})
        return removed

    async def all(
        self, *, scope: str | None = None, kind: MemoryKind | None = None, limit: int = 200
    ) -> list[Memory]:
        items = [
            m
            for m in self._items.values()
            if (scope is None or m.scope == scope)
            and (kind is None or m.kind == kind)
            and m.superseded_by is None
        ]
        items.sort(key=lambda m: (m.created_at or self._clock.now(), m.id), reverse=True)
        return items[:limit]

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        scope: str | None = None,
        kinds: list[MemoryKind] | None = None,
        min_score: float = 0.05,
    ) -> list[Recall]:
        """Hybrid recall. Candidates are the whole store; ranking is shared."""
        if not self._items:
            return []

        query_vector = (await self._embedder.embed([query]))[0]
        candidates = [
            memory
            for memory in self._items.values()
            if memory.superseded_by is None
            # An agent sees its own scope plus anything global.
            and (scope is None or memory.scope in (scope, "global"))
            and (not kinds or memory.kind in kinds)
        ]

        recalls = ranking.rank(
            candidates,
            query=query,
            query_vector=query_vector,
            now=self._clock.now(),
            limit=limit,
            min_score=min_score,
        )
        for recall in recalls:
            recall.memory.touch(self._clock.now())
        if self._bus:
            self._bus.publish("memory.recalled", {"query": query[:120], "hits": len(recalls)})
        return recalls

    async def supersede(self, old_id: str, new_content: str, **kwargs: object) -> Memory:
        """Replace a stale memory, keeping the old one for audit."""
        replacement = await self.remember(new_content, **kwargs)  # type: ignore[arg-type]
        if old := self._items.get(old_id):
            old.superseded_by = replacement.id
        return replacement
