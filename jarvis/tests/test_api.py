"""Integration tests exercising the HTTP API end-to-end via TestClient."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_required(client):
    r = client.get("/api/agents")
    assert r.status_code == 401


def test_login_flow(client):
    email = "flow@test.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    bad = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert bad.status_code == 401


def test_agents_listed(auth_client):
    r = auth_client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert len(agents) >= 20
    keys = {a["key"] for a in agents}
    assert {"ceo", "coding", "research", "finance"} <= keys


def test_memory_crud_and_search(auth_client):
    add = auth_client.post("/api/memory", json={"content": "I prefer concise answers", "kind": "preference"})
    assert add.status_code == 200
    mid = add.json()["id"]

    search = auth_client.post("/api/memory/search", json={"query": "how do I like my responses"})
    assert search.status_code == 200
    assert any("concise" in m["content"] for m in search.json())

    stats = auth_client.get("/api/memory/stats")
    assert stats.json()["total"] >= 1

    dele = auth_client.delete(f"/api/memory/{mid}")
    assert dele.status_code == 200


def test_project_and_task_lifecycle(auth_client):
    proj = auth_client.post("/api/projects", json={"name": "Q3 Launch"})
    assert proj.status_code == 200
    pid = proj.json()["id"]

    task = auth_client.post("/api/tasks", json={"title": "Write launch plan", "project_id": pid, "priority": 1})
    assert task.status_code == 200
    tid = task.json()["id"]

    upd = auth_client.patch(f"/api/tasks/{tid}", json={"status": "done"})
    assert upd.status_code == 200
    assert upd.json()["completed_at"] is not None

    tasks = auth_client.get(f"/api/tasks?project_id={pid}")
    assert len(tasks.json()) == 1


def test_workflow_validation_and_crud(auth_client):
    bad = auth_client.post("/api/workflows", json={"name": "x", "prompt": "do", "schedule": "not cron"})
    assert bad.status_code == 400

    ok = auth_client.post("/api/workflows", json={
        "name": "Morning brief", "prompt": "Summarize tasks", "schedule": "0 8 * * *",
    })
    assert ok.status_code == 200
    assert ok.json()["next_run_at"] is not None
    wid = ok.json()["id"]

    lst = auth_client.get("/api/workflows")
    assert any(w["id"] == wid for w in lst.json())

    auth_client.delete(f"/api/workflows/{wid}")


def test_analytics_overview(auth_client):
    r = auth_client.get("/api/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert "conversations" in body and "total_cost_usd" in body


def test_chat_stream_degrades_without_llm(auth_client):
    """Without a provider key the stream must still return structured SSE."""
    with auth_client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "event: open" in body
    assert "event: done" in body


def test_voice_config(auth_client):
    r = auth_client.get("/api/voice/config")
    assert r.status_code == 200
    assert "tts_available" in r.json()
