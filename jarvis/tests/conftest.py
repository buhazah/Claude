"""Pytest fixtures: an isolated database and a TestClient per test session."""
import os
import tempfile

import pytest

# Point the app at a throwaway data dir BEFORE importing server modules.
_TMP = tempfile.mkdtemp(prefix="jarvis-test-")
os.environ["JARVIS_DATA_DIR"] = _TMP
os.environ["JARVIS_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/test.db"
os.environ.setdefault("JARVIS_EMBEDDING_PROVIDER", "local")
os.environ.setdefault("JARVIS_ENABLE_SHELL_TOOL", "true")


@pytest.fixture(scope="session")
def client():
    from starlette.testclient import TestClient
    from server.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    """A client with a freshly-registered, authenticated user."""
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    res = client.post("/api/auth/register", json={"email": email, "password": "password123", "name": "Tester"})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    client.headers.update({"authorization": f"Bearer {token}"})
    yield client
    client.headers.pop("authorization", None)
