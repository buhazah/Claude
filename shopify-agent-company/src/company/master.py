"""Builds and runs the company: the master agent plus its subagents."""

from __future__ import annotations

from .agents import build_subagents, master_prompt
from .mcp_servers import build_mcp_servers
from .settings import StoreConfig


def build_options(cfg: StoreConfig):
    """Assemble ClaudeAgentOptions for the whole company."""
    from claude_agent_sdk import ClaudeAgentOptions

    subagents = build_subagents(cfg)
    mcp = build_mcp_servers(cfg.enabled_agents)

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
    """Send one task to the master agent and stream the result."""
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
    )

    options = build_options(cfg)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
            elif isinstance(message, ResultMessage):
                print()  # trailing newline after the final answer
