# Jarvis — System Architecture

> Jarvis is a personal AI operating system: a durable execution engine with a
> multi-agent runtime, long-term memory, a tool/plugin fabric, and a premium
> client. It is designed to *complete work*, not describe it.

---

## 1. Design tenets

| Tenet | Consequence in the code |
|---|---|
| **The kernel is the product** | Agents, tools and providers are all plugins loaded into a small, hard-tested core. Nothing in the core imports a concrete agent, provider or tool. |
| **Everything is an event** | Every state change is published on the event bus. Observability, streaming UI, and automations are all just subscribers. No special-case telemetry code. |
| **Deterministic offline mode** | An `echo` LLM provider and in-memory stores let the entire system run, and the entire test suite pass, with zero API keys and zero network. |
| **Ports & adapters** | `Protocol` at the boundary, adapters behind it: `LLMProvider`, `MemoryStore`, `Tool`, `EventBus`. Swapping SQLite → Postgres+pgvector is a config change. |
| **Human-in-the-loop by default** | Any tool marked `requires_approval` suspends the run and emits an approval event. "Jarvis, handle it" is earned per-capability, not assumed. |
| **Local-first where possible** | Secrets never leave the vault; memory and documents can live entirely on-device; provider selection can be constrained by a `privacy` floor per request. |

## 2. Topology

```
┌───────────────────────────────────────────────────────────────────────┐
│  CLIENTS                                                               │
│  Next.js web app  ·  Tauri desktop shell  ·  CLI  ·  Voice endpoint    │
└───────────────┬───────────────────────────────────────────────────────┘
                │  HTTP + SSE (text/event-stream)  ·  WebSocket (voice)
┌───────────────▼───────────────────────────────────────────────────────┐
│  API LAYER — FastAPI, fully async                                      │
│  /v1/chat (stream)  /v1/agents  /v1/memory  /v1/models  /v1/runs       │
│  /v1/tools  /v1/workflows  /v1/events (SSE firehose)                   │
└───────────────┬───────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────────┐
│  KERNEL                                                                │
│                                                                        │
│   Orchestrator ──► Planner ──► Router ──► Agent Runtime ──► Tools      │
│        │                          │             │                      │
│        └──────────── Event Bus ◄──┴─────────────┘                      │
│                          │                                             │
│        Memory  ·  Model Router  ·  Vault  ·  Policy/Permissions        │
└───────────────┬───────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────────┐
│  ADAPTERS                                                              │
│  LLM: Anthropic · OpenAI · Gemini · DeepSeek · Qwen · Ollama · Echo     │
│  Store: SQLite/aiosqlite · Postgres+pgvector · Redis · filesystem      │
│  Tools: MCP servers · REST · browser · terminal · SaaS connectors      │
└───────────────────────────────────────────────────────────────────────┘
```

## 3. Kernel components

### 3.1 Event bus (`jarvis.kernel.bus`)
In-process async pub/sub with hierarchical topics (`run.started`, `agent.*`,
`**`). Every subscriber gets its own bounded queue; a slow subscriber drops its
own messages rather than stalling producers. Interface is deliberately
narrow so a Redis Streams / NATS adapter is a drop-in for multi-process.

### 3.2 Model router (`jarvis.llm.router`)
Requests declare *intent*, not a model. The router scores every registered
model against the request policy:

```
score = w_quality·quality + w_cost·(1-norm_cost) + w_latency·(1-norm_latency)
        − hard_fail(context_window < needed)
        − hard_fail(privacy_level < required)
```

Weights come from the request's `RoutingPolicy` (`quality`, `balanced`,
`cheap`, `fast`, `private`). The result is an ordered chain; failures cascade
down it with circuit-breaking per provider, so a provider outage degrades
quality instead of causing an error.

### 3.3 Agent runtime (`jarvis.agents`)
An agent is **data + a policy**, not a subclass. `AgentSpec` declares
responsibilities, system prompt, tool allowlist, capability tags, routing
keywords, default routing policy, and memory scopes. `AgentRuntime` executes
any spec: it assembles context (memory recall + working set), calls the model
router, streams deltas onto the bus, executes tool calls with permission
checks, and records `AgentMetrics` (runs, success rate, p50/p95 latency,
tokens, cost, rolling confidence).

Routing is a two-stage funnel: cheap lexical/capability scoring produces
candidates, then an LLM arbiter picks and can decompose into a multi-agent
plan. Stage one alone is enough offline and is unit-tested deterministically.

### 3.4 Memory (`jarvis.memory`)
Four tiers, one interface:

| Tier | Lifetime | Backing |
|---|---|---|
| Working | one run | in-process |
| Episodic | conversations, runs | relational |
| Semantic | facts, people, projects, prefs, style | relational + vector |
| Procedural | learned workflows, mistakes, successes | relational + vector |

Writes are auto-categorized (`MemoryKind` × topic) and scored for salience;
recall blends lexical BM25-ish scoring with vector similarity and recency
decay. The `EmbeddingModel` port has a deterministic hash-embedding
implementation so recall is testable without network.

### 3.5 Tools (`jarvis.tools`)
A tool is a name, JSON schema, permission tier, and an async callable. The
registry produces provider-native tool definitions. Permission tiers:
`safe` (auto) → `sensitive` (audit-logged) → `dangerous` (explicit approval).
MCP servers mount as tool namespaces.

### 3.6 Runs & workflows
Every unit of work is a `Run` — a durable, resumable record with a step
timeline, cost ledger, and terminal state. Workflows are graphs of steps
(`agent`, `tool`, `approval`, `branch`, `parallel`, `wait`) over the same
runtime, which is why "when email arrives → summarize → draft → approve →
send" needs no new execution machinery.

## 4. Technology decisions

| Choice | Why | Rejected alternative |
|---|---|---|
| FastAPI + async | Streaming is the core UX; SSE/WS first-class | Django (sync-first, heavy) |
| Pydantic v2 everywhere | One schema for validation, OpenAPI and the TS client | hand-written dataclasses |
| SQLAlchemy 2 async + Alembic | Same ORM for SQLite (dev/local-first) and Postgres | raw asyncpg (no local-first story) |
| pgvector | Vectors live *with* the rows they belong to — no dual-write | Pinecone/Weaviate (extra ops, sync drift) |
| SSE over WebSocket for chat | Unidirectional, proxy-friendly, auto-reconnect. WS reserved for duplex voice | WS everywhere |
| Next.js App Router + RSC | Streaming UI, server components for dashboard data | Vite SPA (no streaming SSR) |
| Tailwind + shadcn/ui + Framer Motion | Owned components, no design-system lock-in | MUI (fights the design language) |
| uv | Fast, lockfile-accurate Python builds | Poetry (slower resolution) |
| Echo provider | Full offline determinism for CI | mocking at the HTTP layer (brittle) |

## 5. Security model

- **Vault** — secrets encrypted at rest with a key derived from the OS keychain
  (desktop) or KMS (server). Plaintext never crosses the API boundary; tools
  receive handles, not values.
- **Permissions** — capability-scoped grants per tool, per agent, per
  connector, with an expiry. Grants are data, checked in the runtime, not
  ambient.
- **Audit log** — append-only, hash-chained record of every tool invocation,
  approval, and secret access.
- **Prompt-injection posture** — content fetched from the web, email, or
  repos is wrapped as untrusted and can never elevate a permission tier or
  auto-approve a `dangerous` tool.

## 6. Repository layout

```
jarvis/
├── docs/                   ARCHITECTURE · ROADMAP · UI-DESIGN · adr/
├── apps/
│   ├── api/                FastAPI service (Python)
│   │   ├── src/jarvis/
│   │   │   ├── kernel/     bus · ids · clock · errors · container
│   │   │   ├── llm/        base · router · providers/
│   │   │   ├── agents/     spec · runtime · registry · catalog/ · orchestrator
│   │   │   ├── memory/     store · embeddings · categorizer
│   │   │   ├── tools/      registry · builtins/
│   │   │   ├── runs/       run store · timeline
│   │   │   ├── api/        routes/ · schemas · sse
│   │   │   └── observability/
│   │   └── tests/
│   └── web/                Next.js client
└── infra/                  docker-compose · migrations · CI
```

## 7. Non-goals (deliberately deferred)

Multi-tenancy, RBAC beyond a single principal, mobile clients, and a
distributed scheduler. The event bus and run store are the two seams where
these get added; both are already behind ports.
