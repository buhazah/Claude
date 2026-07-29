# Obsidian as long-term memory

Point Jarvis at a vault and its memory becomes markdown files you own.

```bash
export JARVIS_OBSIDIAN_VAULT=~/Documents/Vault
```

That is the whole setup. Nothing else changes: the same recall, the same
scoping, the same events — the files simply *are* the memory now, rather than
rows in a database somewhere.

## The one rule

**When your edit and Jarvis's record disagree, you are right.**

Open a note, fix a number, delete a line you did not want kept. Jarvis reads
what is there now. There is no shadow database to overwrite you on the next
sync, because there is no shadow database.

That rule is why this is Obsidian rather than a markdown *export*. An export
looks the same until the first time you correct something, and then it is
confidently wrong and immune to being told so.

## What the vault looks like

```
Vault/
├── Projects/Northbound.md
├── People/Alison.md
├── Meetings/Q3 planning.md
├── Research/Oat milk market.md
├── Business/Pricing.md
├── Areas/business/sales.md          ← memories with no topic tag
└── Journal/2026-07-29.md            ← what happened today
```

A note:

```markdown
---
title: Northbound
type: project
tags: [project/Northbound]
created: 2026-07-01
updated: 2026-07-29
related: ["[[Alison]]"]
jarvis: {"v":1,"blocks":{"mem_01j9x":{"kind":"decision","scope":"business","salience":0.85}}}
---

## Decisions

- Stopped taking consulting work this year ^mem-01j9x

## Facts

- Gross margin is 62% ^mem-01j9y

## Related

- [[Alison]]
```

Each `^mem-…` is one memory. They are Obsidian block references, so you can
link to a single fact from anywhere: `[[Northbound#^mem-01j9y]]`.

The body is yours. Rewrite it, reorder it, add your own prose between the
bullets — Jarvis reads the anchored lines and leaves the rest alone. The
`jarvis:` line is metadata you never have to look at, and **any frontmatter
Jarvis does not recognise is preserved untouched**, so Templater configs,
Dataview fields and plugin settings survive.

## Where things land

One sentence: **a memory goes to the note its first namespaced tag names, or
to its scope's area note; things that happened also get a line in the day.**

| tag | note |
|---|---|
| `project/Northbound` | `Projects/Northbound.md` |
| `person/Alison` | `People/Alison.md` |
| `meeting/Q3 planning` | `Meetings/Q3 planning.md` |
| `research/Oat milk market` | `Research/Oat milk market.md` |
| `business/Pricing` | `Business/Pricing.md` |
| *(none)* | `Areas/<scope>.md` |

No model decides this. If it did, the same fact would land somewhere different
each day and you could never build a mental model of where anything is.

Headings come from the memory's kind, so opening a project page shows what was
*decided* separately from what is merely true.

## The journal

Conversations, events, decisions and mistakes get a dated line pointing at
where the detail lives:

```markdown
## Decisions

- Dropped the subscription tier → [[Northbound]] ^mem-01j9x-j
```

A pointer, not a copy. Two copies drift, and the one you correct is never the
one recall reads.

**Every completed task leaves something here.** Not because of a special hook —
the runtime has written a memory after every run since M1, and pointing memory
at a vault is all it takes for those to become notes.

## Links

Jarvis wraps note titles it recognises in `[[wikilinks]]` as it writes, and
maintains a `## Related` section.

Deliberately literal: exact title, case-sensitive, word boundaries, nothing
under four characters. A linker that connects "Ali" to "Alignment" builds a
graph that looks impressive and means nothing — and every wrong link is a
wrong retrieval later. A missing link costs you one keystroke.

Backlinks are Obsidian's own; writing them by hand would be a second copy of
state the app already maintains.

## Seeing the shape of what you know

```bash
curl localhost:8000/v1/vault
```

```json
{
  "notes": 143, "memories": 892,
  "orphans": ["Projects/Half-started idea.md"],
  "cold": [{"path": "Projects/Northbound.md", "updated": "2026-05-02"}],
  "unlinked_mentions": [["Meetings/Q3 planning.md", "Alison"]],
  "busiest": [{"path": "Projects/Northbound.md", "memories": 61}]
}
```

Recall answers "what do I know about X". This answers the questions recall
cannot, because they are about the *shape* of what you know: what has gone
cold, what is connected to nothing, which links Jarvis should have made and
did not. It is what makes proactive work possible — a system that only reads
recall can tell you about things you asked about; one that reads the graph can
tell you about the project you have not touched in five weeks.

## After you have been editing

```bash
curl -X POST localhost:8000/v1/vault/sync
```

Runs on start too. Exposed because the interesting moment is right after you
finish editing, and waiting for a restart to be believed is not a memory system
anybody trusts.

## Mirroring instead of owning

If you already run on Postgres and want a readable vault alongside it:

```bash
export JARVIS_OBSIDIAN_VAULT=~/Documents/Vault
export JARVIS_OBSIDIAN_PRIMARY=false
```

The database stays authoritative for writes; the vault gets a copy. Mirroring
follows the event bus rather than wrapping the store, so nothing waits on a
file write and a vault on a disconnected drive is a degraded mirror, not an
outage.

Your edits still win. A sync reads the vault and supersedes the database record
— matched by provenance (`source="vault:<block id>"`), which survives restarts
because it is a persisted field.

## Safety

- **No path escapes the vault.** Note names come from tags, which come from
  agents, which read untrusted documents. Every path is resolved and required
  to sit under the root — symlinks included, since a link planted inside the
  vault pointing out is the interesting attack.
- **No write half-happens.** Temp file plus atomic replace. Vaults live in
  iCloud and Dropbox, and those will happily propagate a half-written note to
  every other device before the rest arrives.
- **An identical write touches nothing.** Every write wakes a sync client and
  adds a version to your file history.
- **Scoping is unchanged.** A mode narrows which memories an agent can read,
  and that holds here exactly as it does elsewhere — `Areas/business/sales.md`
  is not readable from personal mode.

## Turning it off

Unset the variable. Jarvis remembers into whichever store the database switch
selects, the vault stays on disk exactly as it is, and nothing in the kernel
notices — `jarvis/obsidian/` is an adapter behind the `MemoryStore` port, and a
test walks every module's imports to prove nothing in core reaches for it.

See [ADR 0013](adr/0013-the-files-are-the-memory.md) for why it is built this
way.
