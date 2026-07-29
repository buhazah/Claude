# 13. The files are the memory

Date: Phase 11, M11.4
Status: accepted

## Context

Jarvis needed long-term memory that outlives a conversation, a process and —
eventually — Jarvis itself. Obsidian is the obvious host: a vault is a folder
of markdown files, the user already has one, and it syncs, versions and
searches without anybody building any of that.

The interesting question was not "how do we write markdown". It was **which
copy is the truth** when the user edits a note.

Three options, and the difference between them is the whole design:

1. **A database with a markdown exporter.** Easy. The store stays what it is
   and a background job writes a readable mirror.
2. **Files as truth, with a cache.** The vault *is* the store. Reads parse
   markdown; writes rewrite it.
3. **Two-way sync with conflict resolution.** Both are authoritative, with
   timestamps and merge rules.

## Decision

**Option 2. A memory is a line in a note, and when the user's edit and
Jarvis's record disagree, the user is right.**

Option 1 fails on the first disagreement. The user opens
`Projects/Northbound.md`, sees "gross margin is 62%", knows it is 71%, fixes
it — and the next export overwrites their correction, because the database
never heard about it. A memory system you cannot correct by hand is worse than
no memory system: it is confidently wrong and immune to being told so.

Option 3 fails more slowly and more expensively. Every conflict rule that is
not "the human wins" eventually overwrites a human, and the machinery to
decide which side is newer is a second source of bugs on the path that matters
most.

So: `ObsidianStore` implements the existing `MemoryStore` protocol. There is
no shadow database. `search` reads the vault, `remember` writes a line,
`forget` deletes one, and a line the user deleted in Obsidian is gone the next
time the note is read.

### The format follows from the same rule

**The body belongs to the user. The frontmatter belongs to Jarvis.**

Nothing Jarvis needs may live in the prose, because the prose will be
rewritten by somebody who was not thinking about a data model. Nothing the
user has to look at may be machine noise, because a note full of inline
metadata is a note nobody opens.

- A memory is an Obsidian **block reference** — `^mem-01j9x` at the end of a
  line. Native, survives the line being moved, linkable by hand.
- Readable keys (`title`, `type`, `tags`, `created`, `updated`, `related`) are
  plain YAML, because Obsidian's properties UI, Dataview and the graph view
  read them.
- Per-block metadata is one line of JSON under `jarvis:`. YAML is a superset
  of JSON, so Obsidian parses it and Python round-trips it exactly.
- **Every frontmatter line Jarvis does not recognise is preserved verbatim.**
  A vault has plugins; breaking their config is breaking the user's tools.

That last point is also why there is no YAML dependency. A general library
would be a heavier commitment than the format needs and — worse — a full
parse-and-reserialise loses comments and reorders keys, which mangles a file
somebody has been editing.

### Placement is deterministic

A memory goes to the note its first namespaced tag names (`project/northbound`
→ `Projects/Northbound.md`), or to its scope's area note; episodic kinds
additionally get a line in the day's journal.

No model is consulted. If placement asked one, the same fact would land in
different notes on different days, the structure would drift, and no user could
form a mental model of where anything is. A filing system whose rules cannot be
stated in a sentence is one nobody trusts.

Tags carry the decision because the *writer* is best placed to make it: an
agent recording something about a project already knows it is about that
project, and a downstream classifier would be guessing at what the agent knew.

### Linking is precise, not clever

Only exact title matches, case-sensitively, at word boundaries, and never for
titles under four characters. Obsidian derives backlinks itself, so Jarvis
writes the outgoing links and maintains a `## Related` section for legibility
outside Obsidian.

A fuzzy linker that connects "Ali" to "Alignment" produces a graph that looks
impressive and means nothing, and every wrong link is a wrong retrieval later.
A missing link costs one keystroke; a wrong one costs trust in the graph.

## Consequences

**Recall reads every note.** For a personal vault — thousands of notes, not
millions — that is a few milliseconds against a warm cache, and it buys a
system with exactly one copy of the truth. If a vault outgrows it, the fix is
an index *beside* the files, not a database in front of them.

**Ranking does not change.** Scoring is `jarvis.memory.ranking`, byte for byte
the code the other two stores use. Stores differ only in how they fetch
candidates; ranking semantics are part of the product.

**Every completed run already leaves knowledge behind.** The runtime has
written a memory after every run since M1. Pointing memory at a vault is all it
took for those to become notes — no hook, no second path. That is the payoff of
implementing the port rather than bolting a vault on the side.

**One memory is one line.** Block references anchor lines, so content is
flattened on write. The runtime's own conversation memory is two lines, which
means the very first thing a vault ever stored would otherwise have orphaned
half of itself — silently, visible only as recall returning half a sentence.

**The dependency runs one way, and a test says so.** `jarvis.obsidian` imports
from `jarvis.memory`; nothing in `jarvis` imports it back except the
composition root. `test_the_kernel_does_not_import_obsidian` walks the AST of
every module and fails on a violation — which it did, on the first run, catching
the API layer reaching for the indexer directly. Delete the package and the
kernel still builds, still runs, and still remembers.

**Mirroring is a bus subscriber, not a wrapper.** When the vault is not the
primary store, `memory.written` drives the mirror, so nothing on the request
path waits on a file write and a vault on a disconnected network drive is a
degraded mirror rather than an outage.

**Reconciliation is by provenance, not by content.** The two stores mint their
own ids, so an imported memory carries `source="vault:<block id>"` — a durable
link, because `source` is persisted. Matching on content would look simpler and
would break on the one case that matters: the user rewriting a line, treated as
a new memory with the old one left beside it.
