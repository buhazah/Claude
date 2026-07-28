# Jarvis — Execution Roadmap

Each milestone is independently shippable, tested, and committed. No milestone
begins before the previous one's suite is green.

| # | Milestone | Contents | State |
|---|---|---|---|
| **M1** | **Kernel** | Config, structured logging, event bus, model router + provider adapters (Anthropic/OpenAI/Echo), agent spec + runtime + registry + 30-agent catalog, memory store + embeddings + categorizer, run store, tool registry, FastAPI surface with SSE streaming | ✅ **done** |
| **M2** | **Client** | Next.js app, design system, command palette with routing preview, dashboard, streaming chat, agent/memory/run/tool browsers, live activity rail off the event firehose | ✅ **done** |
| **M3** | **Persistence** | Postgres + pgvector, Alembic migrations, hosted embeddings, Redis-backed bus, docker-compose | ✅ **done** |
| **M4** | **Tools & connectors** | MCP client, browser tool, terminal tool, filesystem, GitHub, Gmail, Calendar, Slack, Notion, Stripe; permission tiers + approval UI | |
| **M5** | **Knowledge** | Ingestion pipeline (PDF/DOCX/PPTX/XLSX/images/audio/repos/URLs), chunking, hybrid retrieval, citations |  |
| **M6** | **Workflows** | Graph engine, triggers, scheduler, approvals, workflow builder UI | |
| **M7** | **Voice** | Streaming STT, TTS, barge-in/interruption, wake word | |
| **M8** | **Computer control** | Sandboxed desktop/browser control with screenshot loop and a hard permission wall | |
| **M9** | **Modes** | Business / Coding (Claude Code integration) / Research mode surfaces + document generation | |
| **M10** | **Hardening** | Vault, audit chain, cost governance, CI/CD, load + chaos tests, packaging | |

## Milestone 1 — delivered

**Built**
- `jarvis.kernel` — event bus with hierarchical topics and per-subscriber
  bounded queues; ULID-ish ids; injectable clock; error taxonomy.
- `jarvis.llm` — provider port, model catalog with cost/latency/quality/
  context/privacy attributes, policy-weighted router with fallback chains and
  per-provider circuit breaking; Anthropic, OpenAI and Echo adapters.
- `jarvis.agents` — declarative `AgentSpec`, generic `AgentRuntime` that
  streams onto the bus and records metrics, lexical+capability router, and a
  catalog of 30 agents.
- `jarvis.memory` — tiered store with auto-categorization, salience scoring,
  hybrid lexical+vector recall with recency decay, deterministic embeddings.
- `jarvis.tools` — schema'd tool registry with three permission tiers.
- `jarvis.runs` — durable run records with step timelines and cost ledgers.
- `jarvis.api` — FastAPI app: health, models, agents, memory, runs, chat
  (SSE), and an event firehose.

**Verification** — `pytest` suite covering router scoring, fallback and
circuit breaking, bus fan-out and backpressure, agent routing, memory recall
ranking, run lifecycle, and the HTTP surface end-to-end. Runs with no API keys
and no network.

## Milestone 2 — delivered

**Built**
- Design system in CSS custom properties: dark-first tokens, layered surfaces,
  one accent reserved for live state, glass restricted to floating surfaces.
- App shell — sidebar with spring-animated active indicator, ⌘K palette,
  live activity rail.
- **Command palette** — the defining interaction. As you type, it calls
  `/v1/route` and shows which agents Jarvis would activate, with confidence
  bars and the matched signals, *before* you commit.
- **Streaming chat** — token-by-token rendering with a caret, the answering
  agent and its confidence, recalled-memory count, and live cost/token/latency.
  Interruptible mid-answer via `AbortController`.
- **Live activity rail** — the kernel's event bus rendered directly. Not
  instrumentation; a subscriber.
- Dashboard, agent grid with per-agent metrics, memory browser showing the
  lexical/semantic/recency signals behind each recall, run history, and a tool
  browser grouped by permission tier.
- Every surface defines loading (geometry-matched skeletons), empty, error and
  streaming states.

**Verification** — 20 unit tests (incremental SSE parsing across arbitrary
chunk boundaries, malformed frames, the typed API client) plus a 7-check
Playwright end-to-end run against the real kernel: routing preview →
execution → streaming → run history, with zero console errors. `tsc --noEmit`
and ESLint clean.

## Milestone 3 — delivered

**Built**
- `jarvis.persistence` — SQLAlchemy 2 async schema serving both dialects. The
  only dialect-specific piece is the embedding column: a real pgvector
  `vector` on Postgres, JSON on SQLite, behind one `TypeDecorator`.
- `SqlMemoryStore` / `SqlRunStore` — durable stores behind the existing ports.
  Recall retrieves candidates per-backend (HNSW ANN ∪ lexical on Postgres, a
  bounded window on SQLite) and ranks them with **shared** code, so results
  cannot drift between deployments (ADR 0004).
- Run persistence splits cheap synchronous mutation from explicit awaited
  checkpoints, keeping IO off the streaming hot path.
- Alembic migrations with an HNSW cosine index, applied and verified against a
  live Postgres 16 + pgvector.
- `RedisEventBus` — cross-process fan-out that extends rather than replaces the
  in-process bus, so local delivery keeps its latency and a Redis outage
  degrades to single-node instead of failing.
- `HostedEmbedder` — OpenAI-compatible embeddings that fall back to the
  deterministic local embedder on any failure.
- `docker-compose.yml` + API `Dockerfile` for the server deployment.

**Verification** — 192 tests. The store contract suite runs against all three
backends; migrations are asserted not to have drifted from the models; Redis
cross-node delivery and no-Redis degradation are both covered. Verified for
real against Postgres 16 + pgvector and Redis 7: migrations applied, HNSW index
created, and runs, steps and memories all survived a process restart.

Storage stays opt-in — with no `JARVIS_DATABASE_URL` the system is fully
in-process, and the offline suite (174 tests) still runs with no server.

## Definition of done (every milestone)

1. Tests written alongside the code, suite green.
2. `ruff` + `mypy` clean on changed packages.
3. Docs updated (architecture deltas, ADR if a decision changed).
4. Committed with a message that explains the *why*.
