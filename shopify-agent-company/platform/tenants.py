"""Tenant model + storage interface for the multi-tenant platform.

A Tenant is one customer's store: their brand profile, per-agent autonomy, and
their Shopify Admin token. The web app (Lovable + Postgres) is the source of
truth; this module defines the shape the agent-runner needs and a storage
interface with two implementations:

  - InMemoryTenantStore  — for local dev/tests.
  - SupabaseTenantStore  — reads the Lovable Cloud (Supabase) Postgres tables.

The runner never trusts the network for secrets: tokens come from the tenant
store, and the operator's single Anthropic key comes from the runner's env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Tenant:
    id: str
    shop_domain: str
    shopify_token: str                      # the customer's Admin API token
    brand_niche: str = ""
    brand_tone: str = ""
    target_market: str = "US"
    # agent_name -> {"enabled": bool, "autonomy": "advise|approve|auto", "schedule_minutes": int}
    agents: dict[str, dict] = field(default_factory=dict)

    def to_store_config_dict(self) -> dict:
        """Translate a tenant row into the engine's StoreConfig dict shape."""
        return {
            "store": {
                "name": self.shop_domain.split(".")[0],
                "domain": self.shop_domain,
                "niche": self.brand_niche,
                "target_market": self.target_market,
            },
            "brand_voice": {"tone": self.brand_tone},
            "rules": [
                "Never publish changes or spend money without approval unless autonomy is 'auto'.",
                "When data is missing, say so — never fabricate numbers, products, or reviews.",
            ],
            "agents": {a: c.get("enabled", False) for a, c in self.agents.items()},
            "autonomy": {a: c.get("autonomy", "approve") for a, c in self.agents.items()},
        }


class TenantStore(Protocol):
    def get(self, tenant_id: str) -> Tenant: ...
    def due_jobs(self) -> list[tuple[Tenant, str, str]]: ...  # (tenant, agent_name, task)


class InMemoryTenantStore:
    """Simple store for local development and tests."""

    def __init__(self, tenants: dict[str, Tenant] | None = None):
        self._tenants = tenants or {}

    def add(self, tenant: Tenant) -> None:
        self._tenants[tenant.id] = tenant

    def get(self, tenant_id: str) -> Tenant:
        return self._tenants[tenant_id]

    def due_jobs(self) -> list[tuple[Tenant, str, str]]:
        # In-memory store has no scheduler; the platform DB drives scheduling.
        return []


def default_store() -> TenantStore:
    """Pick a tenant store based on env. Defaults to in-memory for safety."""
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"):
        from .supabase_store import SupabaseTenantStore  # lazy import

        return SupabaseTenantStore()
    return InMemoryTenantStore()
