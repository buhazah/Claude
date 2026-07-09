# Deployment Guide

JARVIS ships as a single container plus a persistent volume. It runs anywhere
that runs Docker, and on any PaaS that builds a Dockerfile.

## 1. Docker Compose (recommended)

```bash
cd jarvis
cp .env.example .env      # set JARVIS_SECRET_KEY and at least one LLM key
docker compose up --build -d
```

- App: <http://localhost:8700>
- Data persists in the `jarvis_data` named volume (`/data` in the container).
- Health: `curl localhost:8700/api/health`.

Always set a stable `JARVIS_SECRET_KEY` in production (otherwise a key is
generated and stored in the data volume; losing the volume invalidates
sessions). Generate one with `openssl rand -base64 48`.

## 2. Plain Docker

```bash
docker build -t jarvis:latest jarvis
docker run -d --name jarvis -p 8700:8700 \
  -e JARVIS_SECRET_KEY="$(openssl rand -base64 48)" \
  -e ANTHROPIC_API_KEY="sk-ant-…" \
  -v jarvis_data:/data \
  jarvis:latest
```

## 3. Bare metal / VM

```bash
cd jarvis
pip install -r requirements.txt
export JARVIS_SECRET_KEY=... ANTHROPIC_API_KEY=...
uvicorn server.main:app --host 0.0.0.0 --port 8700 --workers 1
```

Run it behind Nginx/Caddy for TLS. Use **one worker** unless you move to
Postgres — the in-process scheduler and SQLite assume a single process. With
Postgres you can add workers, but run the scheduler in exactly one of them (see
Scaling).

Example systemd unit:
```ini
[Unit]
Description=JARVIS
After=network.target

[Service]
WorkingDirectory=/opt/jarvis
EnvironmentFile=/opt/jarvis/.env
ExecStart=/usr/bin/uvicorn server.main:app --host 0.0.0.0 --port 8700
Restart=always
User=jarvis

[Install]
WantedBy=multi-user.target
```

## 4. One-click PaaS (Render / Railway / Fly.io / DigitalOcean)

The app binds to the platform-injected `$PORT` automatically and normalizes a
provided `postgres://`/`postgresql://` URL to the async driver at startup, so
managed Postgres "just works".

### Render (blueprint included)
[`render.yaml`](../../render.yaml) at the repo root defines the whole stack: a
Docker web service built from `jarvis/` plus a free managed Postgres.

1. Deploy: <https://render.com/deploy?repo=https://github.com/buhazah/Claude>
2. Render generates `JARVIS_SECRET_KEY` and wires `JARVIS_DATABASE_URL` from the
   database automatically.
3. Paste `ANTHROPIC_API_KEY` (and optional `ELEVENLABS_*`) when prompted.
4. Health check `/api/health` is preconfigured.

> Free Render Postgres is deleted after ~30 days — move to a paid instance for
> anything you want to keep. The free web service also sleeps when idle.

### Railway ([`railway.json`](../railway.json) included)
New Project → Deploy from GitHub → pick this repo → set the service **Root
Directory** to `jarvis/`. Add the Postgres plugin (Railway injects
`DATABASE_URL` — copy it into `JARVIS_DATABASE_URL`) and set `ANTHROPIC_API_KEY`.

### Fly.io / DigitalOcean / any Docker host
All build the Dockerfile directly. Configuration:
- The container listens on `$PORT` (falls back to 8700 for plain `docker run`).
- Add a persistent disk mounted at `/data` **or** use Postgres (recommended).
- Set env vars: `JARVIS_SECRET_KEY`, one LLM key, and any optional keys.
- Health check path: `/api/health`.

> **External Postgres requiring SSL**: the normalizer strips `sslmode` (asyncpg
> doesn't accept it as a query param). If your provider mandates TLS, pass it via
> `connect_args={"ssl": True}` in `create_async_engine` or use the provider's
> internal (same-network) connection string, which typically doesn't need it.

**Fly.io** example `fly.toml` snippet:
```toml
[env]
  JARVIS_PORT = "8080"
[[services]]
  internal_port = 8080
  [[services.http_checks]]
    path = "/api/health"
[mounts]
  source = "jarvis_data"
  destination = "/data"
```

## 5. Postgres (production database)

SQLite is fine for personal use. For durability and concurrency, use Postgres:

```bash
JARVIS_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/jarvis
```

Uncomment the `db` service and the `JARVIS_DATABASE_URL` line in
`docker-compose.yml`, and uncomment `asyncpg` in `requirements.txt`. Tables are
created automatically on first boot (`init_db`).

## Kubernetes

The image is stateless except for `/data`. A minimal setup:
- `Deployment` with 1 replica (or N replicas with Postgres + a single
  scheduler replica).
- `PersistentVolumeClaim` mounted at `/data` (only needed for SQLite/sandbox).
- `Service` + `Ingress` on port 8700.
- Liveness/readiness probe: `GET /api/health`.
- Secrets for API keys via a `Secret` mounted as env vars.

## Scaling

| Concern | Single node (default) | Scaled |
|---------|----------------------|--------|
| Database | SQLite in `/data` | Postgres (asyncpg) |
| Vector search | brute-force cosine in `memory/manager.py` | swap to pgvector/Qdrant behind the same interface |
| Scheduler | in-process 30s loop | run in one replica only, or call `/api/workflows/{id}/run` from an external scheduler |
| App tier | 1 uvicorn worker | N workers/replicas behind a load balancer (JWTs are stateless) |

## Backups

- **SQLite**: back up the `/data` volume (contains `jarvis.db*` and the
  sandbox). `sqlite3 jarvis.db ".backup backup.db"` for a hot copy.
- **Postgres**: standard `pg_dump`.
- The secret key lives in `/data/.secret_key` unless you set
  `JARVIS_SECRET_KEY` — set it explicitly so backups aren't security-sensitive.

## Post-deploy checklist

1. `GET /api/health` returns `200`.
2. `GET /api/analytics/status` lists your providers under `llm_providers`.
3. Register the first user (becomes `owner`); then set
   `JARVIS_ALLOW_REGISTRATION=false` to lock down signups.
4. Confirm TLS termination and that `JARVIS_CORS_ORIGINS` matches your domain.
