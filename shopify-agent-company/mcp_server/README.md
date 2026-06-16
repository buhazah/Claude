# Local Shopify MCP server

Wraps the Shopify Admin GraphQL API and serves it as MCP tools over HTTP, so the
agent company can read/manage your store. **Your Admin token never leaves this
process** — it's not sent to the model or committed anywhere.

## Run it

```bash
# from shopify-agent-company/
source .venv/bin/activate
export SHOPIFY_STORE_DOMAIN=cvqpju-j0.myshopify.com
export SHOPIFY_ADMIN_TOKEN=shpat_your_fresh_token
python mcp_server/shopify_mcp.py
# -> Shopify MCP server for cvqpju-j0.myshopify.com on http://localhost:8000
```

(These two vars are also read from your `.env` if you `export $(grep -v '^#' .env | xargs)`.)

Then in another terminal, run the company — its `.env` already points
`SHOPIFY_MCP_URL=http://localhost:8000/mcp`:

```bash
python run.py "Audit conversion for the last 7 days"
python run.py --autopilot
```

## Tools served

Read-only: `get-shop-info`, `search_products`, `get-product`, `list-orders`,
`get-order`, `run-analytics-query`, `get-inventory-levels`.

Write (needs `write_products` scope on the token, and the agent's autonomy set to
`auto`): `update-product`.

## Token scopes

Start with read scopes only: `read_products`, `read_orders`, `read_inventory`,
`read_customers`, `read_reports`, `read_analytics`. Add `write_products` etc.
only when you graduate an agent to `auto`.
