# JARVIS — notes for Claude Code

Production AI operating system. Modular monolith: one FastAPI process, cleanly
separated subsystems.

## Run / test
- Dev server: `./scripts/dev.sh` (http://localhost:8700)
- Tests: `python -m pytest` (hermetic; throwaway SQLite; no external LLM calls)
- Seed demo data: `python scripts/seed_examples.py`
- Docker: `docker compose up --build`

## Layout
- `server/` — backend (see `docs/DEVELOPER.md` for the full map)
  - `agents/` orchestrator + runtime + 23 agent definitions
  - `llm/` multi-provider router with cost/speed/quality scoring + fallback
  - `memory/` embeddings + semantic recall/decay/consolidation/reflection
  - `tools/` typed tool registry + sandboxed web/fs/shell/code/doc tools
  - `automation/` in-house cron parser + async workflow scheduler
  - `api/` FastAPI routers, one per domain
- `web/` — vanilla-JS SPA (no build step)
- `docs/` — architecture, API, deployment, developer, env, DB, security, troubleshooting

## Conventions (enforce in changes)
- Async I/O everywhere; config only via `server/config.py`.
- Validate all inputs (Pydantic for API, param schemas for tools).
- Ownership check (`row.user_id == user.id`) on every user-scoped resource.
- Timeouts on all external calls; best-effort paths (memory) never break responses.
- No secrets or model identifiers in commits/logs/artifacts.

## Adding things
Recipes for a new agent / tool / provider / endpoint are in `docs/DEVELOPER.md`.
Agents are pure data in `server/agents/definitions.py`.
