# Architecture

JARVIS is a modular monolith: one deployable FastAPI process composed of
cleanly separated subsystems that communicate through well-defined interfaces.
This gives the operational simplicity of a single service with the internal
boundaries of a microservice design, so any subsystem can later be extracted
behind its existing interface without rewrites.

## High-level flow

1. The **browser SPA** (`web/`) authenticates, then sends a chat request to
   `POST /api/chat/stream`.
2. The **orchestrator** (`server/agents/orchestrator.py`) recalls relevant
   long-term memory, decides *simple* vs *complex*, and either answers with a
   single agent or builds and executes a task graph.
3. Each **agent** (`server/agents/runtime.py`) runs a ReAct-style
   reason→act→observe loop, calling **tools** and the **model router** as
   needed.
4. The **model router** (`server/llm/router.py`) scores every configured
   model and dispatches to the best fit, falling back on failure.
5. Results are **synthesized**, streamed back as Server-Sent Events, persisted
   as messages and an `AgentRun`, and mined for new **memories**.

```
                         ┌──────────────────────────────┐
   Browser SPA  ───SSE──►│         FastAPI app          │
   (web/)               │        (server/main.py)       │
                         └───────────────┬───────────────┘
                                         │
              ┌──────────────────────────┼───────────────────────────┐
              ▼                          ▼                            ▼
      Orchestrator                Memory Manager               Automation Engine
   task decomposition          recall / rank / decay          cron loop, run history
   routing / synthesis         consolidate / reflect          (30s tick)
              │                          │                            │
              ▼                          ▼                            │
       Agent Runtime  ◄───── memory context ─────┐                    │
   reason/act/observe                            │                    │
              │                                  │                    │
      ┌───────┴────────┐                         │                    │
      ▼                ▼                         ▼                    ▼
  Tool Registry    Model Router  ────►  Embeddings backend    (invokes orchestrator)
  web/fs/shell/    cost/speed/quality    OpenAI/Voyage/local
  code/docs        + fallback
                         │
                         ▼
              LLM Providers (Anthropic, OpenAI, Google, Groq, DeepSeek,
                             OpenRouter, Ollama)

  All subsystems persist through async SQLAlchemy ──► SQLite (default) / Postgres
```

## Subsystems

### Orchestrator (`agents/orchestrator.py`)
The "master" reasoning layer. For each request it:
- Pulls a memory context block (semantic recall over the user's memories).
- Calls a fast model to classify **simple** vs **complex** and, if complex,
  emit a JSON task graph: `[{id, agent, instruction, depends_on}]`.
- Executes tasks in dependency order (with cycle protection), feeding upstream
  results into downstream instructions.
- Synthesizes a single cohesive answer and triggers memory extraction.

Simple requests skip decomposition entirely and go straight to one agent —
most chat is simple, so this keeps latency and cost low.

### Agent runtime (`agents/runtime.py`)
A bounded ReAct loop (max 8 steps). The agent thinks in plain text, optionally
emits a fenced-JSON tool call, observes the result, and repeats until it emits
`{"final": …}` or the step budget runs out. Every run is persisted as an
`AgentRun` with its plan, steps, token counts, and estimated cost — this is
what the Agents and Analytics views read.

### Agents (`agents/definitions.py`)
23 declarative `AgentDef`s. Each carries a role, goals, an allow-list of tools,
and routing hints (`complexity`, `min_context`, `temperature`). The system
prompt is generated from these fields, so adding an agent is pure data.

### Memory (`memory/`)
- **Embeddings** (`embeddings.py`): OpenAI or Voyage when a key exists,
  otherwise a dependency-free local hash embedder (character-n-gram feature
  hashing) that gives useful lexical retrieval offline. All vectors are
  unit-norm float32, so cosine similarity is a dot product.
- **Manager** (`manager.py`): stores memories with per-kind importance;
  retrieval ranks by `0.6·similarity + 0.25·importance + 0.15·recency_decay`.
  Recency uses exponential decay with a configurable half-life. It also does
  LLM-backed extraction, consolidation (merge bloated kinds into summaries),
  and reflection (distill recent memory into insights).

### Model router (`llm/`)
A catalog of models with cost/speed/quality/context metadata. Given a
`RouteProfile`, the router scores every model from every *configured* provider
and returns a ranked list; `complete`/`stream` walk that list so a provider
outage degrades gracefully. Costs are computed from real token usage.

### Tools (`tools/`)
A typed registry. Tools declare parameters with types/enums/required flags;
the executor validates arguments before running and enforces a per-tool
timeout. Filesystem and shell tools are confined to a sandbox directory via
resolved-path checks that block traversal.

### Automation (`automation/scheduler.py`)
An in-process async loop ticks every 30s, evaluates each enabled workflow's
5-field cron expression (parsed in-house — ranges, lists, steps, `*/n`), and
runs due workflows through the orchestrator, recording a `WorkflowRun`.

### API (`api/`)
FastAPI routers, one per domain (auth, chat, agents, memory, projects,
workflows, voice, analytics). Chat streams SSE; everything else is JSON with
Pydantic validation on the way in and out.

## Data flow: a complex request

```
User: "Research my top competitor and draft a positioning statement."
  │
  ├─ orchestrator.recall() → memory context (user's business, voice, goals)
  ├─ planner → mode=complex, tasks=[
  │     {id:1, agent:research,  instruction:"Research competitor X"},
  │     {id:2, agent:marketing, instruction:"Draft positioning", depends_on:[1]}]
  ├─ run task 1 (research): web_search → web_fetch → synthesize findings
  ├─ run task 2 (marketing): receives task 1's result, writes positioning
  ├─ synthesize(1,2) → single answer
  └─ extract_from_exchange() → new memories (competitor, positioning decision)
```

## Scaling path

The default single-node SQLite deployment handles a personal/small-team load
comfortably. To scale:
- **Database**: set `JARVIS_DATABASE_URL` to Postgres (asyncpg). No code change.
- **Vector search**: the embedding storage is behind the memory manager; swap
  the brute-force cosine for pgvector or Qdrant by changing only `manager.py`.
- **Scheduler**: for multi-instance, move the cron loop to a single leader or
  an external scheduler that calls `POST /api/workflows/{id}/run`.
- **Stateless app tier**: JWTs are self-contained, so the API tier scales
  horizontally behind a load balancer once the DB is Postgres.
