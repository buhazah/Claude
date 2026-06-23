# Storepilot Platform (multi-tenant SaaS)

Turns the single-store agent company into a product non-technical owners sign
up for. Two halves:

```
   ┌─────────────────────────────┐         ┌──────────────────────────────┐
   │   WEB APP  (Lovable)         │  calls  │  AGENT RUNNER  (this dir)    │
   │   - signup / login           │ ───────▶│  FastAPI, one Anthropic key  │
   │   - Connect Shopify (OAuth)  │         │  loads tenant + token, runs  │
   │   - dashboard + action queue │ ◀────── │  the agent company per call  │
   │   - Stripe billing           │ writes  │                              │
   │   Postgres (Supabase)  ◀─────┼─────────┤  reads stores/agents_config  │
   └─────────────────────────────┘         └──────────────────────────────┘
```

- **Web app** (built in Lovable): everything the customer sees. Owns auth,
  Shopify OAuth, the dashboard, Stripe billing, and the Postgres tables.
- **Agent runner** (`runner/`): the operator's single backend. Holds the one
  Anthropic key (customers never see it), loads a tenant's brand profile +
  Shopify token, and runs the agent company for that store.

## Why split this way
- **One Anthropic key, your margin.** Customers pay a subscription; you absorb
  model cost in the runner. No customer ever handles an API key.
- **Secrets stay server-side.** Shopify tokens live in Postgres (encrypted) and
  are only ever read by the runner via the service key — never sent to a browser.
- **Scales per tenant.** One runner serves many stores; each request injects that
  tenant's Shopify credentials.

## Run the runner

```bash
pip install -r requirements.txt -r runner/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export PLATFORM_API_KEY=$(openssl rand -hex 24)     # web app sends this header
export SUPABASE_URL=...                              # Lovable Cloud project
export SUPABASE_SERVICE_KEY=...                      # service role (server only)
export SHOPIFY_MCP_URL=http://localhost:8000/mcp     # the Shopify MCP server

uvicorn runner.app:app --host 0.0.0.0 --port 8080
```

Trigger a run (the web app does this when a customer clicks "Run audit", or a
scheduler fires):

```bash
curl -X POST http://localhost:8080/tenants/<store_id>/run \
  -H "X-Platform-Key: $PLATFORM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task":"Audit conversion for the last 7 days and give the top 3 fixes"}'
```

## Shopify OAuth (how "Connect Shopify" works — no API keys for the customer)

The customer never creates a token. Standard Shopify OAuth, handled by the web
app:

1. Customer clicks **Connect Shopify**, enters their store domain.
2. App redirects to
   `https://{shop}/admin/oauth/authorize?client_id={APP_KEY}&scope={SCOPES}&redirect_uri={CALLBACK}&state={nonce}`.
3. Customer approves in their own Shopify admin.
4. Shopify redirects back to the app's callback with a `code`.
5. The callback (a Supabase edge function) exchanges `code` for a permanent
   Admin API access token, **encrypts it**, and stores it on the `stores` row.
6. The runner later reads + decrypts that token to act on the store.

Requires a **Shopify Partner app** (client id/secret). Start with read scopes
(`read_products, read_orders, read_inventory, read_customers, read_reports,
read_analytics`); request `write_products` etc. only for customers who enable an
agent's `auto` autonomy.

## Scheduling (autopilot per tenant)
A small worker calls `TenantStore.due_jobs()` on an interval and POSTs each due
job to `/tenants/{id}/run`. `agents_config.schedule_minutes` drives cadence per
agent per store. Results write back to `activity_log`; anything needing approval
writes to `action_queue` for the dashboard.
