#!/usr/bin/env bash
# Local development launcher with auto-reload.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found — copying .env.example. Add an LLM key to enable reasoning."
  cp .env.example .env
fi

python3 -m pip install -q -r requirements-dev.txt
export JARVIS_DEBUG=true
echo "Starting JARVIS on http://localhost:${JARVIS_PORT:-8700}"
exec python3 -m uvicorn server.main:app --reload --host 0.0.0.0 --port "${JARVIS_PORT:-8700}"
