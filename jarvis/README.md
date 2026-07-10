# JARVIS — Personal AI Operating System

A production-grade, self-hostable AI operating system: not a chatbot, but an
autonomous system that reasons, plans, remembers, uses tools, coordinates a
team of specialized agents, and runs automations while you're away.

<p align="center"><em>Reasoning · Long-term memory · 23 specialized agents · Master orchestrator · Tool use · Automations · Voice</em></p>

---

## What it does

- **Master orchestrator** decomposes each request, routes sub-tasks to the
  right specialists, runs them in dependency order, and synthesizes one answer.
- **23 specialized agents** (CEO, Research, Coding, Finance, Marketing, and
  more) — each with its own role, goals, tools, and reasoning loop.
- **Long-term memory** with semantic search, importance scoring, recency
  decay, consolidation, reflection, and summarization. JARVIS learns about
  you as you talk to it.
- **Tool use**: web search, web fetch, sandboxed filesystem, sandboxed shell,
  Python execution, and document generation — with schema-validated arguments.
- **Multi-provider LLM routing**: Anthropic, OpenAI, Google, Groq, DeepSeek,
  OpenRouter, and Ollama, auto-selected per task by cost, speed, quality, and
  context length, with automatic fallback.
- **Automation engine**: cron-scheduled autonomous workflows with run history.
- **Voice mode**: browser speech recognition + ElevenLabs TTS (with a browser
  fallback), streamed responses.
- **Full dashboard UI**: chat, voice, agents, Kanban tasks, memory browser,
  workflow builder, analytics, command palette, dark/light mode — responsive
  from desktop to mobile.
- **Production security**: JWT auth with refresh-token rotation, PBKDF2
  password hashing, role-based authorization, rate limiting, audit logging,
  and a path-confined execution sandbox.

## Deploy to the cloud (get a public URL, nothing to install)

**Render (recommended — includes a managed Postgres):**

1. Click **[Deploy to Render](https://render.com/deploy?repo=https://github.com/buhazah/Claude)**.
2. Render reads [`render.yaml`](render.yaml), builds `jarvis/`, and provisions a
   free Postgres. Signing key is auto-generated.
3. When prompted, paste your `ANTHROPIC_API_KEY` (and optionally the ElevenLabs
   voice vars). Deploy.
4. Open the service URL, create the first account (becomes owner), and set
   `JARVIS_ALLOW_REGISTRATION=false` to lock signups.

**Railway:** New Project → Deploy from GitHub → select this repo → set the
service **Root Directory** to `jarvis/` (it picks up [`railway.json`](jarvis/railway.json)).
Add a Postgres plugin and an `ANTHROPIC_API_KEY` variable.

Both honor the platform's `$PORT` and normalize the provided Postgres URL
automatically. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for details, other
platforms, and scaling.

## Run locally — one command

Requires **Python 3.11+** and **git**. The script does everything — creates an
isolated virtualenv, installs dependencies, asks for your `ANTHROPIC_API_KEY`
(paste it when prompted), seeds demo data, launches the server, and opens
<http://localhost:8700>. Log in with `demo@jarvis.app` / `demopassword123` or
create your own account. Press `Ctrl+C` to stop; re-run to start again.

**macOS / Linux** — paste into a terminal:

```bash
git clone -b claude/ai-os-jarvis-system-o2cdv5 https://github.com/buhazah/Claude.git && cd Claude/jarvis && bash scripts/quickstart.sh
```

**Windows** — paste into PowerShell:

```powershell
git clone -b claude/ai-os-jarvis-system-o2cdv5 https://github.com/buhazah/Claude.git; cd Claude\jarvis; powershell -ExecutionPolicy Bypass -File scripts\quickstart.ps1
```

Or, after cloning, just double-click **`jarvis\scripts\quickstart.bat`** in File
Explorer. (When installing Python, tick **"Add python.exe to PATH"**.)

## Quick start (Docker)

```bash
cd jarvis
cp .env.example .env          # add at least one LLM key (e.g. ANTHROPIC_API_KEY)
docker compose up --build
```

Open <http://localhost:8700>, create an account (the first user becomes owner),
and start talking to JARVIS.

## Quick start (local Python)

```bash
cd jarvis
pip install -r requirements-dev.txt
cp .env.example .env          # add an LLM key
python scripts/seed_examples.py   # optional: demo data
./scripts/dev.sh                  # or: uvicorn server.main:app --reload
```

Without any LLM key the app still boots, authenticates, stores memory, manages
tasks, and serves the UI — the reasoning endpoints return a clear "configure a
provider" message. Add `ANTHROPIC_API_KEY` (or any other provider) to light it
up. Embeddings and web search work with **no keys at all** (local hash
embedder + DuckDuckGo).

## Architecture at a glance

```
Browser SPA (web/)  ──HTTP/SSE──►  FastAPI (server/main.py)
                                      │
        ┌─────────────────────────────┼──────────────────────────────┐
        ▼                             ▼                               ▼
  Orchestrator                  Memory manager                  Automation engine
  (agents/orchestrator.py)      (memory/manager.py)             (automation/scheduler.py)
        │                             │                               │
        ▼                             ▼                               ▼
  Specialized agents  ──►  Model router (llm/router.py)  ──►  Providers (Anthropic, …)
  (agents/*.py)                       │
        │                             ▼
        └──►  Tool registry  ──►  Embeddings (memory/embeddings.py)
              (tools/*.py)
                                  SQLAlchemy async ORM  ──►  SQLite / Postgres
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

## Documentation

| Guide | What's inside |
|-------|---------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, memory model, orchestration |
| [API reference](docs/API.md) | Every endpoint, request/response shapes, the SSE stream |
| [Deployment](docs/DEPLOYMENT.md) | Docker, Postgres, cloud platforms, scaling, backups |
| [Developer guide](docs/DEVELOPER.md) | Add an agent, a tool, a provider; project layout |
| [Environment variables](docs/ENVIRONMENT.md) | Every setting and its default |
| [Database schema](docs/DATABASE.md) | Tables, columns, relationships |
| [Security](docs/SECURITY.md) | Auth, sandboxing, threat model, hardening |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and fixes |

## Testing

```bash
cd jarvis
python -m pytest        # 35 tests: security, memory, tools, cron, API
```

## Tech stack & why

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | FastAPI + async SQLAlchemy | Async-native, typed, production-proven, great streaming support |
| Persistence | SQLite → Postgres | Zero-config to start; swap one env var to scale out |
| Vector store | SQLAlchemy `LargeBinary` + NumPy cosine | No extra infra to run; swap in pgvector/Qdrant later without touching callers |
| Embeddings | OpenAI/Voyage with a local hash fallback | Works fully offline; upgrades to true semantics with a key |
| LLM access | Plain httpx per provider | No heavy SDK lock-in; one code path for all OpenAI-compatible hosts |
| Frontend | Vanilla JS + CSS SPA | No build step, instant load, trivially embeddable — the whole UI ships as static files |
| Auth | Stdlib JWT (HMAC) + PBKDF2 | Security-critical path with zero third-party surface |
| Scheduler | In-process async cron | No Celery/Redis needed for single-node; documented path to distributed |

Every decision favors **starting with zero external infrastructure** while
leaving a clear, documented upgrade path to a distributed production setup.

## License

MIT — see [LICENSE](LICENSE).
