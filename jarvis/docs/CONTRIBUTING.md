# Contributing

Thanks for helping build JARVIS. This guide keeps changes consistent and safe.

## Setup
```bash
cd jarvis
pip install -r requirements-dev.txt
./scripts/dev.sh
python -m pytest
```

## Workflow
1. Branch from the default branch.
2. Make the change with a test that proves it.
3. Run `python -m pytest` — it must be green.
4. Keep the diff focused; match the surrounding style.
5. Open a PR describing the change and its rationale.

## Code standards
- **Async I/O only** for anything touching the DB, network, or subprocess.
- **Config through `server/config.py`** — never read `os.environ` elsewhere.
- **Validate inputs** with Pydantic (API) or tool param schemas (tools).
- **Enforce ownership** on every user-scoped resource.
- **Bound external calls** with timeouts.
- **No secrets in code, logs, commits, or the model-identifier in artifacts.**
- Docstrings explain *why*; keep comments about constraints, not narration.

## Adding capabilities
See `docs/DEVELOPER.md` for step-by-step recipes to add an agent, a tool, an
LLM provider, or an API endpoint. Each is designed to be a localized change.

## Tests
- Unit-test pure logic (security, cron, embeddings, tool validation).
- Integration-test API routes via the `auth_client` fixture.
- Never call real LLM providers in tests; assert graceful degradation instead.

## Reporting security issues
Do not open a public issue for vulnerabilities. Contact the maintainer directly
and allow time for a fix before disclosure.
