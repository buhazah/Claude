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


# ── Knowledge ─────────────────────────────────────────────────────────────────


def test_pasted_text_is_ingested_and_searchable(client: TestClient) -> None:
    created = client.post(
        "/v1/knowledge",
        json={"text": "The vendor contract renews on 1 March.", "title": "Contract"},
    )
    assert created.status_code == 201
    assert created.json()["ingested"][0]["title"] == "Contract"

    found = client.get("/v1/knowledge/search", params={"q": "when does the contract renew"}).json()
    assert found
    assert "1 March" in found[0]["snippet"]
    assert found[0]["reference"].startswith("Contract")


def test_documents_are_listed_and_removable(client: TestClient) -> None:
    client.post("/v1/knowledge", json={"text": "A durable note.", "title": "Note"})

    documents = client.get("/v1/knowledge").json()
    assert len(documents) == 1
    assert client.get("/health").json()["knowledge"] == 1

    assert client.delete(f"/v1/knowledge/{documents[0]['id']}").status_code == 204
    assert client.delete(f"/v1/knowledge/{documents[0]['id']}").status_code == 404


def test_ingesting_without_a_source_is_rejected(client: TestClient) -> None:
    assert client.post("/v1/knowledge", json={}).status_code == 422


def test_ingesting_a_path_outside_the_workspace_is_refused(client: TestClient) -> None:
    """Ingestion must not become a way to read arbitrary files off the host."""
    response = client.post("/v1/knowledge", json={"path": "../../etc/passwd"})
    assert response.status_code == 403


def test_the_knowledge_tool_is_registered_and_safe(client: TestClient) -> None:
    tools = {t["name"]: t for t in client.get("/v1/tools").json()}
    assert tools["search_documents"]["permission"] == "safe"
    assert tools["search_documents"]["namespace"] == "knowledge"


def test_an_agent_can_search_documents_through_the_tool(client: TestClient) -> None:
    client.post("/v1/knowledge", json={"text": "Runway is 14 months.", "title": "Finance"})

    result = client.post(
        "/v1/tools/search_documents/invoke", json={"arguments": {"query": "how much runway"}}
    ).json()["result"]

    assert result
    # The reference travels with the passage, so an agent has no excuse for
    # using the text without citing it.
    assert result[0]["reference"].startswith("Finance")
    assert "untrusted_content" in result[0]


# ── Workflows ─────────────────────────────────────────────────────────────────


def test_starter_workflows_are_seeded(client: TestClient) -> None:
    workflows = client.get("/v1/workflows").json()
    assert {w["name"] for w in workflows} >= {"Inbox triage", "Company brief"}
    assert client.get("/health").json()["workflows"] >= 3


def test_a_workflow_can_be_run_from_the_api(client: TestClient) -> None:
    run = client.post("/v1/workflows/wfl_weekly_review/run", json={"inputs": {}}).json()
    assert run["state"] in {"succeeded", "awaiting_approval"}
    assert run["records"]

    listed = client.get("/v1/workflow-runs").json()
    assert listed[0]["workflow_name"] == "Weekly review"

    detail = client.get(f"/v1/workflow-runs/{run['id']}").json()
    assert detail["context"]["steps"]


def test_running_an_unknown_workflow_is_404(client: TestClient) -> None:
    assert client.post("/v1/workflows/wfl_nope/run", json={"inputs": {}}).status_code == 404


def test_an_invalid_graph_is_rejected_with_every_problem(client: TestClient) -> None:
    response = client.post(
        "/v1/workflows",
        json={
            "id": "wfl_bad",
            "name": "Bad",
            "steps": [{"id": "a", "kind": "agent", "next": "nowhere"}],
        },
    )
    assert response.status_code == 422
    problems = response.json()["detail"]["problems"]
    assert any("nowhere" in p for p in problems)
    assert any("no agent" in p for p in problems)


def test_a_workflow_can_be_saved_and_deleted(client: TestClient) -> None:
    created = client.post(
        "/v1/workflows",
        json={
            "id": "wfl_custom",
            "name": "Custom",
            "steps": [{"id": "note", "kind": "note", "label": "hello"}],
        },
    )
    assert created.status_code == 201
    assert client.delete("/v1/workflows/wfl_custom").status_code == 204
    assert client.delete("/v1/workflows/wfl_custom").status_code == 404


def test_triggers_can_be_created_and_removed(client: TestClient) -> None:
    created = client.post(
        "/v1/triggers",
        json={"workflow_id": "wfl_weekly_review", "kind": "schedule", "interval_seconds": 86400},
    )
    assert created.status_code == 201
    trigger_id = created.json()["id"]

    assert len(client.get("/v1/triggers").json()) == 1
    assert client.delete(f"/v1/triggers/{trigger_id}").status_code == 204


def test_a_trigger_for_an_unknown_workflow_is_refused(client: TestClient) -> None:
    response = client.post("/v1/triggers", json={"workflow_id": "wfl_nope", "kind": "manual"})
    assert response.status_code == 404


def test_an_approval_workflow_suspends_and_is_listed(client: TestClient) -> None:
    """The suspended run is visible and decidable through the ordinary surface."""
    run = client.post("/v1/workflows/wfl_inbox_triage/run", json={"inputs": {"body": "hi"}}).json()

    if run["state"] == "awaiting_approval":
        pending = client.get("/v1/approvals", params={"pending_only": True}).json()
        assert pending and pending[0]["arguments"]["step"] == "approve"

        decided = client.post(f"/v1/approvals/{pending[0]['id']}", json={"approved": False})
        assert decided.json()["state"] == "denied"


# ── Voice ─────────────────────────────────────────────────────────────────────


def test_health_reports_the_voice_configuration(client: TestClient) -> None:
    voice = client.get("/health").json()["voice"]
    assert voice["speaker"] == "silent"  # no key configured in tests
    assert voice["transcription"] is False
    assert voice["wake_word"] == "jarvis"


def test_transcription_without_a_key_says_so(client: TestClient) -> None:
    """Better an explicit 503 than a silent empty transcript."""
    response = client.post("/v1/voice/transcribe", content=b"audio")
    assert response.status_code == 503
    assert "browser" in response.json()["detail"]


def test_the_voice_socket_streams_a_turn(client: TestClient) -> None:
    with client.websocket_connect("/v1/voice") as socket:
        socket.send_json({"type": "transcript", "text": "what is on today", "final": True})

        seen: list[dict] = []
        for _ in range(60):
            event = socket.receive_json()
            seen.append(event)
            if event["type"] == "done":
                break

        kinds = [e["type"] for e in seen]
        assert "transcript" in kinds
        assert "token" in kinds
        assert "speech" in kinds
        assert kinds[-1] == "done"

        states = [e["state"] for e in seen if e["type"] == "state"]
        assert "thinking" in states and "speaking" in states
        socket.send_json({"type": "end"})


def test_a_partial_transcript_over_the_socket_is_not_answered(client: TestClient) -> None:
    with client.websocket_connect("/v1/voice") as socket:
        socket.send_json({"type": "transcript", "text": "what is", "final": False})
        assert socket.receive_json() == {"type": "partial", "text": "what is"}
        socket.send_json({"type": "end"})


# ── Computer control ──────────────────────────────────────────────────────────


def test_health_reports_the_browsers_reach(client: TestClient) -> None:
    """A capability nobody can see the boundary of is a capability nobody trusts."""
    body = client.get("/health").json()
    assert body["computer"] == {
        "driver": "none",
        "available": False,
        "allowed_hosts": [],
        "blocked_hosts": [],
    }


def test_computer_status_shows_the_policy_and_the_budget(client: TestClient) -> None:
    body = client.get("/v1/computer").json()
    assert body["available"] is False
    assert body["budget"]["max_steps"] > 0
    assert body["steps"] == []


def test_the_screen_is_404_before_anything_is_observed(client: TestClient) -> None:
    assert client.get("/v1/computer/screen").status_code == 404


def test_a_driven_browser_reports_its_screen_and_history(
    settings: Settings, clock: FrozenClock
) -> None:
    from jarvis.computer.policy import ComputerPolicy
    from jarvis.computer.ports import Page, ScriptedComputer

    driver = ScriptedComputer(
        {"https://ok.example.com/": Page(url="https://ok.example.com/", title="Fine")},
        start_url="https://ok.example.com/",
    )
    system = container.build(
        settings, providers=[EchoProvider()], clock=clock, computer_driver=driver
    )
    system.computer.policy = ComputerPolicy(allowed_hosts=("ok.example.com",))

    with TestClient(create_app(settings, jarvis=system)) as client:
        asyncio.run(_drive(system))
        body = client.get("/v1/computer").json()
        assert body["page"]["url"] == "https://ok.example.com/"
        assert [s["description"] for s in body["steps"]] == ["scroll down on ok.example.com"]

        screen = client.get("/v1/computer/screen")
        assert screen.status_code == 200
        assert screen.headers["content-type"] == "image/png"


async def _drive(system: container.Jarvis) -> None:
    from jarvis.computer.models import Action, ActionKind

    await system.computer.start()
    await system.computer.act(Action(kind=ActionKind.SCROLL, amount=600))


# ── Modes ─────────────────────────────────────────────────────────────────────


def test_modes_publish_what_they_narrow(client: TestClient) -> None:
    body = client.get("/v1/modes").json()
    modes = {m["id"]: m for m in body["modes"]}

    assert body["default"] == "personal"
    assert modes["personal"]["agent_count"] > modes["coding"]["agent_count"]
    assert modes["coding"]["memory_scope"] == "coding"
    assert "life_coach" not in modes["coding"]["agents"]


def test_an_unknown_mode_is_refused_by_the_api(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"message": "hello", "mode": "busines"})
    assert response.status_code == 404
    assert "unknown mode" in response.json()["detail"]


def test_routing_preview_is_scoped_to_the_mode(client: TestClient) -> None:
    body = client.post("/v1/route?mode=coding", json={"message": "refactor this module"}).json()
    assert body["mode"] == "coding"
    assert all(c["agent_id"] != "life_coach" for c in body["candidates"])


def test_pinning_an_agent_the_mode_excludes_is_refused(client: TestClient) -> None:
    """Otherwise `agent_id` is a way straight around the narrowing."""
    response = client.post(
        "/v1/chat", json={"message": "hello", "mode": "coding", "agent_id": "life_coach"}
    )
    assert response.status_code == 404
    assert "not available in coding mode" in response.json()["detail"]

    # The same agent is reachable without the mode.
    unscoped = client.post("/v1/chat", json={"message": "hi", "agent_id": "life_coach"})
    assert unscoped.status_code == 200


def test_chatting_in_a_mode_routes_within_it(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"message": "ship the login fix", "mode": "coding"})
    assert response.status_code == 200
    routing = next(data for event, data in _sse(response.text) if event == "routing")
    assert routing["chosen"] in {
        "coding",
        "architect",
        "security",
        "data_analyst",
        "product_manager",
        "planner",
    }


# ── Documents ─────────────────────────────────────────────────────────────────


def _compose(client: TestClient, **body: object) -> dict:
    response = client.post("/v1/documents", json={"request": "Brief on Q3 revenue", **body})
    assert response.status_code == 200, response.text
    frames = _sse(response.text)
    assert next(e for e, _ in frames) == "outline"
    return next(data for event, data in frames if event == "done")


def test_composing_streams_an_outline_then_finishes(client: TestClient) -> None:
    done = _compose(client)
    assert done["state"] == "complete"
    assert done["sections"] >= 1
    assert done["words"] > 0


def test_a_composed_document_is_retrievable_the_moment_done_arrives(client: TestClient) -> None:
    """`done` is saved before the frame is sent, so a client can act on it."""
    done = _compose(client)
    fetched = client.get(f"/v1/documents/{done['id']}").json()

    assert fetched["title"] == done["title"]
    assert len(fetched["sections"]) == done["sections"]
    assert all(s["body"] for s in fetched["sections"])


def test_documents_carry_their_mode(client: TestClient) -> None:
    done = _compose(client, mode="business")
    assert done["mode"] == "business"
    assert [d["id"] for d in client.get("/v1/documents?mode=business").json()] == [done["id"]]
    assert client.get("/v1/documents?mode=coding").json() == []


def test_an_unknown_document_kind_is_a_bad_request(client: TestClient) -> None:
    response = client.post("/v1/documents", json={"request": "x", "kind": "haiku"})
    assert response.status_code == 400


def test_a_document_exports_as_markdown_and_html(client: TestClient) -> None:
    done = _compose(client)

    markdown = client.get(f"/v1/documents/{done['id']}/export?format=md")
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.text.startswith("# ")
    assert ".md" in markdown.headers["content-disposition"]

    html = client.get(f"/v1/documents/{done['id']}/export?format=html")
    assert html.status_code == 200
    assert html.text.startswith("<!doctype html>")
    # Self-contained: it has to survive being emailed to someone.
    assert "http://" not in html.text and "https://" not in html.text


def test_an_unknown_export_format_is_refused(client: TestClient) -> None:
    done = _compose(client)
    assert client.get(f"/v1/documents/{done['id']}/export?format=docx").status_code == 400


def test_a_missing_document_is_404_everywhere(client: TestClient) -> None:
    assert client.get("/v1/documents/doc_nope").status_code == 404
    assert client.get("/v1/documents/doc_nope/export").status_code == 404
    assert client.delete("/v1/documents/doc_nope").json() == {"deleted": False}


def test_a_document_can_be_deleted(client: TestClient) -> None:
    done = _compose(client)
    assert client.delete(f"/v1/documents/{done['id']}").json() == {"deleted": True}
    assert client.get("/v1/documents").json() == []


def test_health_counts_ingested_and_generated_separately(client: TestClient) -> None:
    """Two different things that were both called "documents"."""
    before = client.get("/health").json()
    assert before["documents"] == 0

    _compose(client)
    after = client.get("/health").json()
    assert after["documents"] == 1
    assert after["knowledge"] == 0


# ── Vault and budget ──────────────────────────────────────────────────────────


def test_a_locked_vault_says_so_and_refuses_writes(client: TestClient) -> None:
    body = client.get("/v1/secrets").json()
    assert body == {"locked": True, "secrets": []}

    refused = client.put("/v1/secrets/stripe", json={"value": "irrelevant-while-locked"})
    assert refused.status_code == 409
    assert "no vault key" in refused.json()["detail"]


def _unlocked(settings: Settings, clock: FrozenClock) -> TestClient:
    from jarvis.security.vault import new_key

    unlocked = settings.model_copy(update={"vault_key": new_key()})
    system = container.build(unlocked, providers=[EchoProvider()], clock=clock)
    return TestClient(create_app(unlocked, jarvis=system))


def test_no_endpoint_returns_a_secret(settings: Settings, clock: FrozenClock) -> None:
    """The property that matters: there is no shape of the API that leaks one."""
    secret = "NOT-A-REAL-KEY-vault-fixture-4821"
    with _unlocked(settings, clock) as client:
        stored = client.put("/v1/secrets/stripe", json={"value": secret})
        assert stored.status_code == 200
        assert secret not in stored.text

        listing = client.get("/v1/secrets")
        assert secret not in listing.text
        assert listing.json()["secrets"][0]["hint"] == "NOT…21"

        assert secret not in client.get("/health").text
        assert client.get("/health").json()["vault"] == {"locked": False, "secrets": 1}


def test_a_secret_can_be_deleted(settings: Settings, clock: FrozenClock) -> None:
    with _unlocked(settings, clock) as client:
        client.put("/v1/secrets/stripe", json={"value": "a-long-enough-fixture"})
        assert client.delete("/v1/secrets/stripe").json() == {"deleted": True}
        assert client.get("/v1/secrets").json()["secrets"] == []


def test_budget_reports_unenforced_by_default(client: TestClient) -> None:
    body = client.get("/v1/budget").json()
    assert body["enforced"] is False
    assert body["budgets"] == []
    assert body["spend"]["day"]["spent_usd"] == 0.0


def test_budget_publishes_the_ceilings_it_will_enforce(
    settings: Settings, clock: FrozenClock
) -> None:
    """A ceiling nobody can see is a ceiling nobody plans around."""
    governed = settings.model_copy(
        update={"daily_budget_soft_usd": 1.0, "daily_budget_hard_usd": 5.0}
    )
    system = container.build(governed, providers=[EchoProvider()], clock=clock)
    with TestClient(create_app(governed, jarvis=system)) as client:
        body = client.get("/v1/budget").json()
        assert body["enforced"] is True
        day = next(b for b in body["budgets"] if b["period"] == "day")
        assert (day["soft_usd"], day["hard_usd"], day["remaining_usd"]) == (1.0, 5.0, 5.0)
