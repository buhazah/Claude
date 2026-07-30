from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ops import db
from ops.app import create_app


@pytest.fixture()
def app():
    """A fresh in-memory database per test. Fast, and no leakage between them."""
    application = create_app("sqlite://")
    db.reset()
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def session():
    with db.session() as s:
        yield s
