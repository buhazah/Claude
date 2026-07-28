# ADR 0010 — A mode only ever subtracts, and a document carries its sources

**Status:** accepted · M9 · extends ADR 0002, ADR 0006

## Context

**Modes.** The obvious way to ship "Business / Coding / Research mode" is a
preset: an accent colour, a system-prompt prefix, maybe a shortlist of
suggested prompts. That is a lie the UI tells. The same agents remain
reachable, the same tools stay in hand, the same memory answers — so the label
promises focus the system does not provide, and the user learns the switch
does not matter.

There is also a worse failure available. If a mode can *add* — grant a tool,
raise a permission, reach an agent the catalog does not have — then picking a
mode becomes a way to widen authority, which is the exact thing the permission
architecture (ADR 0005) exists to prevent. Any design where a mode is a bag of
grants has this hole in it by construction.

**Documents.** A generated document has to survive two things a chat answer
never does: being read by someone who was not there, and being checked. A blob
of markdown produced in one pass fails both — by section four the model has
forgotten what section two claimed, and nothing in the output says where any of
it came from. M5 made every retrieved passage carry a locator; a document that
drops that on the floor is a document whose claims cannot be traced.

## Decision

**A mode is a narrowing, applied at three seams, and it can only subtract.**

* **Routing.** Only the mode's agents are candidates. Coding mode cannot route
  to the life coach, however the words fall.
* **Reach.** An agent's tools are *intersected* with the mode's allowlist. A
  mode listing `wire_money` gets nothing, because the agent's spec does not
  have it.
* **Memory.** Reads and writes are namespaced, so what Jarvis learns about a
  client does not surface while drafting a personal message — and, mattering
  more, personal detail does not leak into client-facing work.

The mechanism is deliberately dull: **a mode produces a narrowed registry of
narrowed specs**, and everything downstream — orchestrator, runtime, tools,
memory — runs unchanged against it. The alternative, threading a mode id
through five call sites, means forgetting the sixth.

Supporting decisions:

* **An unknown mode is refused, not defaulted.** Falling back would fail
  *open*, because the default mode is the unconstrained one: a typo
  (`?mode=busines`) would silently hand back the whole catalog and the personal
  memory namespace when the caller asked to be narrowed.
* **Pinning an agent is checked against the mode's catalog**, not the system's.
  Otherwise `agent_id` is a way straight around the narrowing.
* **A briefing is context, never capability.** It is prepended to the system
  prompt and changes nothing about reach. A briefing that says "you may use any
  tool" still cannot produce one.
* **The mode's first listed agent is its lead**, because the registry falls
  back to its first agent when nothing matches — and who owns an unclassifiable
  request should be a decision, not whatever the catalog happened to list
  first.
* **Modes are published by the kernel** (`GET /v1/modes`), so the client cannot
  claim a constraint the kernel does not hold.

**A document is planned, then written, and carries its sources as data.**

* **Outline first.** Cheap, inspectable, and the point at which the user can
  say "no, not that shape" before the writing has been paid for.
* **Retrieval is per section.** The passages that matter for "Market position"
  are not the ones that matter for "Regulatory risk"; one search for the whole
  request produces sections citing sources they never used.
* **Citations are captured at write time**, from the passages the section was
  handed, and then filtered to the ones whose marker actually appears in the
  prose. Asking a model afterwards which sources it used produces a plausible
  answer, not a true one.

## Consequences

- `memory_scopes` on `AgentSpec` had been declared and never read since M1 —
  dead config. Modes make it real, and the runtime now resolves scope through
  the spec rather than hardcoding the agent id.
- The routing fallback had a hole: an unmatched request returned a hardcoded
  `chief_of_staff` regardless of which registry was asked, so an unmatched
  request in coding mode would have routed to an agent coding mode excludes.
  The fallback now comes from the registry it was asked of. Found by the test
  that asserts routing cannot escape a mode.
- Modes are presentation *and* enforcement, which means the mode list is one
  more thing to keep honest. `surfaces` and `accent` are carried as data so the
  client has one source of truth rather than a switch statement.
- **Attributable is not correct.** Passing a section the right passages makes
  its claims traceable; nothing verifies that a sentence is actually supported
  by the passage beside it. That is a research problem, and a green checkmark
  claiming otherwise would be worse than saying so plainly.
- Documents are in-memory behind a Protocol, like every store before them.
  A restart loses them; a SQL backend is a swap, not a redesign.
- No `.docx` export. Doing it honestly means a real OOXML writer, and a
  half-working one that Word offers to repair is worse than an HTML file the
  recipient can already read.
