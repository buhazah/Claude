"""Pydantic request/response models — the API's input/output validation layer."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ------------------------------------------------------------------- auth

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    preferences: dict


class PreferencesIn(BaseModel):
    preferences: dict


# ------------------------------------------------------------------- chat

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    agent: str | None = None  # force a specific agent, else orchestrator routes


class ConversationOut(BaseModel):
    id: str
    title: str
    agent: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    agent: str
    meta: dict
    created_at: datetime


# ----------------------------------------------------------------- memory

class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    kind: str = "fact"
    importance: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryOut(BaseModel):
    id: str
    kind: str
    content: str
    importance: float
    access_count: int
    created_at: datetime
    score: float | None = None


class MemorySearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=12, ge=1, le=50)
    kinds: list[str] | None = None


# ------------------------------------------------------------ projects/tasks

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    created_at: datetime


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    project_id: str | None = None
    parent_id: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    due_at: datetime | None = None
    assignee_agent: str = ""
    depends_on: list[str] = []


class TaskUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    due_at: datetime | None = None
    assignee_agent: str | None = None


class TaskOut(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: int
    project_id: str | None
    parent_id: str | None
    assignee_agent: str
    depends_on: list
    due_at: datetime | None
    created_at: datetime
    completed_at: datetime | None


# --------------------------------------------------------------- workflows

class WorkflowIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    schedule: str = "manual"  # cron expr or "manual"
    prompt: str = Field(min_length=1, max_length=8000)
    agent: str = "orchestrator"
    enabled: bool = True


class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str
    schedule: str
    prompt: str
    agent: str
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime


class WorkflowRunOut(BaseModel):
    id: str
    status: str
    output: str
    error: str
    started_at: datetime
    finished_at: datetime | None


# ------------------------------------------------------------------- voice

class VoiceIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str | None = None


class VisionIn(BaseModel):
    image: str = Field(description="Data URL or base64 image (e.g. a screenshot)")
    prompt: str = Field(default="", max_length=2000)


TokenOut.model_rebuild()
