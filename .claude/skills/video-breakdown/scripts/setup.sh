#!/usr/bin/env bash
# Idempotent setup for the video-breakdown skill.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
READY=true

echo "=== video-breakdown skill setup ==="

# 1. Check ffmpeg
if command -v ffmpeg &>/dev/null; then
    echo "[OK]   ffmpeg found: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "[NEED] ffmpeg is not installed."
    echo "       Linux:  sudo apt install -y ffmpeg"
    echo "       macOS:  brew install ffmpeg"
    READY=false
fi

# 2. Python venv
if [ ! -d ".venv" ]; then
    echo "[...] Creating Python virtual environment..."
    python3 -m venv .venv || {
        echo "[NEED] Could not create venv. Install python3-venv:"
        echo "       sudo apt install python3-venv"
        READY=false
    }
fi

if [ -d ".venv" ]; then
    echo "[OK]   Virtual environment ready."
    echo "[...] Installing Python dependencies..."
    .venv/bin/pip install --upgrade pip -q
    .venv/bin/pip install -r "$SKILL_DIR/requirements.txt" -q
    echo "[OK]   Dependencies installed."
fi

# 3. .env file
if [ ! -f ".env" ]; then
    echo "GEMINI_API_KEY=your_key_here" > .env
    echo "[NEED] .env created. Add your Gemini API key:"
    echo "       Get one at: https://aistudio.google.com/apikey"
    echo "       Then set:   GEMINI_API_KEY=<your-key>  in .env"
    READY=false
elif grep -q "your_key_here" .env; then
    echo "[NEED] Replace 'your_key_here' in .env with your actual Gemini API key."
    READY=false
else
    echo "[OK]   .env found with API key."
fi

# 4. .gitignore safety
for entry in ".env" ".venv" "*.mp4" "__pycache__/"; do
    if ! grep -qF "$entry" .gitignore 2>/dev/null; then
        echo "$entry" >> .gitignore
    fi
done
echo "[OK]   .gitignore updated."

echo ""
if $READY; then
    echo "READY: environment is set up."
    echo "Run an analysis with:"
    echo "  .venv/bin/python $SKILL_DIR/scripts/analyze.py \"<VIDEO_URL>\""
else
    echo "INCOMPLETE: resolve the [NEED] items above, then re-run this script."
fi
