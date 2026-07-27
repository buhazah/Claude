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

**Milestone 1 (kernel) is complete**: event bus, model router with fallback and
circuit breaking, 30-agent catalog with a spec-driven runtime, tiered memory
with hybrid recall, permissioned tool registry, durable runs, and a streaming
HTTP surface. 134 tests, `ruff` clean, `mypy --strict` clean.

Milestone 2 (the client) is next.

## Run it

Nothing is required to start — no API keys, no database, no network. Jarvis
boots with a deterministic offline provider so the whole system is explorable
immediately.

```bash
cd apps/api
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn jarvis.main:app --reload
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

## Develop

```bash
make test     # pytest
make lint     # ruff check + format check
make types    # mypy --strict
make check    # all three
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
    │   │   ├── runs/    durable run records
    │   │   └── api/     routes · schemas · SSE
    │   └── tests/
    └── web/             Next.js client (M2)
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
