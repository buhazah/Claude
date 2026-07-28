"""Request/response models for the HTTP surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from jarvis.agents.spec import AgentSpec
from jarvis.llm.base import Message


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)
    agent_id: str | None = None  # pin an agent; omit to let Jarvis route
    history: list[Message] = Field(default_factory=list)
    remember: bool = True


class RouteRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)


class ApprovalDecision(BaseModel):
    approved: bool
    reason: str | None = None


class IngestRequest(BaseModel):
    """Exactly one source. Which one is checked by the handler, not the schema,
    so the error names the actual problem rather than a validation shape."""

    url: str | None = None
    path: str | None = None
    text: str | None = None
    title: str | None = None
    scope: str = "global"


class WorkflowRunRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class ToolInvocation(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class RememberRequest(BaseModel):
    content: str = Field(min_length=1)
    kind: str | None = None
    scope: str = "global"
    tags: list[str] = Field(default_factory=list)


class AgentSummary(BaseModel):
    """An agent plus its live performance, as the agent grid renders it."""

    id: str
    name: str
    tagline: str
    responsibilities: list[str]
    capabilities: list[str]
    tools: list[str]
    policy: str
    runs: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: float

    @classmethod
    def build(cls, spec: AgentSpec, metrics: Any) -> AgentSummary:
        return cls(
            id=spec.id,
            name=spec.name,
            tagline=spec.tagline,
            responsibilities=spec.responsibilities,
            capabilities=[c.value for c in spec.capabilities],
            tools=list(spec.tools),
            policy=spec.policy.value,
            runs=metrics.runs,
            success_rate=round(metrics.success_rate, 4),
            avg_latency_ms=round(metrics.avg_latency_ms, 1),
            p95_latency_ms=round(metrics.p95_latency_ms, 1),
            total_cost_usd=round(metrics.total_cost_usd, 6),
        )


class ModelSummary(BaseModel):
    id: str
    provider: str
    context_window: int
    quality: float
    latency_score: float
    input_cost_per_mtok: float
    output_cost_per_mtok: float
    privacy: str
