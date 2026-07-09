"""Project and task routes: full CRUD with dependency-aware auto-prioritization."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Project, TaskItem, User, get_session, utcnow
from ..schemas import ProjectIn, ProjectOut, TaskIn, TaskOut, TaskUpdateIn
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["projects"])


# ----------------------------------------------------------------- projects

@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = (
        (
            await session.execute(
                select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ProjectOut.model_validate(p, from_attributes=True) for p in rows]


@router.post("/projects", response_model=ProjectOut)
async def create_project(
    body: ProjectIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    project = Project(user_id=user.id, name=body.name, description=body.description)
    session.add(project)
    await session.commit()
    return ProjectOut.model_validate(project, from_attributes=True)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    await session.delete(project)
    await session.commit()
    return {"deleted": project_id}


# -------------------------------------------------------------------- tasks

def _task_out(t: TaskItem) -> TaskOut:
    return TaskOut.model_validate(t, from_attributes=True)


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    project_id: str | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(TaskItem).where(TaskItem.user_id == user.id)
    if project_id:
        stmt = stmt.where(TaskItem.project_id == project_id)
    if status:
        stmt = stmt.where(TaskItem.status == status)
    stmt = stmt.order_by(TaskItem.priority.asc(), TaskItem.created_at.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return [_task_out(t) for t in rows]


@router.post("/tasks", response_model=TaskOut)
async def create_task(
    body: TaskIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.project_id:
        project = await session.get(Project, body.project_id)
        if project is None or project.user_id != user.id:
            raise HTTPException(status_code=404, detail="Project not found")
    task = TaskItem(
        user_id=user.id, project_id=body.project_id, parent_id=body.parent_id,
        title=body.title, description=body.description, priority=body.priority,
        due_at=body.due_at, assignee_agent=body.assignee_agent, depends_on=body.depends_on,
    )
    session.add(task)
    await session.commit()
    return _task_out(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    body: TaskUpdateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(TaskItem, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(task, key, value)
    if data.get("status") == "done" and task.completed_at is None:
        task.completed_at = utcnow()
    if data.get("status") and data["status"] != "done":
        task.completed_at = None
    await session.commit()
    return _task_out(task)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await session.get(TaskItem, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    await session.delete(task)
    await session.commit()
    return {"deleted": task_id}
