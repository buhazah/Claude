"""Tests for the daily spend-cap guardrail."""
import uuid

import pytest
from fastapi import HTTPException
from types import SimpleNamespace


def test_effective_caps_prefers_tightest():
    from server.usage import effective_caps

    # Personal cap only.
    u = SimpleNamespace(preferences={"daily_cost_cap_usd": 2})
    assert effective_caps(u) == (2.0, 0)
    # No cap anywhere.
    assert effective_caps(SimpleNamespace(preferences={})) == (0.0, 0)
    # Junk values are ignored, not fatal.
    assert effective_caps(SimpleNamespace(preferences={"daily_cost_cap_usd": "oops"})) == (0.0, 0)


async def test_spend_cap_blocks_when_over_limit(client):
    from server.db import AgentRun, SessionLocal, User
    from server.usage import check_spend_cap, usage_last_24h

    async with SessionLocal() as s:
        uid = uuid.uuid4().hex[:16]
        user = User(
            id=uid, email=f"{uid}@t.co", name="T", password_hash="x",
            preferences={"daily_cost_cap_usd": 1.0},
        )
        s.add(user)
        await s.flush()
        s.add(AgentRun(user_id=uid, agent="assistant", goal="g", cost_usd=2.5, tokens_in=10, tokens_out=20))
        await s.commit()

        cost, tokens = await usage_last_24h(s, uid)
        assert cost == 2.5 and tokens == 30

        with pytest.raises(HTTPException) as ei:
            await check_spend_cap(s, user)
        assert ei.value.status_code == 429


async def test_spend_cap_allows_under_limit(client):
    from server.db import AgentRun, SessionLocal, User
    from server.usage import check_spend_cap

    async with SessionLocal() as s:
        uid = uuid.uuid4().hex[:16]
        user = User(
            id=uid, email=f"{uid}@t.co", name="T", password_hash="x",
            preferences={"daily_cost_cap_usd": 5.0},
        )
        s.add(user)
        await s.flush()
        s.add(AgentRun(user_id=uid, agent="assistant", goal="g", cost_usd=0.10))
        await s.commit()

        # Under the cap → returns without raising.
        await check_spend_cap(s, user)


def test_usage_today_endpoint(auth_client):
    r = auth_client.get("/api/analytics/usage-today")
    assert r.status_code == 200
    body = r.json()
    assert {"cost_usd", "tokens", "cost_cap_usd", "token_cap", "over_cap"} <= set(body)


def test_chat_stream_refuses_when_over_cap(auth_client):
    import asyncio

    from server.db import AgentRun, SessionLocal

    # Set a tiny personal cap, then record spend above it.
    uid = auth_client.get("/api/auth/me").json()["id"]
    auth_client.put("/api/auth/preferences", json={"preferences": {"daily_cost_cap_usd": 0.01}})

    async def _spend():
        async with SessionLocal() as s:
            s.add(AgentRun(user_id=uid, agent="assistant", goal="g", cost_usd=1.0))
            await s.commit()

    asyncio.run(_spend())

    r = auth_client.post("/api/chat/stream", json={"message": "hello", "agent": None})
    assert r.status_code == 429
    assert "limit" in r.json()["detail"].lower()
