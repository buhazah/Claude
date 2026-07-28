# Jarvis

A personal AI operating system: a durable execution engine with a multi-agent
runtime, long-term memory, a tool/plugin fabric, and a premium client.

Jarvis is built to **complete work**, not describe it. The long-term goal is a
system you can hand an outcome to — "handle it" — and get the outcome back.

- [Architecture](docs/ARCHITECTURE.md) — components, ports, decisions
- [Roadmap](docs/ROADMAP.md) — milestones and what each one delivers
- [Interface design](docs/UI-DESIGN.md) — the design language and frames
- [Decisions](docs/adr/) — architecture decision records

## Status

**Milestones 1 through 8 are complete.**

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

Milestone 9 (business, coding and research modes) is next.

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
make e2e      # Playwright, against both servers running
```

## Layout

```
jarvis/
├── docs/                ARCHITECTURE · ROADMAP · UI-DESIGN · adr/
└── apps/
    ├── api/             FastAPI service
    │   ├── src/jarvis/
    │   │   ├── kernel/  bus · clock · ids · errors · container
    │   │   ├── llm/     provider port · router · adapters
    │   │   ├── agents/  spec · runtime · registry · catalog · orchestrator
    │   │   ├── memory/  store · embeddings · ranking · categorisation
    │   │   ├── knowledge/  extract · chunk · ingest · store
    │   │   ├── workflows/  engine · triggers · scheduler · catalog
    │   │   ├── tools/   registry · tiers · approvals · system · MCP
    │   │   ├── voice/   session · segmenter · wake word · speech ports
    │   │   ├── computer/  element index · permission wall · browser driver
    │   │   ├── runs/    run records · durable store
    │   │   ├── persistence/  schema · engine · migrations
    │   │   └── api/     routes · schemas · SSE
    │   └── tests/
    └── web/             Next.js client
        ├── src/app/      dashboard · chat · agents · memory · knowledge ·
        │                 workflows · runs · tools · computer
        ├── src/components/  shell · command palette · activity rail · ui
        ├── src/lib/      typed API client · incremental SSE parser
        └── e2e/          Playwright: smoke · approval · knowledge ·
                          workflows · voice · computer
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

**Connectors are MCP servers.** Rather than a hand-written adapter per SaaS
product, Jarvis speaks Model Context Protocol and mounts each server as a tool
namespace — so `Grant("github.*", SENSITIVE)` governs a whole server, and a
remote server never gets to choose its own blast radius.
