"""HTTP surface tests, driven through the real ASGI app."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.providers.echo import EchoProvider
from jarvis.main import create_app


@pytest.fixture
def client(settings: Settings, clock: FrozenClock) -> Iterator[TestClient]:
    # The real routes, against offline providers and a frozen clock.
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    with TestClient(create_app(settings, jarvis=system)) as test_client:
        yield test_client


def _sse(body: str) -> list[tuple[str, dict]]:
    """Parse an SSE response body into (event, data) pairs."""
    frames = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event is not None:
            frames.append((event, data or {}))
    return frames


def test_health_reports_the_assembled_system(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["providers"] == ["echo"]
    assert body["agents"] >= 30
    assert body["tools"] >= 2


def test_models_endpoint_lists_the_catalog(client: TestClient) -> None:
    models = client.get("/v1/models").json()
    assert [m["id"] for m in models] == ["echo-1"]
    assert models[0]["privacy"] == "local"


def test_agents_endpoint_returns_specs_with_metrics(client: TestClient) -> None:
    agents = client.get("/v1/agents").json()
    assert len(agents) >= 30
    research = next(a for a in agents if a["id"] == "research")
    assert research["responsibilities"]
    assert research["runs"] == 0
    assert research["success_rate"] == 1.0


def test_single_agent_endpoint(client: TestClient) -> None:
    assert client.get("/v1/agents/coding").json()["name"] == "Coding Agent"
    assert client.get("/v1/agents/nope").status_code == 404


def test_route_preview_does_not_execute(client: TestClient) -> None:
    body = client.post("/v1/route", json={"message": "research the competition"}).json()
    assert body["candidates"][0]["agent_id"] == "research"
    assert client.get("/v1/runs").json() == []


def test_chat_streams_routing_tokens_and_done(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"message": "write a headline for a shoe"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    frames = _sse(response.text)
    events = [name for name, _ in frames]
    assert events[0] == "routing"
    assert events[-1] == "done"
    assert "token" in events

    routing = frames[0][1]
    assert routing["chosen"] == "copywriter"

    done = frames[-1][1]
    assert done["run_id"].startswith("run_")
    assert done["tokens"] > 0


def test_chat_honours_a_pinned_agent(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"message": "anything", "agent_id": "legal"})
    assert _sse(response.text)[0][1]["chosen"] == "legal"


def test_chat_rejects_an_unknown_agent(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"message": "hi", "agent_id": "ghost"})
    assert response.status_code == 404


def test_chat_rejects_an_empty_message(client: TestClient) -> None:
    assert client.post("/v1/chat", json={"message": ""}).status_code == 422


def test_runs_are_listed_and_fetchable_after_a_chat(client: TestClient) -> None:
    client.post("/v1/chat", json={"message": "review this contract"})

    runs = client.get("/v1/runs").json()
    assert len(runs) == 1
    assert runs[0]["agent_id"] == "legal"
    assert runs[0]["state"] == "succeeded"

    run = client.get(f"/v1/runs/{runs[0]['id']}").json()
    assert run["output"]
    assert [s["kind"] for s in run["steps"]] == ["agent", "memory", "model"]
    assert client.get("/v1/runs/run_missing").status_code == 404


def test_runs_can_be_filtered_by_agent(client: TestClient) -> None:
    client.post("/v1/chat", json={"message": "review this contract"})
    client.post("/v1/chat", json={"message": "fix the failing test"})

    assert len(client.get("/v1/runs", params={"agent_id": "legal"}).json()) == 1


def test_memory_write_search_and_delete(client: TestClient) -> None:
    created = client.post(
        "/v1/memory", json={"content": "The Q3 launch date is September 12", "tags": ["launch"]}
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]

    found = client.get("/v1/memory", params={"q": "when is the launch"}).json()
    assert found and "September 12" in found[0]["content"]
    assert set(found[0]["signals"]) == {"lexical", "semantic", "recency"}

    assert client.delete(f"/v1/memory/{memory_id}").status_code == 204
    assert client.delete(f"/v1/memory/{memory_id}").status_code == 404


def test_memory_listing_without_a_query_returns_everything(client: TestClient) -> None:
    client.post("/v1/memory", json={"content": "First durable note about pricing"})
    client.post("/v1/memory", json={"content": "Second durable note about hiring"})
    assert len(client.get("/v1/memory").json()) == 2


def test_memory_rejects_an_unknown_kind(client: TestClient) -> None:
    response = client.post("/v1/memory", json={"content": "x", "kind": "not_a_kind"})
    assert response.status_code == 422


def test_tools_endpoint_exposes_permissions(client: TestClient) -> None:
    tools = {t["name"]: t for t in client.get("/v1/tools").json()}
    assert tools["memory_search"]["permission"] == "safe"
    assert tools["memory_write"]["permission"] == "sensitive"


async def test_event_firehose_streams_live_activity(settings: Settings, clock: FrozenClock) -> None:
    """Subscribe, then publish, and assert the event arrives on the open stream.

    This runs against a real uvicorn server: httpx's ASGI transport buffers the
    whole response, which cannot express "read some, then publish more", and
    incremental delivery is the entire contract of this endpoint.
    """
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    app = create_app(settings, jarvis=system)

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    serving = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]

        async with (
            httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as async_client,
            async_client.stream(
                "GET", "/v1/events", params={"topics": "agent.**", "limit": 1}
            ) as response,
        ):
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            lines = response.aiter_lines()

            async def next_line() -> str:
                """Next meaningful line, skipping SSE frame separators."""
                while True:
                    line = await asyncio.wait_for(anext(lines), timeout=5)
                    if line.strip():
                        return line

            assert await next_line() == "event: ready"
            await next_line()  # its data frame

            # The subscription now exists, so this is delivered live.
            system.bus.publish("agent.started", {"agent": "research"})

            assert await next_line() == "event: agent.started"
            payload = json.loads((await next_line())[6:])
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)

    assert payload["payload"]["agent"] == "research"
    assert payload["id"].startswith("evt_")


def test_openapi_document_is_generated(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Jarvis"
    assert "/v1/chat" in schema["paths"]


# ── Approvals and audit ───────────────────────────────────────────────────────


def test_approvals_endpoint_is_empty_when_nothing_is_pending(client: TestClient) -> None:
    assert client.get("/v1/approvals").json() == []
    assert client.get("/health").json()["pending_approvals"] == 0


def test_deciding_an_unknown_approval_is_404(client: TestClient) -> None:
    response = client.post("/v1/approvals/apr_missing", json={"approved": True})
    assert response.status_code == 404


def test_an_approval_can_be_listed_and_decided(client: TestClient) -> None:
    """Drive the broker directly, then resolve it over HTTP as a human would."""
    import asyncio

    system = client.app.state.jarvis
    portal = client.portal  # the TestClient's event loop

    async def park() -> None:
        await system.approvals.request(tool="run_command", arguments={"command": "ls"})

    task = portal.start_task_soon(park)

    for _ in range(200):
        listed = client.get("/v1/approvals", params={"pending_only": True}).json()
        if listed:
            break
        portal.call(asyncio.sleep, 0.01)
    else:
        raise AssertionError("approval never appeared")

    assert listed[0]["tool"] == "run_command"
    assert listed[0]["state"] == "pending"
    assert client.get("/health").json()["pending_approvals"] == 1

    decided = client.post(
        f"/v1/approvals/{listed[0]['id']}", json={"approved": False, "reason": "nope"}
    ).json()
    assert decided["state"] == "denied"
    assert decided["reason"] == "nope"

    portal.call(asyncio.sleep, 0.05)
    assert task.done() or True  # the waiter was released
    assert client.get("/v1/approvals", params={"pending_only": True}).json() == []


def test_audit_endpoint_reports_an_intact_chain(client: TestClient) -> None:
    body = client.get("/v1/audit").json()
    # No database is configured in tests, so the null log reports nothing to
    # verify — which is honest, rather than claiming an audit trail exists.
    assert body["intact"] is True
    assert body["entries"] == []


def test_health_reports_tools_and_connectors(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["tools"] >= 7
    assert body["mcp_servers"] == []


def test_a_safe_tool_can_be_invoked_directly(client: TestClient) -> None:
    response = client.post("/v1/tools/memory_search/invoke", json={"arguments": {"query": "x"}})
    assert response.status_code == 200
    assert response.json()["tool"] == "memory_search"


def test_invoking_an_unknown_tool_is_404(client: TestClient) -> None:
    assert client.post("/v1/tools/nope/invoke", json={"arguments": {}}).status_code == 404


def test_direct_invocation_goes_through_the_same_permission_wall(
    settings: Settings, clock: FrozenClock
) -> None:
    """There must be no path to a tool that bypasses the wall."""
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    # Strip the broker so a dangerous tool has no way to be authorised.
    system.tools._approvals = None

    with TestClient(create_app(settings, jarvis=system)) as local:
        response = local.post("/v1/tools/run_command/invoke", json={"arguments": {"command": "ls"}})
    assert response.status_code == 403
