"""Agent definitions.

An agent is **data**, not a subclass. Everything that distinguishes the Sales
Agent from the Coding Agent — its remit, prompt, tools, routing signals,
memory scopes and default model policy — is declarative. One runtime executes
all of them, so adding an agent is adding a row to the catalog, and the
execution path stays a single well-tested code path.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from jarvis.llm.base import Privacy, RoutingPolicy


class Capability(StrEnum):
    """Coarse capability tags used for routing and permission scoping."""

    PLANNING = "planning"
    RESEARCH = "research"
    WRITING = "writing"
    CODING = "coding"
    ANALYSIS = "analysis"
    DESIGN = "design"
    COMMUNICATION = "communication"
    SCHEDULING = "scheduling"
    FINANCE = "finance"
    LEGAL = "legal"
    SALES = "sales"
    MARKETING = "marketing"
    OPERATIONS = "operations"
    AUTOMATION = "automation"
    MEMORY = "memory"
    SECURITY = "security"
    VISION = "vision"
    VOICE = "voice"
    PERSONAL = "personal"
    LEARNING = "learning"
    HEALTH = "health"
    TRAVEL = "travel"
    SHOPPING = "shopping"
    SUPPORT = "support"


class AgentSpec(BaseModel):
    """The complete definition of an agent."""

    id: str
    name: str
    tagline: str
    responsibilities: list[str] = Field(default_factory=list)
    system_prompt: str
    capabilities: tuple[Capability, ...] = ()
    tools: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    # Where this agent's memories live. Empty means its own id, which is the
    # right default — an agent should not read another's working notes. A mode
    # rewrites this to namespace the whole catalog (ADR 0010).
    memory_scopes: tuple[str, ...] = ()
    policy: RoutingPolicy = RoutingPolicy.BALANCED
    min_privacy: Privacy = Privacy.CLOUD
    max_output_tokens: int = 2048
    temperature: float = 0.7
    # Agents that this one commonly delegates to, used by the planner.
    collaborators: tuple[str, ...] = ()

    model_config = {"frozen": True}

    @property
    def scope(self) -> str:
        """The memory namespace this agent reads from and writes to."""
        return self.memory_scopes[0] if self.memory_scopes else self.id


class AgentMetrics(BaseModel):
    """Rolling performance record. Feeds the router's confidence prior."""

    runs: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    recent_latencies_ms: list[float] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 1.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.runs if self.runs else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self.recent_latencies_ms:
            return 0.0
        ordered = sorted(self.recent_latencies_ms)
        index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
        return ordered[index]

    def record(self, *, ok: bool, latency_ms: float, cost_usd: float, tokens: int) -> None:
        self.runs += 1
        self.successes += int(ok)
        self.failures += int(not ok)
        self.total_latency_ms += latency_ms
        self.total_cost_usd += cost_usd
        self.total_tokens += tokens
        self.recent_latencies_ms.append(latency_ms)
        del self.recent_latencies_ms[:-100]  # keep a bounded window


class AgentMetricsStore(Protocol):
    """Durable per-agent track record."""

    async def save(self, agent_id: str, metrics: AgentMetrics) -> None: ...

    async def load(self) -> dict[str, AgentMetrics]: ...


class AgentMatch(BaseModel):
    """A routing decision: this agent, this confident, for these reasons."""

    agent_id: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
