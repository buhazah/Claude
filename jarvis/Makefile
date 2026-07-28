.PHONY: install test lint format types check e2e run clean

API := apps/api
WEB := apps/web

install:
	cd $(API) && uv venv && uv pip install -e ".[dev]"
	cd $(WEB) && pnpm install

test:
	cd $(API) && .venv/bin/python -m pytest -q
	cd $(WEB) && pnpm test

# Same suite, additionally against live Postgres and Redis. Backend-specific
# tests skip themselves when these are unset, so `make test` stays offline.
test-all:
	cd $(API) && JARVIS_TEST_POSTGRES_URL=postgresql+asyncpg://jarvis:jarvis@localhost/jarvis \
		JARVIS_TEST_REDIS_URL=redis://localhost:6379/0 .venv/bin/python -m pytest -q

migrate:
	cd $(API) && .venv/bin/alembic upgrade head

migration:
	cd $(API) && .venv/bin/alembic revision --autogenerate -m "$(m)"

lint:
	cd $(API) && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd $(WEB) && pnpm lint

format:
	cd $(API) && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

types:
	cd $(API) && .venv/bin/mypy
	cd $(WEB) && pnpm typecheck

check: lint types test

# Requires both servers running: `make run-api` and `make run-web` in separate shells.
e2e:
	cd $(WEB) && pnpm e2e:all

# Computer control is off by default, so its suite needs an API started with it
# on and a throwaway origin allowlisted:
#   JARVIS_ENABLE_COMPUTER=true JARVIS_BROWSER_ALLOWED_HOSTS='["127.0.0.1"]' \
#     uvicorn jarvis.main:app
e2e-computer:
	cd $(WEB) && pnpm e2e:computer

# The vault suite needs an API started with a key:
#   JARVIS_VAULT_KEY=$$(python -m jarvis.security.keygen) uvicorn jarvis.main:app
e2e-settings:
	cd $(WEB) && pnpm e2e:settings

run-api:
	cd $(API) && .venv/bin/uvicorn jarvis.main:app --reload

run-web:
	cd $(WEB) && pnpm dev

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(API)/.pytest_cache $(API)/.mypy_cache $(API)/.ruff_cache $(WEB)/.next
