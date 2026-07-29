.PHONY: install test lint format types check e2e eval eval-plan eval-free eval-baseline eval-sample run clean

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

# All eight suites against one API started with everything they need. This is
# what CI runs. `JARVIS_BROWSER_EXECUTABLE` is only needed where a preinstalled
# Chromium does not match the version playwright expects — on a clean install,
# `playwright install chromium` puts one where it will be found and the setting
# can be left empty.
e2e-serve:
	cd $(API) && JARVIS_VAULT_KEY="$$(.venv/bin/python -m jarvis.security.keygen)" \
		JARVIS_ENABLE_COMPUTER=true JARVIS_BROWSER_ALLOWED_HOSTS='["127.0.0.1"]' \
		JARVIS_BROWSER_EXECUTABLE="$${CHROMIUM_PATH}" \
		.venv/bin/uvicorn jarvis.main:app

e2e-computer:
	cd $(WEB) && pnpm e2e:computer

e2e-settings:
	cd $(WEB) && pnpm e2e:settings

# Evaluate the intelligence layer. `eval-free` needs no key and spends nothing:
# routing is scored on stage one alone and memory recall runs against the store,
# which is most of the corpus and is what CI runs on every push.
eval-plan:
	cd $(API) && .venv/bin/python -m eval --dry-run

eval-free:
	cd $(API) && .venv/bin/python -m eval --free --no-probes \
		--baseline eval/baseline.json --out ../../eval-results.md

# Rewrite the committed floor. Only after reading what moved and agreeing with it.
eval-baseline:
	cd $(API) && .venv/bin/python -m eval --free --no-probes \
		--scorecard eval/baseline.json --note "$(note)"

# The whole corpus against a real model. Needs a provider key in the environment.
eval:
	cd $(API) && .venv/bin/python -m eval --budget $(or $(budget),5) \
		--out ../../eval-results.md --scorecard ../../eval-scorecard.json \
		$(if $(baseline),--baseline $(baseline),) $(if $(note),--note "$(note)",)

# A cheap representative pass: at most N cases per suite, spread across each.
eval-sample:
	cd $(API) && .venv/bin/python -m eval --budget $(or $(budget),2) \
		--sample $(or $(n),8) --out ../../eval-results.md

run-api:
	cd $(API) && .venv/bin/uvicorn jarvis.main:app --reload

run-web:
	cd $(WEB) && pnpm dev

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(API)/.pytest_cache $(API)/.mypy_cache $(API)/.ruff_cache $(WEB)/.next
