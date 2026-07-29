"""Where a memory lands, and under which heading.

Every rule here is deterministic and needs no model. That is a deliberate
constraint rather than a limitation accepted reluctantly: if placement asked a
model where a fact belonged, the same fact would land in different notes on
different days, the vault's structure would drift, and no user could form a
mental model of where anything is. A filing system whose rules cannot be stated
in a sentence is a filing system nobody trusts.

The sentence is: **a memory goes to the note its first namespaced tag names,
or to its scope's area note; episodic memories additionally go to the day.**

Tags carry the placement because tagging is a decision the *writer* is in the
best position to make. An agent recording something about a project knows it is
about that project; a downstream classifier would be guessing at what the agent
already knew. So `project/northbound` files under `Projects/Northbound.md`, and
the tag namespaces are exactly the page types Phase 11 asked for.

Headings come from the memory's kind, so a note accumulates structure rather
than a single undifferentiated list. Someone opening `Projects/Northbound.md`
should see what was decided separately from what is merely true.
"""

from __future__ import annotations

from datetime import date

from jarvis.memory.models import Memory, MemoryKind
from jarvis.obsidian.vault import safe_name

# tag namespace → folder. These are the page types Phase 11 named, plus People,
# which every one of them ends up referring to.
FOLDERS: dict[str, str] = {
    "project": "Projects",
    "meeting": "Meetings",
    "research": "Research",
    "business": "Business",
    "person": "People",
    "topic": "Topics",
    "source": "Sources",
}

AREAS = "Areas"
JOURNAL = "Journal"

# Kinds that describe *when* something happened rather than *what is true*.
# These go to the day as well as to their topic, which is what makes the
# journal a record of the day rather than a second copy of the vault.
EPISODIC = frozenset(
    {MemoryKind.CONVERSATION, MemoryKind.EVENT, MemoryKind.DECISION, MemoryKind.MISTAKE}
)

HEADINGS: dict[MemoryKind, str] = {
    MemoryKind.DECISION: "Decisions",
    MemoryKind.GOAL: "Goals",
    MemoryKind.PREFERENCE: "Preferences",
    MemoryKind.MISTAKE: "What went wrong",
    MemoryKind.SUCCESS: "What worked",
    MemoryKind.PERSON: "People",
    MemoryKind.PROJECT: "Projects",
    MemoryKind.EVENT: "Events",
    MemoryKind.IDEA: "Ideas",
    MemoryKind.STYLE: "Voice",
    MemoryKind.CODE: "Code",
    MemoryKind.DOCUMENT: "Sources",
    MemoryKind.CONVERSATION: "Conversations",
    MemoryKind.FACT: "Facts",
}

# The `type:` property, so Obsidian's properties UI and Dataview can filter.
TYPES: dict[str, str] = {folder: namespace for namespace, folder in FOLDERS.items()}


def heading_for(kind: MemoryKind) -> str:
    return HEADINGS.get(kind, "Notes")


def journal_path(day: date) -> str:
    return f"{JOURNAL}/{day.isoformat()}.md"


def area_path(scope: str) -> str:
    """The default home for a scope with no namespaced tag.

    A mode namespaces scopes as `business:sales`, and that colon is illegal in
    a filename on Windows and reserved by Obsidian, so it becomes a folder
    separator — which also gives the vault the nesting the scope implied.
    """
    parts = [safe_name(part, fallback="general") for part in scope.split(":") if part.strip()]
    return f"{AREAS}/{'/'.join(parts) or 'general'}.md"


def note_for(memory: Memory) -> str:
    """The note this memory belongs in."""
    for tag in memory.tags:
        namespace, separator, name = tag.partition("/")
        if separator and (folder := FOLDERS.get(namespace.lower().strip())):
            return f"{folder}/{safe_name(name)}.md"
    return area_path(memory.scope)


def title_for(path: str) -> str:
    """The `[[wikilink]]` name for a note, which is its filename without the
    extension. Obsidian resolves links by basename across the whole vault, so
    the folder is deliberately not part of it."""
    return path.rsplit("/", 1)[-1].removesuffix(".md")


def type_for(path: str) -> str:
    folder = path.split("/", 1)[0]
    if folder == JOURNAL:
        return "journal"
    if folder == AREAS:
        return "area"
    return TYPES.get(folder, "note")


def is_journal(path: str) -> bool:
    return path.startswith(f"{JOURNAL}/")
