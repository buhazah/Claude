"""Spend guardrails: measure a user's rolling-24h LLM cost/tokens and enforce
a daily cap before starting an expensive request.

Two caps stack — whichever trips first blocks the request:
- an instance-wide cap from config (JARVIS_DAILY_COST_CAP_USD / _TOKEN_CAP), and
- an optional tighter per-user cap stored in ``user.preferences``.

A cap of 0 (or unset) means unlimited. Cost/tokens are summed from AgentRun
rows, which the runtime writes after every agent execution.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import AgentRun, User, utcnow


async def usage_last_24h(session: AsyncSession, user_id: str) -> tuple[float, int]:
    """Return (cost_usd, tokens) spent by a user in the last rolling 24 hours."""
    since = utcnow() - timedelta(hours=24)
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(AgentRun.cost_usd), 0.0),
                func.coalesce(func.sum(AgentRun.tokens_in + AgentRun.tokens_out), 0),
            ).where(AgentRun.user_id == user_id, AgentRun.started_at >= since)
        )
    ).one()
    return float(row[0] or 0.0), int(row[1] or 0)


def _positive(*values: float) -> float:
    """Smallest positive cap among the candidates, or 0 if none is set."""
    active = [v for v in values if v and v > 0]
    return min(active) if active else 0.0


def effective_caps(user: User | None) -> tuple[float, int]:
    """Resolve the cost/token caps that apply to this user (min of instance + personal)."""
    prefs = (user.preferences or {}) if user else {}
    cost_cap = _positive(settings.daily_cost_cap_usd, _as_float(prefs.get("daily_cost_cap_usd")))
    token_cap = int(_positive(settings.daily_token_cap, _as_float(prefs.get("daily_token_cap"))))
    return cost_cap, token_cap


def _as_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


async def check_spend_cap(session: AsyncSession, user: User) -> None:
    """Raise HTTP 429 if the user has hit their rolling-24h cost or token cap."""
    cost_cap, token_cap = effective_caps(user)
    if cost_cap <= 0 and token_cap <= 0:
        return
    cost, tokens = await usage_last_24h(session, user.id)
    if cost_cap > 0 and cost >= cost_cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily spend limit reached (${cost_cap:.2f}). It resets within 24 hours.",
        )
    if token_cap > 0 and tokens >= token_cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily token limit reached ({token_cap:,}). It resets within 24 hours.",
        )
