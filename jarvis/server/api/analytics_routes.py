"""Analytics routes: usage, cost, agent activity, and system status."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import (
    AgentRun, Conversation, Memory, Message, TaskItem, User, Workflow, get_session, utcnow,
)
from ..llm.router import router as model_router
from ..security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    async def count(model, *where):
        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)
        return (await session.execute(stmt)).scalar_one()

    week_ago = utcnow() - timedelta(days=7)
    total_cost = (
        await session.execute(
            select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0)).where(AgentRun.user_id == user.id)
        )
    ).scalar_one()
    total_tokens = (
        await session.execute(
            select(
                func.coalesce(func.sum(AgentRun.tokens_in), 0),
                func.coalesce(func.sum(AgentRun.tokens_out), 0),
            ).where(AgentRun.user_id == user.id)
        )
    ).one()

    return {
        "conversations": await count(Conversation, Conversation.user_id == user.id),
        "messages": await count(
            Message,
            Message.conversation_id.in_(
                select(Conversation.id).where(Conversation.user_id == user.id)
            ),
        ),
        "memories": await count(Memory, Memory.user_id == user.id, Memory.consolidated_into.is_(None)),
        "open_tasks": await count(
            TaskItem, TaskItem.user_id == user.id, TaskItem.status != "done"
        ),
        "workflows": await count(Workflow, Workflow.user_id == user.id),
        "agent_runs_total": await count(AgentRun, AgentRun.user_id == user.id),
        "agent_runs_week": await count(
            AgentRun, AgentRun.user_id == user.id, AgentRun.started_at >= week_ago
        ),
        "total_cost_usd": round(float(total_cost), 6),
        "tokens_in": int(total_tokens[0]),
        "tokens_out": int(total_tokens[1]),
    }


@router.get("/agent-activity")
async def agent_activity(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = (
        await session.execute(
            select(AgentRun.agent, func.count(), func.coalesce(func.sum(AgentRun.cost_usd), 0.0))
            .where(AgentRun.user_id == user.id)
            .group_by(AgentRun.agent)
            .order_by(func.count().desc())
        )
    ).all()
    return {
        "agents": [
            {"agent": a, "runs": c, "cost_usd": round(float(cost), 6)} for a, c, cost in rows
        ]
    }


@router.get("/status")
async def system_status(_: User = Depends(get_current_user)):
    from ..memory.embeddings import embedder

    return {
        "version": settings.version,
        "llm_providers": sorted(model_router.providers.keys()),
        "llm_available": model_router.available,
        "embedding_backend": embedder.name,
        "voice_configured": bool(settings.elevenlabs_api_key),
        "shell_enabled": settings.enable_shell_tool,
    }
