.PHONY: install test lint format types check run clean

API := apps/api
PY  := $(API)/.venv/bin

install:
	cd $(API) && uv venv && uv pip install -e ".[dev]"

test:
	cd $(API) && .venv/bin/python -m pytest -q

lint:
	cd $(API) && .venv/bin/ruff check . && .venv/bin/ruff format --check .

format:
	cd $(API) && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

types:
	cd $(API) && .venv/bin/mypy

check: lint types test

run:
	cd $(API) && .venv/bin/uvicorn jarvis.main:app --reload

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(API)/.pytest_cache $(API)/.mypy_cache $(API)/.ruff_cache
