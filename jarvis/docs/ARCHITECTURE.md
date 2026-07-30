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
| **A model for judgement with no rule; arithmetic for judgement with one** | Routing between thirty agents has no rule, so an arbiter decides when lexical scoring cannot. "Is this project neglected" has a rule — nobody has written to it in six weeks — so no model is asked, and the answer can be audited and corrected. |
| **Measured, not guessed** | A prompt change is answerable with "eleven cases improved and two broke" against a committed baseline, not with an impression. |

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
│  /v1/briefing  /v1/recommendations  /v1/vault                          │
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

Routing is a two-stage funnel: cheap lexical scoring produces candidates, then
an LLM arbiter decides when that pass is genuinely ambiguous. Stage one alone is
enough offline and is unit-tested deterministically.

Stage one scores **how much a match distinguishes an agent**, not how much text
matched (ADR 0012). Each keyword's weight is divided by how many agents in the
registry claim it, counted per registry so a mode's narrowing makes a contested
word exclusive where it has become so. That is what lets the ambiguity
threshold sit high enough to catch homonyms without escalating every precisely
worded request with them.

**Delegation** (ADR 0014) is opt-in per agent via `collaborators`, which until
Phase 11 was read by nothing while two prompts promised it. A coordinating
agent's request may be decomposed into assignments, run sequentially and
silently, and synthesised into one answer. One level deep, only against *this*
registry, and it falls back to ordinary single-agent routing whenever the
split cannot be parsed.

### 3.4 Memory (`jarvis.memory`)
Four tiers, one interface:

| Tier | Lifetime | Backing |
|---|---|---|
| Working | one run | in-process |
| Episodic | conversations, runs | relational |
| Semantic | facts, people, projects, prefs, style | relational + vector |
| Procedural | learned workflows, mistakes, successes | relational + vector |

Writes are auto-categorized (`MemoryKind` × topic) and scored for salience;
recall blends lexical scoring with vector similarity and recency decay. The
`EmbeddingModel` port has a deterministic hash-embedding implementation so
recall is testable without network. Lexical matching drops stopwords and
matches by prefix, because a stopword hit is not a hit and the router had been
matching by prefix since M1 while recall matched by equality — two opinions
about what a word is, with the weaker one governing what the user could
remember.

An **Obsidian vault** can be the store (ADR 0013). Not an export: the files
*are* the memory, a memory is a line carrying an Obsidian block reference, and
when the user's edit and Jarvis's record disagree the user is right. Ranking is
the same `jarvis.memory.ranking` code every backend uses, so recall order
cannot depend on which one is deployed. `jarvis/obsidian/` is an adapter behind
the port; a test walks every module's AST to prove nothing in core imports it.

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

### 3.7 Voice (`jarvis.voice`)
A session state machine over *transcripts*, not audio: recognition happens in
the browser by default, so no audio leaves the machine and barge-in fires
without a server round trip. Hosted STT/TTS sit behind the same two ports for
clients that need them.

The design constraint is interruption (ADR 0008). One task owns generation and
playback together, so cancelling stops both; the turn records what was
*spoken*, frame by frame as each frame finishes playing, and replays it to the
model marked `[interrupted here]`. A sentence segmenter releases each complete
thought as it forms, so speech starts before generation ends.

### 3.8 Computer control (`jarvis.computer`)
A real browser behind a narrow port, perceived as an **element index** — ref,
role, accessible name, enabled, secret — built from the DOM rather than from
pixels (ADR 0009). Every action names an element, so it also has a sentence:
*click button «Place order — £2,480» on checkout.example.com*. That sentence is
the approval prompt, the audit entry and the UI row.

The wall grades the *target*, not the verb, because for a browser the verb
carries almost no information. Navigation off the allowlist escalates,
credential and payment fields are refused with no approval path, committing
clicks escalate quoting the page, and a ref absent from the current snapshot is
refused as acting blind. Budgets — steps, wall clock, and loop detection — are
part of the boundary, not a nicety.

### 3.9 Modes (`jarvis.modes`)
A mode is a **narrowing**, not a preset (ADR 0010). It produces a narrowed
`AgentRegistry` of narrowed specs — agents filtered, tools intersected with the
agent's own allowlist, memory namespaced, routing policy overridden — and
everything downstream runs unchanged against it. The invariant is that a mode
can only subtract: it cannot grant a tool, raise a permission, or reach an
agent the catalog lacks, so choosing a mode can never widen authority.

### 3.10 Documents (`jarvis.documents`)
Outline first, then each section written against passages retrieved for that
section. Citations are captured from what the section was handed and filtered
to the markers that actually appear in its prose — a claim about provenance the
system can make, unlike asking a model afterwards what it used.

### 3.11 Security (`jarvis.security`)
The vault is AES-256-GCM over a `SecretStore`, but its substantive part is the
**redactor** (ADR 0011): every known secret scrubbed from anything headed for a
log, an event or the audit log. The model references a secret by name and never
receives one; the tool registry resolves `${vault:name}` at call time, after
authorisation and after the audit write.

`CostGovernor` grades a call *before* it is made, against a conservative
estimate, in the model router — the one place every call passes through. A soft
ceiling routes into the approval gate; a hard ceiling refuses outright.

### 3.12 Chief of Staff (`jarvis.chief`)
Proactive intelligence with **no model in the loop** (ADR 0014). Nine
deterministic detectors read one snapshot of state — approvals blocking a run,
failures nobody returned to, workflows suspended and forgotten, projects gone
cold, goals stated and never mentioned, deadlines, repeated mistakes, budget
pressure, knowledge stranded in the vault — and ranking is
`impact × urgency × confidence` with the evidence attached.

Handing everything to a model and asking "what should they do today" reads
better and is unauditable, non-deterministic, unavailable offline and
unfalsifiable. Arithmetic can be corrected: either the evidence is wrong or the
number is.

The hard part is restraint. Each detector caps its own output, a sweep surfaces
at most ten and at most two per signal, and the report says how many it held
back. Recommendation ids are stable across sweeps so "not now" means something;
dismissals expire after a week so it does not mean "never".

The **morning briefing** composes from the same sweep. A model writes the
two-sentence opener when one is configured — facts are never asked of it — with
a deterministic fallback that is plainer and never wrong. Empty sections are
absent rather than empty, and sources Jarvis cannot read (mail, calendar,
absent a connector) are named rather than silently omitted.

### 3.13 Evaluation (`eval/`)
Not a test suite (ADR 0015). 288 cases across ten dimensions, each carrying
expected behaviour, defensible and actively-wrong agents, expected tools,
success criteria and a confidence. A check answers yes, no or **not
applicable**, and skipped checks carry no weight — so a provider outage
produces a smaller sample rather than a perfect score.

Two-thirds never touch a model, so CI runs them on every push against a
committed baseline. The exit code answers "did this change make things worse",
not "is the corpus perfect".

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
├── docs/                   ARCHITECTURE · ROADMAP · UI-DESIGN ·
│                        EVALUATION · PROMPTS · OBSIDIAN ·
│                        INTELLIGENCE-AUDIT · adr/
├── apps/
│   ├── api/                FastAPI service (Python)
│   │   ├── src/jarvis/
│   │   │   ├── kernel/     bus · ids · clock · errors · container
│   │   │   ├── llm/        base · router · providers/
│   │   │   ├── agents/     spec · runtime · registry · catalog/ · orchestrator
│   │   │   ├── memory/     store · embeddings · ranking · categorizer
│   │   │   ├── obsidian/   note · vault · naming · links · store · index · sync
│   │   │   ├── chief/      situation · signals · engine · briefing
│   │   │   ├── tools/      registry · builtins/
│   │   │   ├── runs/       run store · timeline
│   │   │   ├── api/        routes/ · schemas · sse
│   │   │   └── observability/
│   │   ├── eval/           checks · scoring · corpus/ · runner · report
│   │   └── tests/
│   └── web/                Next.js client
└── infra/                  docker-compose · migrations · CI
```

## 7. Non-goals (deliberately deferred)

Multi-tenancy, RBAC beyond a single principal, mobile clients, and a
distributed scheduler. The event bus and run store are the two seams where
these get added; both are already behind ports.
