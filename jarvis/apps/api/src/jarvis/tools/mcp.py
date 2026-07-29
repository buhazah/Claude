"""MCP client — mounts external servers as tool namespaces.

This is the connector strategy. Rather than hand-writing an adapter per SaaS
product, Jarvis speaks Model Context Protocol and inherits whatever the
ecosystem already exposes: GitHub, Slack, Notion, Stripe, Gmail, and anything
someone writes tomorrow.

Two decisions worth stating:

* **A server is a namespace.** Its tools mount as ``<server>.<tool>``, so an
  existing grant like ``Grant("github.*", SENSITIVE)`` governs a whole server
  without enumerating its tools.
* **Imported tools do not get to pick their own permission tier.** The server
  describes what a tool *does*; Jarvis decides what that is allowed to cost.
  A remote server declaring everything ``SAFE`` must not be able to bypass the
  approval gate, so the tier is assigned locally from configuration, defaulting
  to ``SENSITIVE``.

Transport is JSON-RPC 2.0 over stdio, which is what MCP servers ship with.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from jarvis.kernel.errors import ConfigurationError
from jarvis.tools.registry import Permission, ToolRegistry

log = structlog.get_logger(__name__)

PROTOCOL_VERSION = "2024-11-05"
REQUEST_TIMEOUT_S = 30.0


@dataclass(slots=True)
class MCPServerConfig:
    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    # Local policy, not the server's opinion of itself.
    permission: Permission = Permission.SENSITIVE
    enabled: bool = True


class MCPClient:
    """A JSON-RPC client for one MCP server process."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 0
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        if not self.config.command:
            raise ConfigurationError(f"MCP server '{self.config.name}' has no command")

        import os

        self._process = await asyncio.create_subprocess_exec(
            *self.config.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **self.config.env},
        )
        await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "jarvis", "version": "0.1.0"},
            },
        )
        await self._notify("notifications/initialized", {})
        log.info("mcp_server_started", server=self.config.name)

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _send(self, message: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise ConfigurationError(f"MCP server '{self.config.name}' is not running")
        self._process.stdin.write(json.dumps(message).encode() + b"\n")
        await self._process.stdin.drain()

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        # One request at a time: stdio is a single stream and interleaving
        # would require correlating ids across concurrent readers.
        async with self._lock:
            if self._process is None or self._process.stdout is None:
                raise ConfigurationError(f"MCP server '{self.config.name}' is not running")

            self._next_id += 1
            request_id = self._next_id
            await self._send(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )

            while True:
                line = await asyncio.wait_for(self._process.stdout.readline(), REQUEST_TIMEOUT_S)
                if not line:
                    raise ConfigurationError(
                        f"MCP server '{self.config.name}' closed the connection"
                    )
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue  # servers sometimes log to stdout; skip noise
                if message.get("id") != request_id:
                    continue  # a notification arriving mid-request
                if error := message.get("error"):
                    raise ConfigurationError(f"{self.config.name}: {error.get('message', error)}")
                return dict(message.get("result", {}))

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._request("tools/list", {})
        return list(result.get("tools", []))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        # MCP returns content blocks; flatten the text ones, which is what a
        # model can actually consume.
        blocks = result.get("content", [])
        text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if result.get("isError"):
            return f"Tool reported an error: {text}"
        return text or json.dumps(result, default=str)

    async def stop(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()
        self._process = None


async def mount(client: MCPClient, registry: ToolRegistry) -> int:
    """Start a server and register its tools. Returns how many were mounted."""
    await client.start()
    mounted = 0

    for descriptor in await client.list_tools():
        remote_name = descriptor.get("name")
        if not remote_name:
            continue

        def make_caller(tool_name: str) -> Any:
            async def call(**arguments: Any) -> str:
                return await client.call_tool(tool_name, arguments)

            return call

        registry.register(
            f"{client.config.name}.{remote_name}",
            descriptor.get("description", f"{remote_name} via {client.config.name}"),
            make_caller(remote_name),
            parameters=descriptor.get("inputSchema", {"type": "object", "properties": {}}),
            # Local policy wins: the server does not choose its own blast radius.
            permission=client.config.permission,
            namespace=client.config.name,
        )
        mounted += 1

    log.info("mcp_tools_mounted", server=client.config.name, tools=mounted)
    return mounted


class MCPManager:
    """Owns the lifecycle of every configured MCP server."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._clients: dict[str, MCPClient] = {}

    @property
    def servers(self) -> dict[str, MCPClient]:
        return dict(self._clients)

    async def add(self, config: MCPServerConfig) -> int:
        """Mount a server. A failure disables that server, never the system."""
        if not config.enabled:
            return 0
        client = MCPClient(config)
        try:
            mounted = await mount(client, self._registry)
        except Exception as exc:
            log.warning("mcp_mount_failed", server=config.name, error=str(exc))
            await client.stop()
            return 0
        self._clients[config.name] = client
        return mounted

    async def stop_all(self) -> None:
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
