.PHONY: install run test check format clean

install:
	uv venv && uv pip install -e ".[dev]"

run:
	.venv/bin/uvicorn ops.app:app --reload --port 8900

test:
	.venv/bin/python -m pytest -q

check:
	.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest -q

format:
	.venv/bin/ruff check --fix . && .venv/bin/ruff format .

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
