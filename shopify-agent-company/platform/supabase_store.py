"""Supabase-backed tenant store.

Reads the same tables the Lovable web app writes (stores, agents_config) so the
agent-runner and the dashboard share one source of truth. Decrypts the stored
Shopify token. Requires SUPABASE_URL + SUPABASE_SERVICE_KEY (service role, kept
only on the runner — never shipped to the browser).

This is a thin implementation; flesh out queries to match your final schema.
"""

from __future__ import annotations

import os

from .tenants import Tenant


class SupabaseTenantStore:
    def __init__(self) -> None:
        from supabase import create_client  # lazy import

        self._db = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
        )

    def _decrypt(self, token: str) -> str:
        # The web app stores the Shopify token encrypted. Plug your KMS/secret
        # decryption here. Returned plaintext stays in-process only.
        return token

    def get(self, tenant_id: str) -> Tenant:
        store = (
            self._db.table("stores").select("*").eq("id", tenant_id).single().execute().data
        )
        cfgs = (
            self._db.table("agents_config")
            .select("*")
            .eq("store_id", tenant_id)
            .execute()
            .data
        )
        agents = {
            c["agent_name"]: {
                "enabled": c["enabled"],
                "autonomy": c["autonomy"],
                "schedule_minutes": c.get("schedule_minutes", 0),
            }
            for c in cfgs
        }
        return Tenant(
            id=tenant_id,
            shop_domain=store["shop_domain"],
            shopify_token=self._decrypt(store["encrypted_access_token"]),
            brand_niche=store.get("brand_niche", ""),
            brand_tone=store.get("brand_tone", ""),
            target_market=store.get("target_market", "US"),
            agents=agents,
        )

    def due_jobs(self) -> list[tuple[Tenant, str, str]]:
        # A scheduler worker queries agents_config for due rows and emits
        # (tenant, agent_name, task). Left as an extension point.
        return []
