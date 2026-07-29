"""The vault read as a graph, so Jarvis can see what it has and what it lacks.

Recall answers "what do I know about X". This module answers the questions
recall cannot, because they are about the *shape* of what is known rather than
its content:

* Which notes has nothing linked to in months — the knowledge that is there and
  effectively lost.
* Which are orphans, connected to nothing, which usually means a tag was
  misspelled or a note was created and abandoned.
* Which topics are dense, which is where the user's actual attention has been.
* Which notes mention each other without linking — the connections Jarvis
  should have made and did not.

This is what makes the Chief of Staff possible (M11.5). A recommendation engine
that only reads recall can tell you about the things you asked about; one that
reads the graph can tell you about the project you have not touched in five
weeks, which is the thing you actually needed to hear.

The index is built on demand and is not cached beyond the vault manager's own
per-file cache. It walks the whole vault, which for a personal vault is
milliseconds, and the alternative — an incrementally maintained index — would
be a second copy of the truth that can disagree with the files. The whole
integration exists to avoid exactly that.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.obsidian import naming
from jarvis.obsidian.note import Note
from jarvis.obsidian.vault import VaultManager

# A note untouched for longer than this is "cold". Six weeks, because that is
# roughly when a project stops being paused and starts being abandoned without
# anybody deciding it was.
COLD_AFTER = timedelta(days=42)


@dataclass(slots=True)
class NoteSummary:
    path: str
    title: str
    type: str
    blocks: int = 0
    links_out: list[str] = field(default_factory=list)
    links_in: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    updated: date | None = None
    # The prose, kept so `unlinked_mentions` does not force a second full read
    # of the vault. Not part of the summary's meaning — hence the underscore.
    body: str = ""

    @property
    def is_orphan(self) -> bool:
        return not self.links_in and not self.links_out


@dataclass(slots=True)
class VaultIndex:
    """One pass over the vault, in a shape other subsystems can question."""

    notes: dict[str, NoteSummary] = field(default_factory=dict)
    backlinks: dict[str, list[str]] = field(default_factory=dict)
    tags: Counter[str] = field(default_factory=Counter)
    total_blocks: int = 0

    def by_type(self, note_type: str) -> list[NoteSummary]:
        return sorted(
            (n for n in self.notes.values() if n.type == note_type),
            key=lambda n: n.updated or date.min,
            reverse=True,
        )

    def orphans(self) -> list[NoteSummary]:
        """Connected to nothing. Usually a misspelled tag or an abandoned page."""
        return sorted(
            (n for n in self.notes.values() if n.is_orphan and not naming.is_journal(n.path)),
            key=lambda n: n.path,
        )

    def cold(self, *, now: datetime, older_than: timedelta = COLD_AFTER) -> list[NoteSummary]:
        """Notes nothing has touched in a while, oldest first.

        Journals are excluded: a journal entry is *supposed* to stop changing
        the day after it is written, and listing every past day as neglected
        would bury the one project that genuinely is.
        """
        cutoff = (now - older_than).date()
        stale = [
            note
            for note in self.notes.values()
            if not naming.is_journal(note.path) and note.updated and note.updated < cutoff
        ]
        return sorted(stale, key=lambda n: n.updated or date.min)

    def busiest(self, limit: int = 10) -> list[NoteSummary]:
        return sorted(self.notes.values(), key=lambda n: n.blocks, reverse=True)[:limit]

    def unlinked_mentions(self) -> list[tuple[str, str]]:
        """`(note, title)` pairs where the text names a note it does not link.

        The connections Jarvis should have made. Usually because the target
        note did not exist yet when the line was written, which is the common
        case and the reason this cannot be a one-shot job at write time.
        """
        found: list[tuple[str, str]] = []
        titles = {n.title for n in self.notes.values() if len(n.title) >= 4}
        for note in self.notes.values():
            if naming.is_journal(note.path):
                continue
            linked = set(note.links_out)
            for title in titles:
                if title == note.title or title in linked:
                    continue
                if title in note.body:
                    found.append((note.path, title))
        return sorted(found)


class KnowledgeIndexer:
    """Builds a `VaultIndex`. One pass, no state kept between calls."""

    def __init__(self, vault: VaultManager, *, clock: Clock = SYSTEM_CLOCK) -> None:
        self._vault = vault
        self._clock = clock

    def build(self) -> VaultIndex:
        index = VaultIndex()

        for path in self._vault.notes():
            relative = self._vault.relative(path)
            note = self._vault.read_path(path)
            summary = _summarise(relative, note)
            index.notes[summary.title] = summary
            index.total_blocks += summary.blocks
            index.tags.update(summary.tags)

        inbound: dict[str, list[str]] = defaultdict(list)
        for summary in index.notes.values():
            for target in summary.links_out:
                if target in index.notes:
                    inbound[target].append(summary.title)

        for title, sources in inbound.items():
            index.notes[title].links_in = sorted(sources)
        index.backlinks = {title: sorted(sources) for title, sources in inbound.items()}
        return index

    def stale_projects(self, *, older_than: timedelta = COLD_AFTER) -> list[NoteSummary]:
        """Project pages nothing has touched. The Chief of Staff's first input."""
        index = self.build()
        cold = {note.path for note in index.cold(now=self._clock.now(), older_than=older_than)}
        return [note for note in index.by_type("project") if note.path in cold]


def _summarise(relative: str, note: Note) -> NoteSummary:
    tags = note.properties.get("tags") or []
    updated = _as_date(note.properties.get("updated") or note.properties.get("created"))
    return NoteSummary(
        path=relative,
        title=naming.title_for(relative),
        type=str(note.properties.get("type") or naming.type_for(relative)),
        blocks=len(note.anchored()),
        links_out=note.links(),
        tags=[str(tag) for tag in (tags if isinstance(tags, list) else [tags])],
        updated=updated,
        body=note.body,
    )


def _as_date(raw: object) -> date | None:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)).replace(tzinfo=UTC).date()
    except ValueError:
        return None
