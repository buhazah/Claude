# Single image used for all three services (MCP server, autopilot company, and
# the multi-tenant FastAPI runner).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching. Platform deps (FastAPI/uvicorn/supabase)
# are bundled so the same image can also serve the runner.
COPY requirements.txt ./requirements.txt
COPY platform/requirements.txt ./platform-requirements.txt
RUN pip install -r requirements.txt -r platform-requirements.txt

# App code. Secrets are NOT copied — they're injected at runtime via env.
COPY . .

# Default command is overridden per-service in docker-compose.yml.
CMD ["python", "run.py", "--autopilot"]
