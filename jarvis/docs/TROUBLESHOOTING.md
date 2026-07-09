# Troubleshooting

## Chat replies "No LLM provider is configured"
No provider key is set. Add at least one (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GROQ_API_KEY`, …) to your environment/`.env` and restart.
Verify with `GET /api/analytics/status` — your provider should appear under
`llm_providers`. Everything else (auth, memory, tasks, UI) works without a key.

## "All candidate models failed"
Every configured provider errored. Common causes:
- Invalid or expired API key → check the key.
- Network egress blocked → the server must reach the provider's API host.
- The pinned model isn't available on your plan → remove the `agent`/model
  override or add another provider as fallback.
The error message includes the per-model failure reasons.

## Semantic search feels "lexical", not semantic
You're on the local fallback embedder (no embedding key). It does character-
n-gram matching — useful, but not true semantics. Set `OPENAI_API_KEY` or
`VOYAGE_API_KEY` (with `JARVIS_EMBEDDING_PROVIDER=auto`) for real semantic
recall. Existing memories are re-embedded lazily on next access.

## Voice: "Speech recognition unavailable"
Browser speech recognition needs Chrome or Edge (the Web Speech API). Firefox
and Safari have limited/no support. TTS falls back to the browser's speech
synthesis if `ELEVENLABS_API_KEY`/`ELEVENLABS_VOICE_ID` aren't set.

## Voice TTS returns 503
`ELEVENLABS_API_KEY` or `ELEVENLABS_VOICE_ID` is missing. Set both, or rely on
the automatic browser-synthesis fallback (no config needed).

## Workflows don't run on schedule
- Confirm the workflow is `enabled` and `schedule` is a valid 5-field cron
  (not `"manual"`). Check `next_run_at` in `GET /api/workflows`.
- The scheduler ticks every 30s and needs the process running continuously.
- With multiple app workers/replicas, run the scheduler in exactly one — see
  DEPLOYMENT.md. Otherwise a workflow may run more than once.
- Run it immediately to test: `POST /api/workflows/{id}/run`.

## 401 on every request
The access token expired and refresh failed (or `JARVIS_SECRET_KEY` changed —
which invalidates all tokens). Log in again. In production, always set a stable
`JARVIS_SECRET_KEY` so restarts don't invalidate sessions.

## 429 Too Many Requests
You hit the per-IP rate limit (`JARVIS_RATE_LIMIT_PER_MINUTE`, default 120/min).
Raise it, or throttle the client.

## Shell/Python tool says it's disabled
`JARVIS_ENABLE_SHELL_TOOL=false`. Set it to `true` if you trust the workload.

## Database is locked (SQLite)
SQLite allows one writer. Run a single uvicorn worker, or switch to Postgres
(`JARVIS_DATABASE_URL=postgresql+asyncpg://…`) for concurrent workers. WAL mode
(enabled by default) mitigates but doesn't eliminate this under heavy write
concurrency.

## Docker container is "unhealthy"
The healthcheck probes `/api/health`. Check logs: `docker logs jarvis`. Usual
causes are a bad `JARVIS_DATABASE_URL` or an unwritable `/data` volume.

## Port already in use
Another process holds 8700. Change `JARVIS_PORT` or the compose port mapping.

## Tests fail locally
Ensure dev deps are installed (`pip install -r requirements-dev.txt`). The
suite is hermetic (throwaway SQLite, no external calls); a failure usually
means a dependency version mismatch — check Python is 3.11+.
