#!/usr/bin/env bash
# JARVIS one-command local setup. Does everything: checks prerequisites,
# installs into an isolated virtualenv, configures your API key, seeds demo
# data, launches the server, and opens your browser.
#
# Run from the jarvis/ directory:   bash scripts/quickstart.sh
set -euo pipefail

cd "$(dirname "$0")/.."
BOLD="\033[1m"; CYAN="\033[36m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; OFF="\033[0m"
say() { printf "${CYAN}▸${OFF} %s\n" "$1"; }
ok()  { printf "${GREEN}✓${OFF} %s\n" "$1"; }
warn(){ printf "${YELLOW}!${OFF} %s\n" "$1"; }

printf "${BOLD}\n  J A R V I S  —  local quickstart${OFF}\n\n"

# ---- 1. Python -------------------------------------------------------------
PY=""
for cand in python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    major=${ver%%.*}; minor=${ver##*.}
    if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then PY="$cand"; break; fi
  fi
done
if [ -z "$PY" ]; then
  printf "${RED}✗${OFF} Python 3.11+ is required but was not found.\n"
  echo "  Install it from https://www.python.org/downloads/ (or 'brew install python@3.12' on macOS), then re-run."
  exit 1
fi
ok "Using $($PY --version) at $(command -v $PY)"

# ---- 2. Virtualenv + deps --------------------------------------------------
if [ ! -d .venv ]; then
  say "Creating virtual environment (.venv)…"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
say "Installing dependencies (first run takes a minute)…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt
ok "Dependencies installed"

# ---- 3. Configuration ------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
fi

# Ensure an Anthropic key is present (the app runs without one, but chat needs it).
current_key=$(grep -E '^ANTHROPIC_API_KEY=' .env | cut -d= -f2- || true)
if [ -z "$current_key" ]; then
  echo
  warn "No ANTHROPIC_API_KEY set yet. Chat/reasoning needs one (get it at https://console.anthropic.com/)."
  printf "  Paste your Anthropic API key (or press Enter to skip and add it later): "
  read -r key < /dev/tty || key=""
  if [ -n "$key" ]; then
    # Portable in-place edit (macOS vs GNU sed).
    if sed --version >/dev/null 2>&1; then
      sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$key|" .env
    else
      sed -i '' "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$key|" .env
    fi
    ok "API key saved to .env"
  else
    warn "Skipped — you can edit .env later. The UI still works; chat will ask you to add a key."
  fi
fi

# ---- 4. Seed demo data -----------------------------------------------------
say "Seeding demo data (memories, tasks, automations)…"
python scripts/seed_examples.py >/dev/null 2>&1 && ok "Demo user ready: demo@jarvis.app / demopassword123" || warn "Seeding skipped (already present)"

# ---- 5. Launch -------------------------------------------------------------
PORT="${JARVIS_PORT:-8700}"
URL="http://localhost:${PORT}"
echo
ok "Starting JARVIS…"
printf "\n  ${BOLD}Open ${CYAN}%s${OFF}${BOLD} in your browser${OFF}\n" "$URL"
printf "  Log in with ${BOLD}demo@jarvis.app${OFF} / ${BOLD}demopassword123${OFF}, or create your own account.\n"
printf "  Press ${BOLD}Ctrl+C${OFF} to stop.\n\n"

# Open the browser shortly after the server comes up (best-effort, non-blocking).
( sleep 3
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1
  fi ) &

exec uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
