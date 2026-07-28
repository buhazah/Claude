"""The workflow engine.

The design constraint that shapes everything: **a suspended workflow must
survive a process restart.** M4's approvals park on an ``asyncio.Event``, which
is fine for a chat turn where a person is watching, but a workflow can wait
overnight for a decision — and a coroutine's stack is not a place to keep
something that has to outlive the process.

So execution is a loop over persisted state rather than recursion:

    load run → execute the step at ``cursor`` → write the result into the
    context → advance the cursor → persist → repeat

An approval step sets ``state = AWAITING_APPROVAL`` and *returns*. Nothing is
held open. When the decision arrives — seconds later or tomorrow, in this
process or another — ``resume`` loads the same row and continues from the
cursor. That is why the run carries its context explicitly instead of relying
on local variables.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog

from jarvis.agents.orchestrator import Orchestrator
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.runtime import AgentRuntime
from jarvis.kernel.bus import CAUSING_WORKFLOW, EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.errors import NotFoundError
from jarvis.tools.approvals import ApprovalBroker, ApprovalState
from jarvis.tools.registry import ToolRegistry
from jarvis.workflows.models import (
    Condition,
    Operator,
    StepKind,
    StepRecord,
    Workflow,
    WorkflowRun,
    WorkflowRunState,
    WorkflowStep,
)
from jarvis.workflows.store import WorkflowStore
from jarvis.workflows.template import render, render_arguments, resolve

log = structlog.get_logger(__name__)

MAX_STEPS_PER_RUN = 100  # a cycle in a user-authored graph must terminate


def evaluate(condition: Condition, context: dict[str, Any]) -> bool:
    """Evaluate a structured condition against the run context."""
    actual = resolve(condition.field, context)
    left = "" if actual is None else str(actual)
    right = "" if condition.value is None else str(condition.value)

    if not condition.case_sensitive:
        left, right = left.lower(), right.lower()

    match condition.op:
        case Operator.CONTAINS:
            return right in left
        case Operator.NOT_CONTAINS:
            return right not in left
        case Operator.EQUALS:
            return left == right
        case Operator.NOT_EQUALS:
            return left != right
        case Operator.MATCHES:
            try:
                return re.search(right, left) is not None
            except re.error:
                # A bad pattern is an authoring mistake, not a match.
                log.warning("bad_condition_regex", pattern=condition.value)
                return False
        case Operator.GREATER_THAN | Operator.LESS_THAN:
            try:
                a, b = float(left), float(right)
            except ValueError:
                return False
            return a > b if condition.op is Operator.GREATER_THAN else a < b
        case Operator.IS_EMPTY:
            return not left.strip()
        case Operator.IS_NOT_EMPTY:
            return bool(left.strip())
    return False


class WorkflowEngine:
    def __init__(
        self,
        *,
        store: WorkflowStore,
        orchestrator: Orchestrator,
        runtime: AgentRuntime,
        agents: AgentRegistry,
        tools: ToolRegistry,
        approvals: ApprovalBroker,
        bus: EventBus,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._store = store
        self._orchestrator = orchestrator
        self._runtime = runtime
        self._agents = agents
        self._tools = tools
        self._approvals = approvals
        self._bus = bus
        self._clock = clock

    async def start(
        self,
        workflow: Workflow,
        *,
        inputs: dict[str, Any] | None = None,
        trigger: str = "manual",
    ) -> WorkflowRun:
        """Begin a run and drive it as far as it will go without a human."""
        if problems := workflow.validate_graph():
            raise ValueError("; ".join(problems))

        run = WorkflowRun(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            state=WorkflowRunState.RUNNING,
            cursor=workflow.steps[0].id,
            context={"trigger": inputs or {}, "steps": {}},
            trigger=trigger,
            created_at=self._clock.now(),
        )
        await self._store.save_run(run)
        self._bus.publish(
            "workflow.started",
            {"run_id": run.id, "workflow": workflow.name, "trigger": trigger},
            run_id=run.id,
        )
        return await self._drive(workflow, run)

    async def resume(self, run_id: str) -> WorkflowRun:
        """Continue a suspended run. Safe to call from any process."""
        run = await self._store.get_run(run_id)
        if run is None:
            raise NotFoundError(f"unknown workflow run: {run_id}")
        if run.state.terminal:
            return run

        workflow = await self._store.get(run.workflow_id)
        if workflow is None:
            raise NotFoundError(f"unknown workflow: {run.workflow_id}")

        if run.awaiting_approval_id:
            decision = self._approvals.get(run.awaiting_approval_id)
            if decision.state is ApprovalState.PENDING:
                return run  # still waiting; nothing to do

            step = workflow.step(run.cursor) if run.cursor else None
            approved = decision.state is ApprovalState.APPROVED
            self._record(
                run,
                step_id=run.cursor or "approval",
                kind=StepKind.APPROVAL,
                state="succeeded" if approved else "denied",
                output=decision.state.value,
            )
            run.context["steps"][run.cursor or "approval"] = {
                "approved": approved,
                "output": decision.state.value,
                "reason": decision.reason,
            }
            run.awaiting_approval_id = None

            if not approved:
                # A denial is a decision, not a failure: the graph may route
                # around it, and only ends the run when it does not.
                target = step.if_false if step and step.if_false else None
                if target:
                    run.cursor = target
                else:
                    return await self._finish(
                        run, WorkflowRunState.CANCELLED, error="approval denied"
                    )
            else:
                run.cursor = self._successor(
                    workflow, step, override=step.if_true if step else None
                )

        run.state = WorkflowRunState.RUNNING
        await self._store.save_run(run)
        return await self._drive(workflow, run)

    def _successor(
        self, workflow: Workflow, step: WorkflowStep | None, *, override: str | None = None
    ) -> str | None:
        """The next step id: an explicit target, else the one after this."""
        if override:
            return override
        if step is None:
            return None
        if step.terminal:
            return None
        if step.next:
            return step.next
        index = next((i for i, s in enumerate(workflow.steps) if s.id == step.id), None)
        if index is None or index + 1 >= len(workflow.steps):
            return None
        return workflow.steps[index + 1].id

    def _record(
        self,
        run: WorkflowRun,
        *,
        step_id: str,
        kind: StepKind,
        state: str = "succeeded",
        output: str = "",
        error: str | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        run.records.append(
            StepRecord(
                step_id=step_id,
                kind=kind,
                state=state,
                output=output[:2000],
                error=error,
                started_at=self._clock.now(),
                ended_at=self._clock.now(),
                cost_usd=cost_usd,
            )
        )

    async def _drive(self, workflow: Workflow, run: WorkflowRun) -> WorkflowRun:
        """Execute steps until the run ends or needs a human."""
        # Everything published from here down is a consequence of this run.
        # Without this, a workflow triggered by "memory.written" whose agents
        # write memories would re-trigger itself, forever.
        token = CAUSING_WORKFLOW.set(run.id)
        try:
            return await self._drive_inner(workflow, run)
        finally:
            CAUSING_WORKFLOW.reset(token)

    async def _drive_inner(self, workflow: Workflow, run: WorkflowRun) -> WorkflowRun:
        executed = 0
        while run.cursor and not run.state.terminal:
            if executed >= MAX_STEPS_PER_RUN:
                return await self._finish(
                    run,
                    WorkflowRunState.FAILED,
                    error=f"exceeded {MAX_STEPS_PER_RUN} steps — the graph may cycle",
                )
            step = workflow.step(run.cursor)
            if step is None:
                return await self._finish(
                    run, WorkflowRunState.FAILED, error=f"unknown step '{run.cursor}'"
                )

            executed += 1
            try:
                outcome = await self._execute(workflow, run, step)
            except Exception as exc:  # recorded, then routed by the graph
                log.warning("workflow_step_failed", step=step.id, error=str(exc))
                self._record(run, step_id=step.id, kind=step.kind, state="failed", error=str(exc))
                run.context["steps"][step.id] = {"error": str(exc), "output": ""}
                if step.on_error:
                    run.cursor = step.on_error
                    await self._store.save_run(run)
                    continue
                if step.optional:
                    run.cursor = self._successor(workflow, step)
                    await self._store.save_run(run)
                    continue
                return await self._finish(run, WorkflowRunState.FAILED, error=str(exc))

            if outcome is SUSPEND:
                await self._store.save_run(run)
                self._bus.publish(
                    "workflow.suspended",
                    {"run_id": run.id, "step": step.id, "approval": run.awaiting_approval_id},
                    run_id=run.id,
                )
                return run

            await self._store.save_run(run)

        return await self._finish(run, WorkflowRunState.SUCCEEDED)

    async def _finish(
        self, run: WorkflowRun, state: WorkflowRunState, *, error: str | None = None
    ) -> WorkflowRun:
        run.state = state
        run.error = error
        run.ended_at = self._clock.now()
        run.cursor = None
        await self._store.save_run(run)
        self._bus.publish(
            "workflow.finished",
            {
                "run_id": run.id,
                "workflow": run.workflow_name,
                "state": state.value,
                "steps": len(run.records),
                "cost_usd": run.cost_usd,
            },
            run_id=run.id,
        )
        return run

    async def _execute(
        self, workflow: Workflow, run: WorkflowRun, step: WorkflowStep
    ) -> object | None:
        """Run one step, update the context, and set the cursor."""
        match step.kind:
            case StepKind.AGENT:
                output, cost = await self._run_agent(run, step)
                run.context["steps"][step.id] = {"output": output}
                self._record(run, step_id=step.id, kind=step.kind, output=output, cost_usd=cost)
                run.cursor = self._successor(workflow, step)

            case StepKind.TOOL:
                arguments, missing = render_arguments(step.arguments, run.context)
                if missing:
                    log.warning("workflow_unresolved_paths", step=step.id, paths=missing)
                result = await self._tools.invoke(
                    step.tool or "", arguments, run_id=run.id, agent_id="workflow"
                )
                text = result if isinstance(result, str) else str(result)
                run.context["steps"][step.id] = {"output": text, "result": result}
                self._record(run, step_id=step.id, kind=step.kind, output=text)
                run.cursor = self._successor(workflow, step)

            case StepKind.APPROVAL:
                question, _ = render(step.question or step.label or step.id, run.context)
                approval = self._approvals.create(
                    tool=f"workflow:{workflow.name}",
                    arguments={"question": question, "step": step.id},
                    run_id=run.id,
                    agent_id="workflow",
                )
                run.awaiting_approval_id = approval.id
                run.state = WorkflowRunState.AWAITING_APPROVAL
                # The cursor stays on this step: resume() needs to know which
                # approval step it is completing.
                return SUSPEND

            case StepKind.BRANCH:
                assert step.condition is not None
                taken = evaluate(step.condition, run.context)
                run.context["steps"][step.id] = {"output": str(taken), "matched": taken}
                self._record(run, step_id=step.id, kind=step.kind, output=str(taken))
                target = step.if_true if taken else step.if_false
                run.cursor = (
                    target if target else self._successor(workflow, step) if not taken else None
                )
                if taken and not target:
                    run.cursor = self._successor(workflow, step)

            case StepKind.PARALLEL:
                children = [workflow.step(child) for child in step.steps]
                results = await asyncio.gather(
                    *[
                        self._run_agent(run, child)
                        for child in children
                        if child is not None and child.kind is StepKind.AGENT
                    ],
                    return_exceptions=True,
                )
                outputs: list[str] = []
                agent_children = [c for c in children if c and c.kind is StepKind.AGENT]
                for child, result in zip(agent_children, results, strict=False):
                    if isinstance(result, BaseException):
                        run.context["steps"][child.id] = {"error": str(result), "output": ""}
                        self._record(
                            run,
                            step_id=child.id,
                            kind=child.kind,
                            state="failed",
                            error=str(result),
                        )
                        continue
                    output, cost = result
                    outputs.append(output)
                    run.context["steps"][child.id] = {"output": output}
                    self._record(
                        run, step_id=child.id, kind=child.kind, output=output, cost_usd=cost
                    )
                run.context["steps"][step.id] = {"output": "\n\n".join(outputs)}
                run.cursor = self._successor(workflow, step)

            case StepKind.WAIT:
                await asyncio.sleep(min(step.seconds, 5.0))
                self._record(run, step_id=step.id, kind=step.kind, output=f"{step.seconds}s")
                run.cursor = self._successor(workflow, step)

            case StepKind.NOTE:
                text, _ = render(step.label or "", run.context)
                run.context["steps"][step.id] = {"output": text}
                self._record(run, step_id=step.id, kind=step.kind, output=text)
                run.cursor = self._successor(workflow, step)

        return None

    async def _run_agent(self, run: WorkflowRun, step: WorkflowStep) -> tuple[str, float]:
        prompt, missing = render(step.prompt or "", run.context)
        if missing:
            log.warning("workflow_unresolved_paths", step=step.id, paths=missing)

        spec = self._agents.get(step.agent or "")
        agent_run = await self._runtime.run(spec, prompt)
        return agent_run.output, agent_run.cost_usd


# Sentinel: a step that stopped the run to wait for a person.
SUSPEND = object()
