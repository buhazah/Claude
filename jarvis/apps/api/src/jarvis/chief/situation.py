"""Everything the detectors read, gathered once.

Detectors are pure synchronous functions over this snapshot. That split is
worth the extra type: it means a detector can be tested by constructing a
`Situation` literal rather than by building a kernel, and it means the whole
sweep does its I/O in one predictable batch instead of each signal quietly
issuing its own queries.

It also makes the failure mode right. A vault on a disconnected drive, a
database mid-restart, a workflow store that raises — none of those should stop
Jarvis from telling you about the approval that has been waiting since Tuesday.
So gathering is per-source and best-effort: a source that fails contributes
nothing and is *named* in `unavailable`, which the report shows, because a
recommendation list silently missing a third of its inputs is worse than one
that says what it could not see.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

log = structlog.get_logger(__name__)


@dataclass(slots=True)
class ProjectPage:
    """A vault note the Chief of Staff can be neglectful about."""

    path: str
    title: str
    updated: datetime | None = None
    memories: int = 0
    links: int = 0


@dataclass(slots=True)
class Situation:
    """A snapshot of everything worth having an opinion about."""

    now: datetime
    approvals: list[Any] = field(default_factory=list)
    runs: list[Any] = field(default_factory=list)
    workflow_runs: list[Any] = field(default_factory=list)
    memories: list[Any] = field(default_factory=list)
    projects: list[ProjectPage] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    unlinked: list[tuple[str, str]] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    # Sources that could not be read. Named rather than swallowed.
    unavailable: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.unavailable


async def gather(jarvis: Any, *, memory_limit: int = 500) -> Situation:
    """Read every source, tolerating any of them being absent or broken."""
    now: datetime = jarvis.clock.now() if hasattr(jarvis, "clock") else datetime.now(UTC)
    situation = Situation(now=now)

    async def source(name: str, read: Any) -> Any:
        try:
            return await read()
        except Exception as exc:
            log.warning("situation_source_failed", source=name, error=str(exc))
            situation.unavailable.append(name)
            return None

    situation.approvals = list(jarvis.approvals.pending())

    if (runs := await source("runs", lambda: jarvis.runs.list(limit=200))) is not None:
        situation.runs = list(runs)

    if (
        workflows := await source("workflows", lambda: jarvis.workflows.runs(limit=200))
    ) is not None:
        situation.workflow_runs = list(workflows)

    if (
        memories := await source("memory", lambda: jarvis.memory.all(limit=memory_limit))
    ) is not None:
        situation.memories = list(memories)

    situation.budget = jarvis.governor.snapshot()

    if jarvis.obsidian is not None:
        index = await source("vault", _as_async(jarvis.obsidian.index))
        if index is not None:
            situation.projects = [
                ProjectPage(
                    path=note.path,
                    title=note.title,
                    updated=_as_datetime(note.updated),
                    memories=note.blocks,
                    links=len(note.links_in) + len(note.links_out),
                )
                for note in index.notes.values()
                if note.type in ("project", "business", "research")
            ]
            situation.orphans = [note.path for note in index.orphans()]
            situation.unlinked = list(index.unlinked_mentions())

    return situation


def _as_async(fn: Any) -> Any:
    async def call() -> Any:
        return fn()

    return call


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)
