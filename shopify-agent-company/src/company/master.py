"""Builds and runs the company: the master agent plus its subagents."""

from __future__ import annotations

from .agents import build_subagents, master_prompt
from .mcp_servers import build_mcp_servers
from .settings import StoreConfig


def build_options(cfg: StoreConfig, *, shopify_url=None, shopify_token=None):
    """Assemble ClaudeAgentOptions for the whole company.

    `shopify_url`/`shopify_token` let the multi-tenant platform inject a
    specific customer's Shopify credentials per run.
    """
    from claude_agent_sdk import ClaudeAgentOptions

    subagents = build_subagents(cfg)
    mcp = build_mcp_servers(
        cfg.enabled_agents, shopify_url=shopify_url, shopify_token=shopify_token
    )

    # The master may use Task (to delegate) plus any tool its subagents use,
    # so delegated calls are permitted end to end.
    allowed: set[str] = {"Task"}
    for defn in subagents.values():
        allowed.update(defn.tools)

    return ClaudeAgentOptions(
        system_prompt=master_prompt(cfg),
        agents=subagents,
        mcp_servers=mcp,
        allowed_tools=sorted(allowed),
        permission_mode="default",
    )


async def run_task(cfg: StoreConfig, task: str) -> None:
    """Send one task to the master agent and stream the result to stdout."""
    from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, ResultMessage, TextBlock

    options = build_options(cfg)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
            elif isinstance(message, ResultMessage):
                print()


async def run_task_collect(
    cfg: StoreConfig, task: str, *, shopify_url=None, shopify_token=None
) -> str:
    """Run a task and return the master's final text (for the platform API)."""
    from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, TextBlock

    options = build_options(cfg, shopify_url=shopify_url, shopify_token=shopify_token)
    chunks: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
    return "".join(chunks)
