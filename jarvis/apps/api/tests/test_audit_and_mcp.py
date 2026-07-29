"""Audit chain, MCP client, and provider tool-call assembly."""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator

import httpx
import pytest

from jarvis.kernel.clock import FrozenClock
from jarvis.llm.base import CompletionRequest, Message, ModelSpec, Role, ToolCall
from jarvis.llm.providers.anthropic import AnthropicProvider
from jarvis.llm.providers.openai import OpenAIProvider
from jarvis.observability.audit import GENESIS, NullAuditLog, SqlAuditLog, entry_hash
from jarvis.persistence.db import Database
from jarvis.persistence.models import AuditRow
from jarvis.tools.mcp import MCPClient, MCPManager, MCPServerConfig, mount
from jarvis.tools.registry import Grant, Permission, ToolRegistry

# ── Audit log ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def audit(tmp_path, clock: FrozenClock) -> AsyncIterator[SqlAuditLog]:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/audit.db")
    await db.create_all()
    yield SqlAuditLog(db, clock=clock)
    await db.dispose()


async def test_entries_are_recorded_newest_first(audit: SqlAuditLog) -> None:
    await audit.record("tool.invoked", {"tool": "write_file"}, approved=True)
    await audit.record("tool.refused", {"tool": "run_command"}, approved=False)

    entries = await audit.entries()
    assert [e["topic"] for e in entries] == ["tool.refused", "tool.invoked"]
    assert entries[0]["approved"] is False
    assert entries[1]["payload"]["tool"] == "write_file"


async def test_the_chain_verifies_when_untouched(audit: SqlAuditLog) -> None:
    for i in range(5):
        await audit.record("tool.invoked", {"n": i})

    intact, broken = await audit.verify()
    assert intact is True
    assert broken is None


async def test_each_entry_chains_to_the_previous(audit: SqlAuditLog) -> None:
    first = await audit.record("a", {})
    await audit.record("b", {})

    entries = await audit.entries()
    assert entries[1]["id"] == first
    assert entries[0]["hash"] != entries[1]["hash"]
    assert len({e["hash"] for e in entries}) == 2


async def test_tampering_with_an_entry_breaks_the_chain(
    audit: SqlAuditLog, tmp_path, clock: FrozenClock
) -> None:
    """The property that makes the log worth having."""
    await audit.record("tool.invoked", {"command": "echo hi"})
    target = await audit.record("tool.invoked", {"command": "rm -rf /"})
    await audit.record("tool.invoked", {"command": "ls"})

    db = Database(f"sqlite+aiosqlite:///{tmp_path}/audit.db")
    async with db.session() as session:
        row = await session.get(AuditRow, target)
        assert row is not None
        # Rewrite history: make the dangerous command look innocuous.
        payload = dict(row.payload)
        payload["payload"] = {"command": "echo harmless"}
        row.payload = payload
        await session.commit()
    await db.dispose()

    intact, broken = await audit.verify()
    assert intact is False
    assert broken == target


async def test_deleting_an_entry_breaks_the_chain(audit: SqlAuditLog, tmp_path) -> None:
    await audit.record("a", {})
    middle = await audit.record("b", {})
    await audit.record("c", {})

    db = Database(f"sqlite+aiosqlite:///{tmp_path}/audit.db")
    async with db.session() as session:
        row = await session.get(AuditRow, middle)
        await session.delete(row)
        await session.commit()
    await db.dispose()

    intact, _ = await audit.verify()
    assert intact is False


async def test_an_empty_log_verifies(audit: SqlAuditLog) -> None:
    assert await audit.verify() == (True, None)


def test_hashing_is_deterministic_and_order_independent() -> None:
    a = entry_hash(GENESIS, {"topic": "x", "n": 1})
    b = entry_hash(GENESIS, {"n": 1, "topic": "x"})
    assert a == b
    assert a != entry_hash(GENESIS, {"topic": "x", "n": 2})


async def test_the_null_log_records_nothing_and_says_it_is_intact() -> None:
    log = NullAuditLog()
    assert await log.record("x", {}) == ""
    assert await log.entries() == []
    assert await log.verify() == (True, None)


async def test_sensitive_tool_calls_are_audited(tmp_path, clock: FrozenClock) -> None:
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/a.db")
    await db.create_all()
    log = SqlAuditLog(db, clock=clock)

    registry = ToolRegistry(grants=[Grant("*", Permission.SENSITIVE)], audit=log)
    registry.register("peek", "read something", lambda: "ok", permission=Permission.SAFE)
    registry.register("touch", "change something", lambda: "ok", permission=Permission.SENSITIVE)

    await registry.invoke("peek", {})
    await registry.invoke("touch", {})
    entries = await log.entries()
    await db.dispose()

    # Safe reads are not worth a durable row; consequential actions are.
    assert [e["payload"]["tool"] for e in entries] == ["touch"]


# ── MCP ───────────────────────────────────────────────────────────────────────

# A minimal but real MCP server: speaks JSON-RPC over stdio, exactly as the
# protocol specifies, so the client is exercised against the wire format rather
# than a mock of our own assumptions.
FAKE_SERVER = """
import json, sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method, request_id = message.get("method"), message.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "fake"}}
    elif method == "tools/list":
        result = {"tools": [
            {"name": "echo", "description": "Echo text back",
             "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}},
            {"name": "boom", "description": "Always errors", "inputSchema": {"type": "object"}},
        ]}
    elif method == "tools/call":
        params = message.get("params", {})
        if params.get("name") == "boom":
            result = {"content": [{"type": "text", "text": "it broke"}], "isError": True}
        else:
            text = params.get("arguments", {}).get("text", "")
            result = {"content": [{"type": "text", "text": f"echo: {text}"}]}
    else:
        continue  # notifications carry no id and expect no reply
    if request_id is not None:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\\n")
        sys.stdout.flush()
"""


@pytest.fixture
def fake_server(tmp_path) -> list[str]:
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_SERVER)
    return [sys.executable, str(script)]


async def test_mcp_tools_mount_under_the_server_namespace(fake_server) -> None:
    registry = ToolRegistry(grants=[Grant("*", Permission.SENSITIVE)])
    client = MCPClient(MCPServerConfig(name="fake", command=fake_server))

    mounted = await mount(client, registry)
    names = sorted(t.name for t in registry.all())
    await client.stop()

    assert mounted == 2
    assert names == ["fake.boom", "fake.echo"]
    assert registry.get("fake.echo").namespace == "fake"


async def test_an_mcp_tool_actually_calls_through(fake_server) -> None:
    registry = ToolRegistry(grants=[Grant("*", Permission.SENSITIVE)])
    client = MCPClient(MCPServerConfig(name="fake", command=fake_server))
    await mount(client, registry)

    result = await registry.invoke("fake.echo", {"text": "hello"})
    await client.stop()
    assert result == "echo: hello"


async def test_a_remote_tool_error_is_returned_not_raised(fake_server) -> None:
    registry = ToolRegistry(grants=[Grant("*", Permission.SENSITIVE)])
    client = MCPClient(MCPServerConfig(name="fake", command=fake_server))
    await mount(client, registry)

    result = await registry.invoke("fake.boom", {})
    await client.stop()
    assert "it broke" in result


async def test_the_server_does_not_choose_its_own_permission_tier(fake_server) -> None:
    """A remote server must not be able to talk its way past the approval gate."""
    registry = ToolRegistry(grants=[Grant("*", Permission.DANGEROUS)])
    client = MCPClient(
        MCPServerConfig(name="fake", command=fake_server, permission=Permission.DANGEROUS)
    )
    await mount(client, registry)
    await client.stop()

    assert registry.get("fake.echo").permission is Permission.DANGEROUS


async def test_a_namespace_grant_governs_a_whole_server(fake_server) -> None:
    registry = ToolRegistry(grants=[Grant("fake.*", Permission.SENSITIVE)])
    client = MCPClient(MCPServerConfig(name="fake", command=fake_server))
    await mount(client, registry)

    assert await registry.invoke("fake.echo", {"text": "x"}) == "echo: x"
    await client.stop()


async def test_a_broken_server_disables_itself_without_breaking_the_system() -> None:
    registry = ToolRegistry()
    manager = MCPManager(registry)

    mounted = await manager.add(MCPServerConfig(name="broken", command=["/nonexistent/binary"]))
    assert mounted == 0
    assert manager.servers == {}
    await manager.stop_all()


async def test_a_disabled_server_is_not_started(fake_server) -> None:
    manager = MCPManager(ToolRegistry())
    assert await manager.add(MCPServerConfig("fake", fake_server, enabled=False)) == 0


def test_server_config_parsing_skips_bad_entries() -> None:
    from jarvis.kernel.container import parse_mcp_servers

    servers = parse_mcp_servers(
        json.dumps(
            [
                {"name": "good", "command": ["echo"], "permission": "dangerous"},
                {"name": "no-command"},
                {"command": ["echo"]},
            ]
        )
    )
    assert [s.name for s in servers] == ["good"]
    assert servers[0].permission is Permission.DANGEROUS


def test_malformed_server_config_disables_connectors_not_jarvis() -> None:
    from jarvis.kernel.container import parse_mcp_servers

    assert parse_mcp_servers("not json at all") == []
    assert parse_mcp_servers("") == []


# ── Provider tool-call assembly ───────────────────────────────────────────────


def _sse(*events: dict) -> bytes:
    return b"".join(f"data: {json.dumps(e)}\n\n".encode() for e in events)


async def test_anthropic_assembles_fragmented_tool_arguments() -> None:
    """Arguments arrive as JSON fragments; a half-parsed call must never escape."""
    body = _sse(
        {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "tu_1", "name": "write_file"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"path": "a.'},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": 'txt", "content": "hi"}'},
        },
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "usage": {"output_tokens": 5}},
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    provider = AnthropicProvider("sk-test", client=httpx.AsyncClient(transport=transport))

    calls = [
        chunk.tool_call
        async for chunk in provider.stream(
            CompletionRequest(messages=[Message(role=Role.USER, content="hi")]),
            provider.models()[0],
        )
        if chunk.tool_call
    ]

    assert len(calls) == 1
    assert calls[0].name == "write_file"
    assert calls[0].arguments == {"path": "a.txt", "content": "hi"}


async def test_anthropic_survives_unparseable_tool_arguments() -> None:
    body = _sse(
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "tu_1", "name": "write_file"},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": "{not json"},
        },
        {"type": "content_block_stop", "index": 0},
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    provider = AnthropicProvider("sk-test", client=httpx.AsyncClient(transport=transport))

    calls = [
        chunk.tool_call
        async for chunk in provider.stream(
            CompletionRequest(messages=[Message(role=Role.USER, content="hi")]),
            provider.models()[0],
        )
        if chunk.tool_call
    ]
    assert calls[0].arguments == {}  # reported to the model, not an exception


async def test_openai_assembles_fragmented_tool_arguments() -> None:
    body = _sse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "function": {"name": "read_file", "arguments": '{"pa'},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [{"index": 0, "function": {"arguments": 'th": "b.txt"}'}}]
                    }
                }
            ]
        },
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    provider = OpenAIProvider("sk-test", client=httpx.AsyncClient(transport=transport))

    calls = [
        chunk.tool_call
        async for chunk in provider.stream(
            CompletionRequest(messages=[Message(role=Role.USER, content="hi")]),
            provider.models()[0],
        )
        if chunk.tool_call
    ]

    assert len(calls) == 1
    assert calls[0].id == "call_1"
    assert calls[0].arguments == {"path": "b.txt"}


def test_anthropic_replays_a_tool_exchange_in_its_own_shape() -> None:
    """Anthropic carries tool results as a user turn, not a distinct role."""
    provider = AnthropicProvider("sk-test")
    request = CompletionRequest(
        messages=[
            Message(role=Role.USER, content="read it"),
            Message(
                role=Role.ASSISTANT,
                content="looking",
                tool_calls=[ToolCall(id="tu_1", name="read_file", arguments={"path": "a"})],
            ),
            Message(role=Role.TOOL, content="file contents", tool_call_id="tu_1"),
        ]
    )
    payload = provider._payload(request, provider.models()[0], None)
    roles = [m["role"] for m in payload["messages"]]

    assert roles == ["user", "assistant", "user"]
    assistant_blocks = payload["messages"][1]["content"]
    assert {b["type"] for b in assistant_blocks} == {"text", "tool_use"}
    assert payload["messages"][2]["content"][0]["type"] == "tool_result"


def test_openai_replays_a_tool_exchange_in_its_own_shape() -> None:
    provider = OpenAIProvider("sk-test")
    request = CompletionRequest(
        messages=[
            Message(
                role=Role.ASSISTANT,
                content="",
                tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "a"})],
            ),
            Message(role=Role.TOOL, content="contents", tool_call_id="call_1"),
        ]
    )
    payload = provider._payload(request, provider.models()[0], None)

    assistant = payload["messages"][0]
    assert assistant["tool_calls"][0]["function"]["name"] == "read_file"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"path": "a"}
    assert payload["messages"][1]["tool_call_id"] == "call_1"


def test_model_specs_are_unchanged_by_tool_support() -> None:
    for provider in (AnthropicProvider("k"), OpenAIProvider("k")):
        assert all(isinstance(m, ModelSpec) and m.supports_tools for m in provider.models())
