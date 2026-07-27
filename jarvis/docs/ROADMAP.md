# Jarvis — Execution Roadmap

Each milestone is independently shippable, tested, and committed. No milestone
begins before the previous one's suite is green.

| # | Milestone | Contents | State |
|---|---|---|---|
| **M1** | **Kernel** | Config, structured logging, event bus, model router + provider adapters (Anthropic/OpenAI/Echo), agent spec + runtime + registry + 30-agent catalog, memory store + embeddings + categorizer, run store, tool registry, FastAPI surface with SSE streaming | ✅ **done** |
| **M2** | **Client shell** | Next.js app, design system, command palette, dashboard, streaming chat, agent/memory browsers, live activity feed off the event firehose | ⏳ next |
| **M3** | **Persistence** | Postgres + pgvector, Alembic migrations, real embeddings, Redis-backed bus, docker-compose | |
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

## Definition of done (every milestone)

1. Tests written alongside the code, suite green.
2. `ruff` + `mypy` clean on changed packages.
3. Docs updated (architecture deltas, ADR if a decision changed).
4. Committed with a message that explains the *why*.
