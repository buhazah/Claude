"""Tests for the gated computer-use endpoint (default OFF, owner-only)."""


def test_computer_config_shape(auth_client):
    r = auth_client.get("/api/computer/config")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body and "max_steps" in body
    # Disabled by default in tests (env not set).
    assert body["enabled"] is False


def test_computer_step_disabled_by_default(auth_client):
    r = auth_client.post(
        "/api/computer/step",
        json={"messages": [], "width": 1280, "height": 800},
    )
    # First registered user is owner, so this passes the role gate but hits the
    # feature gate → 403 with a clear message.
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"].lower()


def test_computer_step_blocked_for_members(client):
    # A non-owner member is blocked (403) whether by the feature gate or the
    # owner gate — they can never drive the computer.
    import uuid

    email = f"member-{uuid.uuid4().hex[:8]}@test.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    tok = client.post("/api/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    r = client.post(
        "/api/computer/step",
        headers={"authorization": f"Bearer {tok}"},
        json={"messages": [], "width": 1280, "height": 800},
    )
    assert r.status_code == 403


def test_computer_step_requires_auth(client):
    r = client.post("/api/computer/step", json={"messages": [], "width": 1280, "height": 800})
    assert r.status_code == 401


def test_computer_step_validates_dimensions(auth_client):
    r = auth_client.post(
        "/api/computer/step",
        json={"messages": [], "width": 50, "height": 800},  # width below min
    )
    assert r.status_code == 422
