"""An Obsidian vault behind the `MemoryStore` port.

This is the whole of the integration's coupling: one class satisfying the same
protocol as `InMemoryStore` and `SqlMemoryStore`, importing from `jarvis.memory`
and nothing importing it back. Jarvis core has no idea Obsidian exists; only the
composition root does, which is the one place allowed to know about adapters.

Two properties matter more than anything else here.

**Recall order does not change.** Scoring is `jarvis.memory.ranking`, byte for
byte the same code the other two stores use. Stores differ only in how they
*fetch candidates*; ranking semantics are part of the product, not of the
backend. A vault that recalled things in a different order from a database
would make "why did Jarvis remember that?" have two answers.

**Files are the truth, not a projection of it.** There is no shadow database.
A memory *is* a line in a note, its metadata *is* the note's frontmatter, and a
memory the user deleted in Obsidian is gone the next time the note is read.
The alternative — a database with the vault as an export — would be easier and
would be a lie: the first time the two disagreed, the user's own edits would
lose, and a memory system the user cannot correct by hand is worse than no
memory system.

The cost of that choice is honest and worth stating: recall reads every note in
the vault. For a personal vault — thousands of notes, not millions — that is a
few milliseconds against a warm cache, and it buys a system with exactly one
copy of the truth. If a vault ever outgrows it, the fix is an index beside the
files, not a database in front of them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.ids import new_id
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
from jarvis.obsidian import naming
from jarvis.obsidian.links import Linker
from jarvis.obsidian.note import Note
from jarvis.obsidian.vault import VaultManager

log = structlog.get_logger(__name__)


class ObsidianStore:
    """A vault of markdown notes, presented as memory."""

    def __init__(
        self,
        vault: VaultManager,
        *,
        embedder: Embedder | None = None,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
        link: bool = True,
    ) -> None:
        self._vault = vault
        self._embedder = embedder or HashingEmbedder()
        self._bus = bus
        self._clock = clock
        self._linker = Linker(vault) if link else None
        # Embeddings keyed by the exact text they were computed for, so a note
        # the user has not touched costs nothing to re-embed and an edited line
        # is re-embedded automatically.
        self._vectors: dict[str, list[float]] = {}
        vault.ensure()

    @property
    def manager(self) -> VaultManager:
        """The directory. Exposed so the indexer and the API can read it
        without reaching through this class into a private attribute."""
        return self._vault

    # ── Reading the vault as memories ─────────────────────────────────────────

    def _memories_in(self, note: Note) -> list[Memory]:
        """Every memory a note currently holds.

        Content comes from the body and metadata from the frontmatter, and when
        they disagree the body wins — that is the rule that makes a hand-edited
        note correct rather than corrupt.
        """
        if orphaned := note.prune():
            log.debug("vault_blocks_deleted_by_hand", path=note.path, count=len(orphaned))

        memories: list[Memory] = []
        for block in note.anchored():
            meta = note.blocks.get(block.memory_id, {})
            kind = _kind(meta.get("kind"), block.text)
            memories.append(
                Memory(
                    id=block.memory_id,
                    content=block.text,
                    kind=kind,
                    tier=tier_for(kind),
                    scope=str(meta.get("scope", "global")),
                    tags=list(meta.get("tags", [])),
                    source=meta.get("source"),
                    salience=float(meta.get("salience", salience_for(kind, block.text))),
                    created_at=_when(meta.get("created")),
                    last_accessed_at=_when(meta.get("accessed")),
                    access_count=int(meta.get("access_count", 0)),
                )
            )
        return memories

    def _all_notes(self) -> list[tuple[Note, list[Memory]]]:
        loaded = []
        for path in self._vault.notes():
            note = self._vault.read_path(path)
            if memories := self._memories_in(note):
                loaded.append((note, memories))
        return loaded

    async def _embed(self, texts: list[str]) -> None:
        """Fill the vector cache for anything new. One batched call."""
        missing = [text for text in dict.fromkeys(texts) if text not in self._vectors]
        if not missing:
            return
        vectors = await self._embedder.embed(missing)
        self._vectors.update(zip(missing, vectors, strict=True))

    # ── MemoryStore ───────────────────────────────────────────────────────────

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
        # One memory is one line, because one memory is one Obsidian block and
        # a block reference anchors a line. The runtime's own conversation
        # memory is two lines ("Asked: …\nAnswered: …"), so without this the
        # first thing the vault ever stored would have put the anchor on the
        # second line and orphaned the first — silently, and only visible as
        # recall returning half a sentence.
        content = " ".join(content.split())
        if not content:
            raise ValueError("cannot remember empty content")

        resolved = kind or categorize(content)
        memory = Memory(
            id=new_id("mem"),
            content=content,
            kind=resolved,
            tier=tier_for(resolved),
            scope=scope,
            tags=list(tags or []),
            source=source,
            salience=salience if salience is not None else salience_for(resolved, content),
            created_at=self._clock.now(),
        )

        path = naming.note_for(memory)
        note = self._vault.read(path)
        note.path = path
        linked = self._linker.link(content, exclude=path) if self._linker else content

        appended = note.upsert_block(memory.id, linked, naming.heading_for(memory.kind))
        if appended:
            note.blocks[memory.id] = _meta(memory)
        _stamp(note, path, memory, self._clock.now())
        self._vault.write(note)

        if self._linker:
            self._linker.relate(path, linked)
        if memory.kind in naming.EPISODIC:
            self._journal(memory, path)

        if self._bus:
            self._bus.publish(
                "memory.written",
                {
                    "id": memory.id,
                    "kind": memory.kind.value,
                    "scope": memory.scope,
                    "salience": memory.salience,
                    "preview": content[:120],
                    "note": path,
                },
            )
        return memory

    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        scope: str | None = None,
        kinds: list[MemoryKind] | None = None,
        min_score: float = 0.05,
    ) -> list[Recall]:
        candidates = [
            memory
            for _, memories in self._all_notes()
            for memory in memories
            # An agent sees its own scope plus anything global — the same rule
            # every other store applies, because it is a product rule and not a
            # storage one.
            if (scope is None or memory.scope in (scope, "global"))
            and (not kinds or memory.kind in kinds)
        ]
        if not candidates:
            return []

        await self._embed([memory.content for memory in candidates] + [query])
        for memory in candidates:
            memory.embedding = self._vectors.get(memory.content)

        recalls = ranking.rank(
            candidates,
            query=query,
            query_vector=self._vectors.get(query, []),
            now=self._clock.now(),
            limit=limit,
            min_score=min_score,
        )
        if self._bus:
            self._bus.publish("memory.recalled", {"query": query[:120], "hits": len(recalls)})
        return recalls

    async def get(self, memory_id: str) -> Memory | None:
        for _, memories in self._all_notes():
            for memory in memories:
                if memory.id == memory_id:
                    return memory
        return None

    async def forget(self, memory_id: str) -> bool:
        for note, memories in self._all_notes():
            if not any(memory.id == memory_id for memory in memories):
                continue
            if note.remove_block(memory_id):
                self._vault.write(note)
                if self._bus:
                    self._bus.publish("memory.forgotten", {"id": memory_id, "note": note.path})
                return True
        return False

    async def all(
        self, *, scope: str | None = None, kind: MemoryKind | None = None, limit: int = 200
    ) -> list[Memory]:
        items = [
            memory
            for _, memories in self._all_notes()
            for memory in memories
            if (scope is None or memory.scope == scope) and (kind is None or memory.kind == kind)
        ]
        items.sort(
            key=lambda m: (m.created_at or datetime.min.replace(tzinfo=UTC), m.id), reverse=True
        )
        return items[:limit]

    async def count(self) -> int:
        return sum(len(memories) for _, memories in self._all_notes())

    async def supersede(self, old_id: str, new_content: str, **kwargs: object) -> Memory:
        """Replace a stale memory.

        Unlike the other stores, the old text is not kept as a tombstone. In a
        file the user reads, a superseded line is clutter that has to be
        explained — and the vault is under version control or a sync client
        with history, which is a better place for "what did this used to say"
        than a note nobody wanted to see.
        """
        replacement = await self.remember(new_content, **kwargs)  # type: ignore[arg-type]
        await self.forget(old_id)
        return replacement

    # ── The journal ───────────────────────────────────────────────────────────

    def _journal(self, memory: Memory, origin: str) -> None:
        """Record that this happened today, pointing at where it lives.

        A line rather than a copy. Two copies of a fact drift, and the one the
        user corrects is never the one recall reads. So the journal is an index
        of the day — what happened, and where the detail is — which is also
        what makes it readable a year later.
        """
        today: date = self._clock.now().date()
        path = naming.journal_path(today)
        note = self._vault.read(path)
        note.path = path
        title = naming.title_for(origin)
        pointer = f"{memory.content} → [[{title}]]" if origin != path else memory.content
        note.upsert_block(f"{memory.id}-j", pointer, naming.heading_for(memory.kind))
        note.properties.setdefault("title", today.isoformat())
        note.properties["type"] = "journal"
        note.properties["created"] = today
        note.properties["updated"] = today
        self._vault.write(note)


def _meta(memory: Memory) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "kind": memory.kind.value,
        "scope": memory.scope,
        "salience": memory.salience,
    }
    if memory.created_at:
        meta["created"] = memory.created_at.isoformat(timespec="seconds")
    if memory.tags:
        meta["tags"] = memory.tags
    if memory.source:
        meta["source"] = memory.source
    return meta


def _stamp(note: Note, path: str, memory: Memory, now: datetime) -> None:
    """Keep the readable frontmatter current without overwriting the user's."""
    note.properties.setdefault("title", naming.title_for(path))
    note.properties.setdefault("type", naming.type_for(path))
    note.properties.setdefault("created", now.date())
    note.properties["updated"] = now.date()

    existing = note.properties.get("tags") or []
    tags = list(existing) if isinstance(existing, list) else [str(existing)]
    for tag in memory.tags:
        if tag not in tags:
            tags.append(tag)
    if tags:
        note.properties["tags"] = tags


def _kind(raw: object, content: str) -> MemoryKind:
    """A kind from the frontmatter, or inferred if a human wrote the line."""
    try:
        return MemoryKind(str(raw))
    except ValueError:
        return categorize(content)


def _when(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
