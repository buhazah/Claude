# JARVIS production image — slim, non-root, single stage (pure-Python deps).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    JARVIS_DATA_DIR=/data

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY server ./server
COPY web ./web

# Non-root runtime user; owns the data volume.
RUN useradd --create-home --uid 10001 jarvis \
    && mkdir -p /data \
    && chown -R jarvis:jarvis /app /data
USER jarvis

VOLUME ["/data"]
EXPOSE 8700

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8700'); sys.exit(0 if urllib.request.urlopen(f'http://localhost:{p}/api/health').status==200 else 1)"

# Shell form so ${PORT} (injected by Render/Railway/Heroku) is expanded;
# falls back to 8700 for plain `docker run`.
CMD uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8700}
