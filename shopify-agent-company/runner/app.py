"""Storepilot agent-runner API (multi-tenant).

The web app (Lovable + Supabase) calls this service to run agent work for a
specific customer. The operator runs ONE instance of this with a single
Anthropic key; each request carries a tenant id, and the runner loads that
tenant's brand profile + Shopify token from the tenant store.

Endpoints:
    GET  /health
    POST /tenants/{tenant_id}/run     body: {"task": "..."}  -> {"result": "..."}

Auth: requests must carry `X-Platform-Key` matching PLATFORM_API_KEY so only
your web app (not the public internet) can trigger runs.

Run:  uvicorn runner.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# make the engine importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from company.master import run_task_collect          # noqa: E402
from company.settings import store_config_from_dict   # noqa: E402

from .tenants import Tenant, default_store             # noqa: E402

app = FastAPI(title="Storepilot Agent Runner")
STORE = default_store()
PLATFORM_API_KEY = os.getenv("PLATFORM_API_KEY", "")
# The single Shopify MCP server the runner talks to; the per-tenant token is
# injected per request, so one MCP endpoint serves all tenants.
SHOPIFY_MCP_URL = os.getenv("SHOPIFY_MCP_URL", "http://localhost:8000/mcp")


class RunRequest(BaseModel):
    task: str


class InlineRunRequest(BaseModel):
    """Tenant data passed inline by the caller (e.g. a Lovable Cloud edge
    function that already read the store row server-side). Lets the runner work
    without any Supabase credentials of its own — secrets stay in the caller."""

    task: str
    shop_domain: str
    shopify_token: str
    brand_niche: str = ""
    brand_tone: str = ""
    target_market: str = "US"
    # agent_name -> {"enabled": bool, "autonomy": "advise|approve|auto", ...}
    agents: dict[str, dict] = {}


def _auth(provided: str | None) -> None:
    if not PLATFORM_API_KEY or provided != PLATFORM_API_KEY:
        raise HTTPException(status_code=401, detail="invalid platform key")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "storepilot-agent-runner"}


@app.post("/tenants/{tenant_id}/run")
async def run_for_tenant(
    tenant_id: str,
    body: RunRequest,
    x_platform_key: str | None = Header(default=None),
) -> dict:
    _auth(x_platform_key)
    try:
        tenant = STORE.get(tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="tenant not found")

    cfg = store_config_from_dict(tenant.to_store_config_dict())
    result = await run_task_collect(
        cfg,
        body.task,
        shopify_url=SHOPIFY_MCP_URL,
        shopify_token=tenant.shopify_token,
    )
    return {"tenant_id": tenant_id, "result": result}


@app.post("/run")
async def run_inline(
    body: InlineRunRequest,
    x_platform_key: str | None = Header(default=None),
) -> dict:
    """Run a task using tenant data passed in the request body. The caller
    (a Lovable Cloud edge function with server-side DB access) supplies the
    store's domain + Shopify token, so the runner needs no Supabase keys."""
    _auth(x_platform_key)
    tenant = Tenant(
        id=body.shop_domain,
        shop_domain=body.shop_domain,
        shopify_token=body.shopify_token,
        brand_niche=body.brand_niche,
        brand_tone=body.brand_tone,
        target_market=body.target_market,
        agents=body.agents,
    )
    cfg = store_config_from_dict(tenant.to_store_config_dict())
    result = await run_task_collect(
        cfg,
        body.task,
        shopify_url=SHOPIFY_MCP_URL,
        shopify_token=body.shopify_token,
    )
    return {"shop_domain": body.shop_domain, "result": result}
