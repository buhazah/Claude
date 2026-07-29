"""LLM port: the contract every provider adapter implements.

Callers never name a model. They describe the work and the constraints; the
router (``jarvis.llm.router``) picks. That indirection is what makes cost
control, privacy floors and provider outages a configuration concern rather
than a code change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A model's request to invoke a tool, fully assembled.

    Providers stream tool arguments as JSON fragments across many events;
    adapters accumulate those and emit this only once it is complete. Partial
    tool calls never leave an adapter — a half-parsed argument object is worse
    than no tool call at all.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Role
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    # Set on assistant turns that requested tools, so the next request can
    # replay the exchange the provider expects.
    tool_calls: list[ToolCall] = Field(default_factory=list)


class Privacy(int, Enum):
    """How much the data may travel. Higher is more private."""

    CLOUD = 0  # any hosted provider
    TRUSTED_CLOUD = 1  # providers under a zero-retention agreement
    LOCAL = 2  # never leaves the machine


class Modality(StrEnum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Everything the router needs to reason about a model."""

    id: str
    provider: str
    context_window: int
    max_output: int
    input_cost_per_mtok: float
    output_cost_per_mtok: float
    quality: float  # 0..1, task-agnostic capability prior
    latency_score: float  # 0..1, higher is faster
    privacy: Privacy = Privacy.CLOUD
    modalities: tuple[Modality, ...] = (Modality.TEXT,)
    supports_tools: bool = True

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_cost_per_mtok + output_tokens * self.output_cost_per_mtok
        ) / 1_000_000


class RoutingPolicy(StrEnum):
    """The weighting profile used to score candidate models."""

    QUALITY = "quality"
    BALANCED = "balanced"
    CHEAP = "cheap"
    FAST = "fast"
    PRIVATE = "private"


POLICY_WEIGHTS: dict[RoutingPolicy, tuple[float, float, float]] = {
    # (quality, cost, latency) — must sum to 1.0
    RoutingPolicy.QUALITY: (0.80, 0.05, 0.15),
    RoutingPolicy.BALANCED: (0.50, 0.25, 0.25),
    RoutingPolicy.CHEAP: (0.20, 0.70, 0.10),
    RoutingPolicy.FAST: (0.25, 0.15, 0.60),
    RoutingPolicy.PRIVATE: (0.50, 0.25, 0.25),
}


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class CompletionRequest(BaseModel):
    """A request for model output, expressed in intent rather than model names."""

    messages: list[Message]
    system: str | None = None
    policy: RoutingPolicy = RoutingPolicy.BALANCED
    max_output_tokens: int = 2048
    temperature: float = 0.7
    min_privacy: Privacy = Privacy.CLOUD
    required_modalities: tuple[Modality, ...] = (Modality.TEXT,)
    needs_tools: bool = False
    estimated_input_tokens: int | None = None
    model_id: str | None = None  # escape hatch: pin a specific model

    model_config = {"arbitrary_types_allowed": True}

    def token_estimate(self) -> int:
        if self.estimated_input_tokens is not None:
            return self.estimated_input_tokens
        chars = sum(len(m.content) for m in self.messages) + len(self.system or "")
        return chars // 4 + 16  # ~4 chars/token, plus envelope


@dataclass(slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class Chunk:
    """One streamed increment."""

    text: str = ""
    tool_call: ToolCall | None = None
    done: bool = False
    usage: Usage | None = None
    model_id: str | None = None  # stamped by the router, not by adapters


@dataclass(slots=True)
class Completion:
    text: str
    model_id: str
    provider: str
    usage: Usage = field(default_factory=Usage)
    tool_calls: list[ToolCall] = field(default_factory=list)
    fallbacks_used: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    """What an adapter must offer. Nothing more."""

    name: str

    def models(self) -> list[ModelSpec]: ...

    def is_available(self) -> bool: ...

    def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]: ...
