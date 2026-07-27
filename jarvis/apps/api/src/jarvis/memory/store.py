"""Memory store: the port, and the in-process implementation behind it.

Recall blends three signals rather than relying on vectors alone, because each
fails differently: lexical matching nails proper nouns and identifiers that
embeddings blur, semantic similarity catches paraphrase, and recency decay
keeps stale facts from outranking current ones. Salience then weights the
whole, so a recorded decision outranks small talk that happens to match.

The Postgres+pgvector adapter (M3) implements this same interface; the scoring
maths moves into SQL, the semantics do not change.
"""

from __future__ import annotations

import math
import re
from typing import Protocol

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.memory.embeddings import Embedder, HashingEmbedder, cosine
from jarvis.memory.models import (
    Memory,
    MemoryKind,
    Recall,
    categorize,
    salience_for,
    tier_for,
)

log = structlog.get_logger(__name__)

_WORD_RE = re.compile(r"[a-z0-9']+")
HALF_LIFE_DAYS = 45.0  # a memory's recency weight halves over this span


class MemoryStore(Protocol):
    async def remember(self, content: str, **kwargs: object) -> Memory: ...

    async def search(self, query: str, *, limit: int = 8) -> list[Recall]: ...

    async def get(self, memory_id: str) -> Memory | None: ...

    async def forget(self, memory_id: str) -> bool: ...


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
        self, *, scope: str | None = None, kind: MemoryKind | None = None
    ) -> list[Memory]:
        items = [
            m
            for m in self._items.values()
            if (scope is None or m.scope == scope)
            and (kind is None or m.kind == kind)
            and m.superseded_by is None
        ]
        items.sort(key=lambda m: m.created_at or self._clock.now(), reverse=True)
        return items

    def _lexical(self, query_tokens: set[str], memory: Memory) -> float:
        if not query_tokens:
            return 0.0
        haystack = set(_WORD_RE.findall(memory.content.lower())) | {t.lower() for t in memory.tags}
        overlap = query_tokens & haystack
        if not overlap:
            return 0.0
        # Normalised by query length: matching 3 of 4 query terms beats
        # matching 3 of 10, independent of how long the memory is.
        return len(overlap) / len(query_tokens)

    def _recency(self, memory: Memory) -> float:
        if not memory.created_at:
            return 0.5
        age_days = (self._clock.now() - memory.created_at).total_seconds() / 86_400
        return math.exp(-math.log(2) * max(age_days, 0.0) / HALF_LIFE_DAYS)

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        scope: str | None = None,
        kinds: list[MemoryKind] | None = None,
        min_score: float = 0.05,
    ) -> list[Recall]:
        """Hybrid recall: lexical + semantic + recency, weighted by salience."""
        if not self._items:
            return []

        query_vector = (await self._embedder.embed([query]))[0]
        query_tokens = set(_WORD_RE.findall(query.lower()))

        results: list[Recall] = []
        for memory in self._items.values():
            if memory.superseded_by is not None:
                continue
            if scope is not None and memory.scope not in (scope, "global"):
                continue
            if kinds and memory.kind not in kinds:
                continue

            lexical = self._lexical(query_tokens, memory)
            semantic = max(0.0, cosine(query_vector, memory.embedding or []))
            recency = self._recency(memory)
            relevance = 0.45 * lexical + 0.40 * semantic + 0.15 * recency
            score = relevance * (0.6 + 0.4 * memory.salience)

            if score >= min_score:
                results.append(
                    Recall(
                        memory=memory,
                        score=round(score, 6),
                        lexical=round(lexical, 4),
                        semantic=round(semantic, 4),
                        recency=round(recency, 4),
                    )
                )

        results.sort(key=lambda r: (-r.score, r.memory.id))
        top = results[:limit]
        for recall in top:
            recall.memory.touch(self._clock.now())
        if self._bus:
            self._bus.publish("memory.recalled", {"query": query[:120], "hits": len(top)})
        return top

    async def supersede(self, old_id: str, new_content: str, **kwargs: object) -> Memory:
        """Replace a stale memory, keeping the old one for audit."""
        replacement = await self.remember(new_content, **kwargs)  # type: ignore[arg-type]
        if old := self._items.get(old_id):
            old.superseded_by = replacement.id
        return replacement
