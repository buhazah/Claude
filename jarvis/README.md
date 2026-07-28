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

**Milestones 1 and 2 are complete.**

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

Milestone 4 (tools and connectors) is next.

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

Open http://localhost:3000 and press ⌘K.

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
    │   │   ├── memory/  store · embeddings · categorisation
    │   │   ├── tools/   registry · permission tiers · builtins
    │   │   ├── runs/    run records · durable store
    │   │   ├── persistence/  schema · engine · migrations
    │   │   └── api/     routes · schemas · SSE
    │   └── tests/
    └── web/             Next.js client
        ├── src/app/      dashboard · chat · agents · memory · runs · tools
        ├── src/components/  shell · command palette · activity rail · ui
        ├── src/lib/      typed API client · incremental SSE parser
        └── e2e/          Playwright smoke test
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

**Permissions are data.** Tools declare a blast-radius tier; grants are checked
at call time. An agent cannot widen its own reach by reasoning about it.
