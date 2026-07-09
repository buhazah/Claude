"""Memory routes: browse, add, search, delete, and trigger maintenance
(consolidation and reflection)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Memory, User, get_session
from ..memory.manager import memory_manager
from ..schemas import MemoryIn, MemoryOut, MemorySearchIn
from ..security import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    kind: str | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Memory).where(Memory.user_id == user.id, Memory.consolidated_into.is_(None))
    if kind:
        stmt = stmt.where(Memory.kind == kind)
    stmt = stmt.order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(min(limit, 500))
    rows = (await session.execute(stmt)).scalars().all()
    return [MemoryOut.model_validate(m, from_attributes=True) for m in rows]


@router.get("/stats")
async def memory_stats(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = (
        await session.execute(
            select(Memory.kind, func.count())
            .where(Memory.user_id == user.id, Memory.consolidated_into.is_(None))
            .group_by(Memory.kind)
        )
    ).all()
    return {"by_kind": {k: c for k, c in rows}, "total": sum(c for _, c in rows)}


@router.post("", response_model=MemoryOut)
async def add_memory(
    body: MemoryIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    mem = await memory_manager.remember(
        session, user.id, body.content, kind=body.kind,
        source="manual", importance=body.importance,
    )
    return MemoryOut.model_validate(mem, from_attributes=True)


@router.post("/search", response_model=list[MemoryOut])
async def search_memory(
    body: MemorySearchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    results = await memory_manager.recall(
        session, user.id, body.query, limit=body.limit, kinds=body.kinds
    )
    out = []
    for mem, score in results:
        item = MemoryOut.model_validate(mem, from_attributes=True)
        item.score = round(score, 4)
        out.append(item)
    return out


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    mem = await session.get(Memory, memory_id)
    if mem is None or mem.user_id != user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.delete(mem)
    await session.commit()
    return {"deleted": memory_id}


@router.post("/maintenance")
async def run_maintenance(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    merged = await memory_manager.consolidate(session, user.id)
    reflection = await memory_manager.reflect(session, user.id)
    return {
        "consolidated": merged,
        "reflection": reflection.content if reflection else None,
    }
