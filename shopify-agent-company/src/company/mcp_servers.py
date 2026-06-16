"""MCP server wiring. Each store supplies its own endpoints/tokens via .env,
so the same code connects to any store's Shopify (and optional research/ad)
backends. Servers with no configured URL are simply skipped."""

from __future__ import annotations

import os
from typing import Any


def _http_server(url: str | None, token: str | None) -> dict[str, Any] | None:
    if not url:
        return None
    server: dict[str, Any] = {"type": "http", "url": url}
    if token:
        server["headers"] = {"Authorization": f"Bearer {token}"}
    return server


def build_mcp_servers(enabled_agents: list[str]) -> dict[str, Any]:
    """Return the MCP server map for the agents that are turned on.

    Keys here are referenced by tool names as ``mcp__<key>__<tool>`` in
    agents.py, so an agent only gets tools for servers it actually needs.
    """
    servers: dict[str, Any] = {}

    shopify = _http_server(os.getenv("SHOPIFY_MCP_URL"), os.getenv("SHOPIFY_MCP_TOKEN"))
    shopify_users = {"store", "creative", "finance", "support", "ads", "fulfillment", "retention"}
    if shopify and shopify_users & set(enabled_agents):
        servers["shopify"] = shopify

    research = _http_server(os.getenv("RESEARCH_MCP_URL"), os.getenv("RESEARCH_MCP_TOKEN"))
    if research and "product_scout" in enabled_agents:
        servers["research"] = research

    meta = _http_server(os.getenv("META_MCP_URL"), os.getenv("META_MCP_TOKEN"))
    if meta and "finance" in enabled_agents:
        servers["meta"] = meta

    return servers
