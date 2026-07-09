"""Workflow (automation) routes: CRUD, manual run, and run history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.definitions import AGENTS
from ..automation.scheduler import engine, next_run_after
from ..db import Workflow, WorkflowRun, User, get_session
from ..schemas import WorkflowIn, WorkflowOut, WorkflowRunOut
from ..security import get_current_user

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _validate_schedule(schedule: str) -> None:
    if schedule == "manual":
        return
    if len(schedule.split()) != 5:
        raise HTTPException(
            status_code=400,
            detail="Schedule must be 'manual' or a 5-field cron expression (min hour dom mon dow)",
        )


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = (
        (
            await session.execute(
                select(Workflow).where(Workflow.user_id == user.id).order_by(Workflow.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [WorkflowOut.model_validate(w, from_attributes=True) for w in rows]


@router.post("", response_model=WorkflowOut)
async def create_workflow(
    body: WorkflowIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _validate_schedule(body.schedule)
    if body.agent != "orchestrator" and body.agent not in AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown agent '{body.agent}'")
    from ..db import utcnow
    wf = Workflow(
        user_id=user.id, name=body.name, description=body.description,
        schedule=body.schedule, prompt=body.prompt, agent=body.agent, enabled=body.enabled,
        next_run_at=next_run_after(body.schedule, utcnow()),
    )
    session.add(wf)
    await session.commit()
    return WorkflowOut.model_validate(wf, from_attributes=True)


@router.patch("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: str,
    body: WorkflowIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if wf is None or wf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_schedule(body.schedule)
    from ..db import utcnow
    wf.name, wf.description, wf.schedule = body.name, body.description, body.schedule
    wf.prompt, wf.agent, wf.enabled = body.prompt, body.agent, body.enabled
    wf.next_run_at = next_run_after(body.schedule, utcnow())
    await session.commit()
    return WorkflowOut.model_validate(wf, from_attributes=True)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if wf is None or wf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await session.delete(wf)
    await session.commit()
    return {"deleted": workflow_id}


@router.post("/{workflow_id}/run")
async def run_workflow_now(
    workflow_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if wf is None or wf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    output = await engine.run_workflow(workflow_id)
    return {"output": output}


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunOut])
async def workflow_runs(
    workflow_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if wf is None or wf.user_id != user.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    rows = (
        (
            await session.execute(
                select(WorkflowRun)
                .where(WorkflowRun.workflow_id == workflow_id)
                .order_by(WorkflowRun.started_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [WorkflowRunOut.model_validate(r, from_attributes=True) for r in rows]
