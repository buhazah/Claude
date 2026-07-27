.PHONY: install test lint format types check e2e run clean

API := apps/api
WEB := apps/web

install:
	cd $(API) && uv venv && uv pip install -e ".[dev]"
	cd $(WEB) && pnpm install

test:
	cd $(API) && .venv/bin/python -m pytest -q
	cd $(WEB) && pnpm test

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
	cd $(WEB) && pnpm e2e

run-api:
	cd $(API) && .venv/bin/uvicorn jarvis.main:app --reload

run-web:
	cd $(WEB) && pnpm dev

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(API)/.pytest_cache $(API)/.mypy_cache $(API)/.ruff_cache $(WEB)/.next
