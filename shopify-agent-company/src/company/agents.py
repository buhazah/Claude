"""The agent registry — the "general" part of the company.

To add an agent: append one AgentSpec below and drop a matching prompt file in
prompts/. The master can immediately delegate to it; no orchestration code
changes. Each spec declares which tools the agent may use (read-only by
default) so capability is explicit and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .settings import DEFAULT_MODEL, StoreConfig, read_prompt


@dataclass(frozen=True)
class AgentSpec:
    name: str                       # subagent id the master delegates to
    prompt_file: str                # file in prompts/ (without .md)
    description: str                # one line the master uses to pick this agent
    tools: list[str] = field(default_factory=list)   # allowed tool names
    can_mutate: bool = False        # if False, write/mutation tools are stripped
    model: str = DEFAULT_MODEL


# Shopify read tools every store-aware agent gets. Mutation tools are added
# only for agents with can_mutate=True (currently none — propose, don't execute).
SHOPIFY_READ = [
    "mcp__shopify__get-shop-info",
    "mcp__shopify__search_products",
    "mcp__shopify__get-product",
    "mcp__shopify__list-orders",
    "mcp__shopify__get-order",
    "mcp__shopify__run-analytics-query",
    "mcp__shopify__get-inventory-levels",
]
SHOPIFY_WRITE = [
    "mcp__shopify__update-product",
    "mcp__shopify__create-product",
]

REGISTRY: list[AgentSpec] = [
    AgentSpec(
        name="store",
        prompt_file="store_agent",
        description="Live store health: catalog, orders, traffic, conversion diagnosis.",
        tools=SHOPIFY_READ,
    ),
    AgentSpec(
        name="creative",
        prompt_file="creative_agent",
        description="Product-page copy and ad hooks/angles in the store's brand voice.",
        tools=SHOPIFY_READ,  # reads product attributes; publishing is gated separately
    ),
    AgentSpec(
        name="product_scout",
        prompt_file="product_scout",
        description="Find winning products and competitor angles via ad-research tools.",
        tools=["mcp__research__find_winning_products", "mcp__research__search_facebook_ads"],
    ),
    AgentSpec(
        name="finance",
        prompt_file="finance_agent",
        description="True margin after costs/ad spend; what to scale or cut.",
        tools=SHOPIFY_READ,
    ),
]


def _render(template: str, cfg: StoreConfig, roster: str = "") -> str:
    return (
        template.replace("{{STORE_PROFILE}}", cfg.profile_block())
        .replace("{{RULES}}", cfg.rules_block())
        .replace("{{BRAND_VOICE}}", cfg.brand_voice_block())
        .replace("{{ECONOMICS}}", cfg.economics_block())
        .replace("{{AGENT_ROSTER}}", roster)
    )


def active_specs(cfg: StoreConfig) -> list[AgentSpec]:
    enabled = set(cfg.enabled_agents)
    return [s for s in REGISTRY if s.name in enabled]


def build_subagents(cfg: StoreConfig):
    """Return {name: AgentDefinition} for every enabled agent."""
    from claude_agent_sdk import AgentDefinition

    subagents = {}
    for spec in active_specs(cfg):
        tools = list(spec.tools)
        if not spec.can_mutate:
            tools = [t for t in tools if t not in SHOPIFY_WRITE]
        subagents[spec.name] = AgentDefinition(
            description=spec.description,
            prompt=_render(read_prompt(spec.prompt_file), cfg),
            tools=tools,
            model=spec.model,
        )
    return subagents


def roster_text(cfg: StoreConfig) -> str:
    return "\n".join(f"- **{s.name}** — {s.description}" for s in active_specs(cfg))


def master_prompt(cfg: StoreConfig) -> str:
    return _render(read_prompt("master"), cfg, roster=roster_text(cfg))
