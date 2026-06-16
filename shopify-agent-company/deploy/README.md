# 24/7 deploy on a VPS

Runs the MCP server + autopilot as a Docker Compose stack, kept alive by
systemd across reboots and crashes.

## Prerequisites
- A Linux VPS (Ubuntu/Debian) with **Docker** + the **compose plugin**:
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```

## 1. Get the code + secrets onto the box
```bash
sudo git clone <your-repo-url> /opt/shopify-agent-company
cd /opt/shopify-agent-company/shopify-agent-company
cp .env.example .env
nano .env        # fill in the values below
```

`.env` must contain (these stay on the host, never in the image or git):
```
ANTHROPIC_API_KEY=sk-ant-...
SHOPIFY_STORE_DOMAIN=cvqpju-j0.myshopify.com
SHOPIFY_ADMIN_TOKEN=shpat_<fresh token>
SHOPIFY_MCP_URL=http://mcp:8000/mcp      # leave as-is; resolves inside compose
SHOPIFY_API_VERSION=2025-01
```

## 2. Smoke test before going unattended
```bash
docker compose build
# one-off read-only run, logs to your terminal:
docker compose run --rm company python run.py "Audit conversion for the last 7 days"
```
If that returns a sensible report, you're wired correctly.

## 3. Install the systemd service (24/7)
```bash
# point WorkingDirectory in the unit at this dir if you cloned elsewhere
sudo cp deploy/agent-company.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agent-company
```

## Operate it
```bash
systemctl status agent-company         # is it up?
docker compose logs -f company         # autopilot activity (scheduled jobs)
docker compose logs -f mcp             # Shopify connection
sudo systemctl restart agent-company   # after editing .env or config
sudo systemctl stop agent-company      # pause everything
```

## Change what it does
- **Schedule / autonomy:** edit `config/store.yaml`, then
  `sudo systemctl restart agent-company`.
- **Add another store:** run a second copy in a different dir with its own
  `.env` + `config/store.yaml`, or template the compose project name.

## Security
- Secrets live only in `.env` on the host (gitignored + dockerignored).
- The MCP server is `expose`d on the internal compose network only — it is **not**
  published to the public internet.
- Keep the box patched; restrict SSH. The Admin token grants whatever scopes you
  gave it, so prefer read-only scopes until you trust the autonomous agents.
