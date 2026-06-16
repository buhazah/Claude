# Single image used for both services (MCP server + autopilot company).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code. Secrets are NOT copied — they're injected at runtime via env.
COPY . .

# Default command is overridden per-service in docker-compose.yml.
CMD ["python", "run.py", "--autopilot"]
