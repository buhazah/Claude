"""Keeping a vault and a store in step, and leaving knowledge behind.

Two jobs that turn out to be one.

**Mirroring.** When the vault is not the primary store — a deployment on
Postgres that also wants a readable vault — the synchroniser subscribes to
`memory.written` and writes each memory through. It is a bus subscriber rather
than a wrapper around the store, so nothing on the request path waits for a
file write, and a vault on a slow network drive cannot make an agent turn slow.

**Reconciling.** The user edits notes in Obsidian. Those edits are the truth —
that is the premise of the whole integration — so a rescan reads the vault and
writes differences back into the primary store. The conflict rule is a single
sentence and it is not negotiable: **the vault wins.** A memory system the user
cannot correct by hand is worse than no memory system, and any rule that
sometimes overwrites their correction is that system.

The consequence is that mirroring is *lossy in one direction on purpose*. If
Jarvis wrote a fact, the user rewrote it, and Jarvis writes it again, the
user's wording survives — because `upsert_block` matches on normalised text and
finds their line rather than appending a second copy.

**Leaving knowledge behind.** `record_completion` is the other half of "every
completed task should leave behind useful knowledge inside the vault". A run
that finished produces a journal line and, where the run named a project, a
line on that project's page. Deliberately not a summary of the transcript: a
vault filling with model prose about what a model did is noise that makes the
useful notes harder to find. What gets written is what happened, when, and
where to look.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict, dataclass

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.memory.models import MemoryKind
from jarvis.memory.store import MemoryStore
from jarvis.obsidian import naming
from jarvis.obsidian.index import KnowledgeIndexer, VaultIndex
from jarvis.obsidian.store import ObsidianStore
from jarvis.obsidian.vault import VaultManager

log = structlog.get_logger(__name__)

# Marks a primary-store memory as a copy of a vault block, and names which one.
# The link has to live in a persisted field, or a restart orphans every mirrored
# memory and the next pull imports the whole vault a second time.
PROVENANCE = "vault:"


@dataclass(frozen=True, slots=True)
class SyncReport:
    scanned: int = 0
    imported: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def changed(self) -> int:
        return self.imported + self.updated


class MemorySynchronizer:
    """Mirrors a primary store into a vault, and reconciles edits back."""

    def __init__(
        self,
        *,
        vault: ObsidianStore,
        primary: MemoryStore | None = None,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._vault = vault
        self._primary = primary
        self._bus = bus
        self._clock = clock
        self._task: asyncio.Task[None] | None = None
        # Ids this synchroniser wrote, so its own mirror-writes do not come
        # back round the bus and get written a second time.
        self._echoes: set[str] = set()

    @property
    def vault_manager(self) -> VaultManager:
        """The directory itself, for callers that need to index or inspect it."""
        return self._vault.manager

    def index(self) -> VaultIndex:
        """The vault read as a graph.

        Here rather than left to the caller because the caller is the API
        layer, and the API layer importing `jarvis.obsidian` would run the
        dependency backwards — the composition root is the only part of Jarvis
        allowed to know this adapter exists, and it already handed this object
        over.
        """
        return KnowledgeIndexer(self.vault_manager, clock=self._clock).build()

    def forget_cache(self) -> None:
        """Drop the read cache before a pull, so a sync client's changes are
        seen even when they landed with an unchanged mtime and size."""
        self._vault.manager.forget_cache()

    # ── Mirroring ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Follow `memory.written` and mirror into the vault."""
        if self._bus is None or self._task is not None:
            return
        subscription = self._bus.subscribe("memory.written")

        async def follow() -> None:
            async for event in subscription.events():
                payload = event.payload
                memory_id = str(payload.get("id", ""))
                if memory_id in self._echoes or payload.get("note"):
                    # `note` in the payload means the vault store published it,
                    # so it is already on disk.
                    self._echoes.discard(memory_id)
                    continue
                await self._mirror(memory_id)

        self._task = asyncio.create_task(follow())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _mirror(self, memory_id: str) -> None:
        if self._primary is None:
            return
        memory = await self._primary.get(memory_id)
        if memory is None:
            return
        try:
            written = await self._vault.remember(
                memory.content,
                kind=memory.kind,
                scope=memory.scope,
                tags=memory.tags,
                source=memory.source,
                salience=memory.salience,
            )
            self._echoes.add(written.id)
        except Exception as exc:
            # A vault on a disconnected network drive must not take the kernel
            # with it. The memory is already in the primary store; the mirror
            # catches up on the next full sync.
            log.warning("vault_mirror_failed", memory=memory_id, error=str(exc))

    # ── Reconciling ───────────────────────────────────────────────────────────

    async def pull(self) -> SyncReport:
        """Read the vault and write what changed back to the primary store.

        The two stores mint their own ids, so a vault memory and its primary
        counterpart never share one. Matching is therefore by **provenance**:
        an imported memory carries `source="vault:<block id>"`, which is a
        durable link that survives a restart because `source` is persisted.

        Matching on content instead would look simpler and would break on the
        one case that matters — the user rewriting a line — by treating their
        correction as a new memory and leaving the old one beside it.
        """
        if self._primary is None:
            return SyncReport()

        scanned = imported = updated = unchanged = 0
        existing = {
            memory.source: memory
            for memory in await self._primary.all(limit=10_000)
            if memory.source and memory.source.startswith(PROVENANCE)
        }
        for memory in await self._vault.all(limit=10_000):
            scanned += 1
            origin = f"{PROVENANCE}{memory.id}"
            current = existing.get(origin)
            if current is None:
                await self._primary.remember(
                    memory.content,
                    kind=memory.kind,
                    scope=memory.scope,
                    tags=memory.tags,
                    source=origin,
                    salience=memory.salience,
                )
                imported += 1
            elif current.content != memory.content:
                # The vault wins. Always.
                await self._primary.supersede(
                    current.id,
                    memory.content,
                    kind=memory.kind,
                    scope=memory.scope,
                    tags=memory.tags,
                    source=origin,
                    salience=memory.salience,
                )
                updated += 1
            else:
                unchanged += 1

        report = SyncReport(
            scanned=scanned, imported=imported, updated=updated, unchanged=unchanged
        )
        if self._bus and report.changed:
            self._bus.publish("memory.synced", {"imported": imported, "updated": updated})
        log.info("vault_pull", **asdict(report))
        return report

    # ── Leaving knowledge behind ──────────────────────────────────────────────

    async def record_completion(
        self,
        *,
        request: str,
        agent: str,
        outcome: str,
        run_id: str = "",
        project: str = "",
    ) -> None:
        """Write what a finished run leaves worth keeping.

        The outcome is truncated hard. A vault where every entry is six
        paragraphs of model output is a vault whose useful notes cannot be
        found, and the run record already holds the full transcript — this is a
        pointer to it, not a second copy of it.
        """
        summary = " ".join(outcome.split())[:280]
        tags = [f"project/{project}"] if project else []
        await self._vault.remember(
            f"{request.strip()[:160]} — {summary}" if summary else request.strip()[:160],
            kind=MemoryKind.EVENT,
            scope=agent,
            tags=tags,
            source=f"run:{run_id}" if run_id else "run",
        )

    async def daily_note(self) -> str:
        """The path of today's journal, created if it does not exist yet."""
        path = naming.journal_path(self._clock.now().date())
        note = self._vault._vault.read(path)
        note.path = path
        if not note.properties:
            today = self._clock.now().date()
            note.properties = {"title": today.isoformat(), "type": "journal", "created": today}
            self._vault._vault.write(note)
        return path
