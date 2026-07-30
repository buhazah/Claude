# Jarvis

A personal AI operating system: a durable execution engine with a multi-agent
runtime, long-term memory, a tool/plugin fabric, and a premium client.

Jarvis is built to **complete work**, not describe it. The long-term goal is a
system you can hand an outcome to — "handle it" — and get the outcome back.

- [Architecture](docs/ARCHITECTURE.md) — components, ports, decisions
- [Roadmap](docs/ROADMAP.md) — milestones and what each one delivers
- [Interface design](docs/UI-DESIGN.md) — the design language and frames
- [Evaluation](docs/EVALUATION.md) — how intelligence is measured rather than guessed
- [Prompt strategy](docs/PROMPTS.md) — what Jarvis tells a model, and why
- [Obsidian](docs/OBSIDIAN.md) — the vault as long-term memory you own
- [Intelligence audit](docs/INTELLIGENCE-AUDIT.md) — what the prompts and router got wrong
- [Decisions](docs/adr/README.md) — architecture decision records

## Status

**Ten milestones built the platform. Phase 11 is making it smarter.**

*M1 — kernel*: event bus, model router with fallback and circuit breaking,
30-agent catalog with a spec-driven runtime, tiered memory with hybrid recall,
permissioned tool registry, durable runs, streaming HTTP surface.
134 tests · `ruff` clean · `mypy --strict` clean.

*M2 — client*: design system, ⌘K command palette that previews routing before
executing, streaming chat, live activity rail wired to the kernel's event bus,
and browsers for agents, memory, runs and tools.
20 unit tests · 7 Playwright end-to-end checks · `tsc` and ESLint clean.

*M3 — persistence*: SQLAlchemy 2 async stores on SQLite or Postgres+pgvector,
Alembic migrations with an HNSW index, a Redis-backed bus for multi-process
fan-out, and hosted embeddings — all behind the M1 ports, all opt-in.
192 tests, including a contract suite run against every backend.

*M4 — tools*: the agentic loop that actually executes tool calls, filesystem/
shell/HTTP tools inside a workspace boundary, an MCP client that mounts any
connector as a tool namespace, human approval for irreversible actions, and a
hash-chained audit log.
262 tests, including a browser-driven approval flow.

*M5 — knowledge*: ingestion for PDF, DOCX, PPTX, XLSX, CSV, HTML, URLs, code
and folders, with locators preserved from extraction through chunking so every
retrieved passage carries a checkable citation.
319 tests, including extraction against real generated documents.

*M6 — workflows*: a graph engine whose suspended runs survive a restart,
structured conditions, schedule and event triggers, and a scheduler that
recovers parked work on boot.
381 tests, including finishing a workflow on a different engine than started it.

*M7 — voice*: a session state machine where interrupting cancels generation as
well as playback, history records what was actually *heard*, speech starts
before generation finishes, and a wake word summons Jarvis without answering
every mention of the name.
426 tests, including barge-in driven through a real browser.

*M8 — computer control*: a real browser behind a permission wall that grades
what an action touches rather than what it is called — off-allowlist navigation
asks first, committing clicks quote the page, and credential fields are refused
outright with no approval to click through.
477 tests, including five against real Chromium.

*M9 — modes and documents*: Business, Coding and Research narrow which agents
can be reached, which tools survive, and which memory answers — and can only
ever subtract, never grant. Documents are planned as an outline, written
section by section, and carry checkable sources.
543 tests, including proof the narrowing is enforced by the kernel rather than
by the client.

*M10 — hardening*: an encrypted vault whose real work is keeping secrets out of
logs, events and the audit trail; cost ceilings checked before each call rather
than reported after; and durable backings for the vault, approvals, documents
and agent metrics.
583 tests, including load and chaos, and durability verified across a real
process restart.

*Phase 11 — intelligence*: an audit of every prompt and routing rule that found
eleven defects in code that read perfectly well; a 288-case evaluation corpus
that CI runs on every push; an Obsidian vault where the files *are* the memory
rather than an export of it; delegation, closing a promise the prompts had been
making since M1; a recommendation engine with no model in the loop; and a
morning briefing.
686 tests · 9 Playwright suites · the router's escalation rate down from 78%
to 48% with accuracy up.
One piece outstanding — the behavioural prompt work needs a provider key, and
doing it without one would be the guessing this phase exists to stop.

## Run it

Nothing is required to start — no API keys, no database, no network. Jarvis
boots with a deterministic offline provider so the whole system is explorable
immediately.

```bash
# kernel — :8000
cd apps/api && uv venv && source .venv/bin/activate
uv pip install -e ".[dev]" && uvicorn jarvis.main:app --reload

# client — :3000
cd apps/web && pnpm install && pnpm dev
```

Open http://localhost:3000 and press ⌘K — or ⌘⇧V to talk to it.

## Secrets and spending

```bash
export JARVIS_VAULT_KEY=$(python -m jarvis.security.keygen)
export JARVIS_DAILY_BUDGET_SOFT_USD=5      # asks you
export JARVIS_DAILY_BUDGET_HARD_USD=25     # refuses
```

The model never holds a secret — it references one as `${vault:stripe}`, and
Jarvis substitutes the value inside the tool call, after the audit entry is
written. Every stored value is scrubbed from logs, events, audit entries and
exception messages, which is where secrets actually escape.

Ceilings are checked *before* each call, against a conservative estimate. The
soft one parks for your approval; the hard one refuses without asking.

## Modes

Switching mode is a real constraint, not a theme. Each one narrows which agents
can be routed to, which tools they keep, and which memory namespace they read —
and a mode can only ever *subtract*, so picking one can never widen what Jarvis
is allowed to do.

| Mode | Narrows to |
|---|---|
| **Personal** | everything — the unconstrained default |
| **Business** | operating agents, `business:` memory |
| **Coding** | engineering agents, quality-first routing, `coding:` memory |
| **Research** | research agents, every claim cited, `research:` memory |

## Documents

Ask for a report and Jarvis plans an outline first, then writes each section
against passages retrieved for *that section* — so the sources at the bottom
are the ones actually used, with the locators M5 preserved. Exports as Markdown
or a self-contained HTML file.

## Computer control

Off by default. Enabled, Jarvis drives a real browser — and every action it
takes is a sentence you can read before you approve it.

```bash
export JARVIS_ENABLE_COMPUTER=true
export JARVIS_BROWSER_ALLOWED_HOSTS='["github.com","docs.python.org"]'
```

Anywhere else asks first. Clicks that commit something — pay, delete, send —
quote the page's own words in the approval prompt. Password and payment fields
are refused outright: that one is not an approval you can click through.

## Voice

Recognition runs in the browser, so no audio leaves the machine by default and
interruptions are instant — the moment you start speaking, Jarvis stops
speaking *and* stops generating. Set a speech key to use hosted transcription
and a real voice instead:

```bash
export JARVIS_SPEECH_API_KEY=...
export JARVIS_TTS_VOICE=alloy
export JARVIS_REQUIRE_WAKE_WORD=true   # only answer after "Jarvis"
```

```bash
curl localhost:8000/health

# Preview which agents Jarvis would activate, without executing
curl -X POST localhost:8000/v1/route \
  -H 'content-type: application/json' \
  -d '{"message":"find leads for my supplement brand"}'

# Execute, streaming
curl -N -X POST localhost:8000/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message":"research competitors in oat milk"}'

# Watch everything happening inside the kernel
curl -N 'localhost:8000/v1/events?topics=agent.**,llm.**'
```

Add real models by setting keys — the router picks up whatever is configured
and falls back through the rest when one fails:

```bash
export JARVIS_ANTHROPIC_API_KEY=...
export JARVIS_OPENAI_API_KEY=...
export JARVIS_ENABLE_LOCAL_LLM=true    # any Ollama-compatible endpoint
```

## Evaluating the intelligence

Everything above is tested against a deterministic offline provider, which
proves the machinery and says nothing about whether the prompts are any good —
a router that confidently sends every request to the wrong agent passes 600
tests. [`eval/`](docs/EVALUATION.md) closes that gap: 288 cases across routing,
planning, tool selection, memory, research, execution, workflows, documents,
coding and business.

```bash
make eval-free                              # two-thirds of it, no key, no network
make eval-plan                              # what a full run would cost
export JARVIS_ANTHROPIC_API_KEY=...
make eval budget=5                          # aborts rather than exceed $5
```

Each case says what good looks like, which agents are defensible, which would be
actively *wrong*, which tools it should reach for, and how much its author
trusts the check to mean anything — so the report can show a weighted score
next to a raw one and never let a proxy pass for a measurement.

Most of the corpus never touches a model, which is what makes it something CI
runs on every push: routing is scored on stage one alone, and recall runs
against the store. A run writes a scorecard small enough to commit, so the next
one can say *what moved* — eleven cases improved, two broke — rather than
offering an average that hides both.

Whether an answer reasons *well* is not a keyword question, so ten probes run
with no verdict at all and their transcripts are printed for a human. Anything
key-shaped is scrubbed on the way out.

## The morning briefing

```
GET /v1/briefing        →  http://localhost:3000/briefing
```

One opener, then only the sections that have something in them. A quiet day
gets a single line — the instinct to fill nine headings whatever the state of
the world is what makes generated briefings unreadable.

It says what it could not see. Jarvis has no mail or calendar unless you mount
a connector, and a briefing that invents "3 emails need you" is *confidently*
useless — so absent sources are named at the bottom rather than silently
omitted, because a missing calendar section reads as "nothing on today".

A model writes the two sentences at the top, when one is configured. Everything
else — what is on the list, in what order, with what evidence — is the
arithmetic below.

## Chief of Staff

Jarvis looks for what you have not asked about.

```bash
curl localhost:8000/v1/recommendations
```

```
[ 20.0] major    / blocking   Approve or refuse: browser_click
[  8.4] major    / this_week  Fix the cause: 3 recorded failures in coding
[  4.8] major    / soon       Decide what happens to Northbound
         · nothing written to Projects/Northbound.md in 13 weeks
```

Nine detectors over what Jarvis already has: approvals blocking a run, failures
nobody returned to, workflows suspended and forgotten, projects gone cold,
goals stated and never mentioned again, deadlines, repeated mistakes, budget
pressure, knowledge stranded in the vault.

**Ranking is arithmetic, not a model's opinion** — `impact × urgency ×
confidence`, with the evidence attached. Handing everything to a model and
asking "what should I do today" reads better and cannot be corrected when it is
wrong. This can: either the evidence is wrong, or the number is. It also costs
nothing and works with no key.

The hard part is not noticing. A sweep surfaces at most ten things, at most two
per kind, and says how many it held back — because an assistant that surfaces
forty observations gets muted in a week and then notices nothing at all. A cold
project is treated as important and *never urgent*, which is exactly why it
went cold.

Ask the Chief of Staff to handle something spanning several specialists and it
now actually delegates — decomposing the request, dispatching to the agents in
its `collaborators`, and writing one answer from what comes back. Off by
default for every other agent, one level deep, and it falls back to ordinary
single-agent routing whenever the split cannot be made.

## Memory you own

Point Jarvis at an Obsidian vault and its memory becomes markdown files:

```bash
export JARVIS_OBSIDIAN_VAULT=~/Documents/Vault
```

Each fact is a line with an Obsidian block reference, filed by tag into
`Projects/`, `People/`, `Meetings/`, `Research/` and `Business/`, with a dated
journal of what happened. Every completed task leaves something behind — not
via a special hook, but because the runtime has written a memory after every
run since M1 and this is where memories now live.

The rule the whole thing rests on: **when your edit and Jarvis's record
disagree, you are right.** Fix a number, delete a line — Jarvis reads what is
there now. There is no shadow database to overwrite you, which is the
difference between this and a markdown export.

`GET /v1/vault` reports the shape of what you know rather than its content:
what has gone cold, what is connected to nothing, which links Jarvis should
have made and did not.

## Persistence

Nothing is stored by default — the system runs entirely in-process. Point it at
a database and the same code becomes durable:

```bash
# local-first: a file on your machine, no server, no extension
export JARVIS_DATABASE_URL="sqlite:///jarvis.db"

# server: Postgres + pgvector, with migrations
export JARVIS_DATABASE_URL="postgresql://jarvis:jarvis@localhost/jarvis"
export JARVIS_REDIS_URL="redis://localhost:6379/0"   # multi-process event bus
alembic upgrade head
```

Or bring up the whole server stack:

```bash
docker compose up
```

SQLite creates its schema on start. Postgres is owned by Alembic, so a server
deployment migrates first — `docker compose` does that before serving.

Embeddings follow the same pattern: deterministic local ones by default,
hosted ones when `JARVIS_EMBEDDING_API_KEY` is set, falling back to local if
the provider fails.

## Develop

```bash
make test     # pytest + vitest
make lint     # ruff + eslint
make types    # mypy --strict + tsc
make check    # everything
make e2e-serve  # one API with everything the suites need (separate shell)
make e2e        # all 9 Playwright suites — what CI runs
make eval-free  # the free two-thirds of the corpus — no key, no network
make eval-plan  # what a full evaluation would cost — spends nothing
make eval       # the whole corpus against a real model
```

## Layout

```
jarvis/
├── docs/                ARCHITECTURE · ROADMAP · UI-DESIGN ·
│                        EVALUATION · PROMPTS · OBSIDIAN ·
│                        INTELLIGENCE-AUDIT · adr/
└── apps/
    ├── api/             FastAPI service
    │   ├── src/jarvis/
    │   │   ├── kernel/  bus · clock · ids · errors · container
    │   │   ├── llm/     provider port · router · adapters
    │   │   ├── agents/  spec · runtime · registry · catalog · orchestrator
    │   │   ├── memory/  store · embeddings · ranking · categorisation
    │   │   ├── obsidian/  note format · vault · naming · links · index · sync
    │   │   ├── chief/   situation · signals · engine · briefing
    │   │   ├── knowledge/  extract · chunk · ingest · store
    │   │   ├── workflows/  engine · triggers · scheduler · catalog
    │   │   ├── tools/   registry · tiers · approvals · system · MCP
    │   │   ├── voice/   session · segmenter · wake word · speech ports
    │   │   ├── computer/  element index · permission wall · browser driver
    │   │   ├── modes/    narrowed registries: agents · tools · memory scope
    │   │   ├── documents/  outline → sections → citations → md/html
    │   │   ├── security/ vault · redaction · cost governance · SQL stores
    │   │   ├── runs/    run records · durable store
    │   │   ├── persistence/  schema · engine · migrations
    │   │   └── api/     routes · schemas · SSE
    │   ├── eval/        checks · scoring · corpus · runner · report
    │   └── tests/
    └── web/             Next.js client
        ├── src/app/      dashboard · briefing · chat · agents · memory ·
        │                 knowledge · workflows · runs · tools · documents ·
        │                 computer · settings
        ├── src/components/  shell · command palette · activity rail · ui
        ├── src/lib/      typed API client · incremental SSE parser
        └── e2e/          Playwright: smoke · approval · knowledge ·
                          workflows · voice · computer · modes · settings ·
                          briefing
```

## Design notes

**Offline determinism.** The `echo` provider and in-process stores are
first-class, not test doubles. CI runs the entire suite with no keys and no
network, which is also why the fallback chain always has a floor.

**Routing is two-stage.** A free, deterministic lexical pass handles most
requests; an LLM arbiter is consulted only when that pass is genuinely
ambiguous. Most messages therefore cost zero extra latency to route.

**Everything is an event.** Token deltas, tool calls, memory writes and run
transitions all publish to one bus. The live activity feed, observability and
(later) workflow triggers are subscribers, not instrumentation.

**Citations are structural.** A locator (`p. 4`, `slide 2`, `Revenue!1:40`) is
captured at extraction and carried through chunking, so a retrieved passage can
always be checked against its source rather than merely attributed to a file.

**Suspension is durable.** A workflow waiting on a human is a database row,
not a coroutine — its cursor and context persist, so a decision can arrive
tomorrow, in a different process, and the run continues.

**Permissions are data.** Tools declare a blast-radius tier; grants are checked
at call time. An agent cannot widen its own reach by reasoning about it, and a
`dangerous` tool suspends for a human rather than failing or proceeding.

**Judgement with a rule is arithmetic.** Routing between thirty agents has no
rule, so an arbiter decides when lexical scoring cannot. "Is this project
neglected" has one — nobody has written to the note in six weeks — so no model
is asked, the answer is the same twice, and when it is wrong there is something
to correct.

**Connectors are MCP servers.** Rather than a hand-written adapter per SaaS
product, Jarvis speaks Model Context Protocol and mounts each server as a tool
namespace — so `Grant("github.*", SENSITIVE)` governs a whole server, and a
remote server never gets to choose its own blast radius.
