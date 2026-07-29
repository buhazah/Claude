"""Workflow definitions and execution state.

A workflow is **data**, like an agent (ADR 0002). That matters more here than
anywhere else: workflows are the thing a user will eventually author without
writing code, and a definition that is a Python object cannot be stored,
versioned, shown in a builder, or shipped between machines.

Two consequences run through this module:

* **Conditions are structured, not expressions.** ``{"field": ..., "op": ...}``
  rather than a string to evaluate. A workflow definition is user input; giving
  user input to ``eval`` in a system that also has a shell tool is not a
  trade-off worth making.
* **Execution state is separable from execution.** A run carries everything
  needed to continue it — context, position, what it is waiting for — so a
  suspended workflow survives a process restart rather than living in a
  coroutine's stack.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from jarvis.kernel.ids import new_id


class StepKind(StrEnum):
    AGENT = "agent"  # run an agent on a prompt
    TOOL = "tool"  # invoke a tool with arguments
    APPROVAL = "approval"  # suspend for a human decision
    BRANCH = "branch"  # jump based on a condition
    PARALLEL = "parallel"  # run several steps concurrently
    WAIT = "wait"  # pause for a duration
    NOTE = "note"  # record something in the timeline


class Operator(StrEnum):
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    MATCHES = "matches"  # regex
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"


class Condition(BaseModel):
    """A comparison against the run context.

    Structured rather than an expression string so a workflow definition can
    come from a user, a file, or an LLM without becoming a code-execution path.
    """

    field: str  # dotted path into the context, e.g. "steps.classify.output"
    op: Operator = Operator.CONTAINS
    value: str | float | None = None
    # Case-insensitive by default: these are usually matched against prose.
    case_sensitive: bool = False


class WorkflowStep(BaseModel):
    id: str
    kind: StepKind
    label: str = ""

    # AGENT
    agent: str | None = None
    prompt: str | None = None  # supports {{ path }} interpolation

    # TOOL
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)

    # APPROVAL
    question: str | None = None

    # BRANCH
    condition: Condition | None = None
    if_true: str | None = None  # step id to jump to
    if_false: str | None = None

    # PARALLEL
    steps: list[str] = Field(default_factory=list)

    # WAIT
    seconds: float = 0.0

    # Flow control. ``next`` overrides the default "step after this one".
    next: str | None = None
    # End the run here. Needed because ``next: None`` means "fall through to
    # the following step", so a branch arm that should finish the workflow has
    # no other way to say so — it would silently run the other arm.
    terminal: bool = False
    # Where to go when this step fails. Without it, a failure ends the run.
    on_error: str | None = None
    # Whether a failure here should stop the workflow at all.
    optional: bool = False


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wfl"))
    name: str
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime | None = None
    # Inputs the trigger supplies, documented for the builder.
    inputs: list[str] = Field(default_factory=list)

    def step(self, step_id: str) -> WorkflowStep | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def validate_graph(self) -> list[str]:
        """Return every structural problem, rather than raising on the first.

        A half-validated workflow is worse than an invalid one: the author
        fixes a typo, re-saves, and discovers the next typo. All of them, now.
        """
        problems: list[str] = []
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            problems.append("step ids must be unique")
        if not self.steps:
            problems.append("a workflow needs at least one step")

        known = set(ids)
        for step in self.steps:
            for label, target in (
                ("next", step.next),
                ("on_error", step.on_error),
                ("if_true", step.if_true),
                ("if_false", step.if_false),
            ):
                if target and target not in known:
                    problems.append(f"step '{step.id}' {label} points at unknown '{target}'")
            for child in step.steps:
                if child not in known:
                    problems.append(f"step '{step.id}' references unknown step '{child}'")

            if step.kind is StepKind.AGENT and not step.agent:
                problems.append(f"step '{step.id}' is an agent step with no agent")
            if step.kind is StepKind.TOOL and not step.tool:
                problems.append(f"step '{step.id}' is a tool step with no tool")
            if step.kind is StepKind.BRANCH and not step.condition:
                problems.append(f"step '{step.id}' is a branch with no condition")
        return problems


class WorkflowRunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (
            WorkflowRunState.SUCCEEDED,
            WorkflowRunState.FAILED,
            WorkflowRunState.CANCELLED,
        )


class StepRecord(BaseModel):
    """What one step did, for the timeline."""

    step_id: str
    kind: StepKind
    state: str = "succeeded"
    output: str = ""
    error: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    cost_usd: float = 0.0


class WorkflowRun(BaseModel):
    """Everything needed to continue a workflow, including across a restart."""

    id: str = Field(default_factory=lambda: new_id("wrn"))
    workflow_id: str
    workflow_name: str = ""
    state: WorkflowRunState = WorkflowRunState.PENDING
    # The step to execute next. This, plus the context, *is* the program counter.
    cursor: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    records: list[StepRecord] = Field(default_factory=list)
    awaiting_approval_id: str | None = None
    error: str | None = None
    trigger: str = "manual"
    created_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self.records), 6)


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"  # every N seconds
    EVENT = "event"  # a bus topic pattern


class Trigger(BaseModel):
    id: str = Field(default_factory=lambda: new_id("trg"))
    workflow_id: str
    kind: TriggerKind = TriggerKind.MANUAL
    enabled: bool = True
    # SCHEDULE
    interval_seconds: float = 3600.0
    # EVENT — a bus topic pattern, matched with the same wildcards as subscriptions.
    topic: str = ""
    last_fired_at: datetime | None = None
