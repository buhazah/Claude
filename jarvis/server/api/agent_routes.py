"""Agent routes: list agents and read recent agent runs (live status feed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.definitions import list_agents
from ..db import AgentRun, User, get_session
from ..security import get_current_user

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def agents(_: User = Depends(get_current_user)):
    return {"agents": list_agents()}


@router.get("/runs")
async def agent_runs(
    limit: int = 30,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        (
            await session.execute(
                select(AgentRun)
                .where(AgentRun.user_id == user.id)
                .order_by(AgentRun.started_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    return {
        "runs": [
            {
                "id": r.id, "agent": r.agent, "goal": r.goal, "status": r.status,
                "plan": r.plan, "steps": r.steps, "output": r.output[:2000],
                "cost_usd": round(r.cost_usd, 6),
                "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]
    }
