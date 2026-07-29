"""Obsidian as Jarvis's long-term memory.

The dependency runs one way and only one way: this package imports from
`jarvis.memory`, and nothing in `jarvis` imports from here except the
composition root, which is the one place allowed to know which adapters exist.
Delete this directory and the kernel still builds, still runs, and still
remembers — into whichever store the container wires instead.

What lives here:

| module | what it owns |
|---|---|
| `note` | the file format — frontmatter, blocks, round-tripping |
| `vault` | the directory — safe paths, atomic writes, the read cache |
| `naming` | where a memory lands and under which heading |
| `links` | wikilinks and the `Related` section |
| `store` | `ObsidianStore`, satisfying the `MemoryStore` port |
| `index` | the vault read as a graph: tags, links, orphans, stale notes |
| `sync` | mirroring, reconciling, and what a finished run leaves behind |

The premise all of it rests on: **the files are the truth.** Not a projection
of a database, not an export. A memory is a line in a note the user can edit,
and when their edit and Jarvis's record disagree, theirs is correct.
"""

from __future__ import annotations

from jarvis.obsidian.index import KnowledgeIndexer, VaultIndex
from jarvis.obsidian.links import Linker
from jarvis.obsidian.store import ObsidianStore
from jarvis.obsidian.sync import MemorySynchronizer, SyncReport
from jarvis.obsidian.vault import VaultManager

__all__ = [
    "KnowledgeIndexer",
    "Linker",
    "MemorySynchronizer",
    "ObsidianStore",
    "SyncReport",
    "VaultIndex",
    "VaultManager",
]
