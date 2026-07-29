"""Workflows: the graph engine, durable suspension, triggers and scheduling."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.base import Chunk, CompletionRequest, ModelSpec, ToolSchema, Usage
from jarvis.llm.providers.echo import ECHO_MODEL
from jarvis.persistence.db import Database
from jarvis.tools.approvals import ApprovalBroker
from jarvis.workflows.catalog import starter_workflows
from jarvis.workflows.engine import MAX_STEPS_PER_RUN, WorkflowEngine, evaluate
from jarvis.workflows.models import (
    Condition,
    Operator,
    StepKind,
    Trigger,
    TriggerKind,
    Workflow,
    WorkflowRun,
    WorkflowRunState,
    WorkflowStep,
)
from jarvis.workflows.store import InMemoryWorkflowStore, SqlWorkflowStore
from jarvis.workflows.template import render, render_arguments, resolve
from jarvis.workflows.triggers import Scheduler

REPLY_MODEL = replace(ECHO_MODEL, id="scripted-1", provider="scripted")


class ScriptedProvider:
    """Returns a canned answer, so a workflow's shape is what is under test."""

    name = "scripted"

    def __init__(self, answer: str = "REPLY: acknowledged") -> None:
        self._answer = answer
        self.calls = 0

    def models(self) -> list[ModelSpec]:
        return [REPLY_MODEL]

    def is_available(self) -> bool:
        return True

    async def stream(
        self, request: CompletionRequest, model: ModelSpec, tools: list[ToolSchema] | None = None
    ) -> AsyncIterator[Chunk]:
        self.calls += 1
        yield Chunk(text=self._answer)
        yield Chunk(done=True, usage=Usage(input_tokens=8, output_tokens=4, cost_usd=0.0002))


@pytest.fixture
def system(settings, clock: FrozenClock, tmp_path):
    return container.build(
        settings.model_copy(update={"workspace_dir": str(tmp_path)}),
        providers=[ScriptedProvider()],
        clock=clock,
    )


# ── Template resolution ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("trigger.body", "hello"),
        ("steps.one.output", "first"),
        ("steps.missing.output", None),
        ("trigger", {"body": "hello"}),
        ("nothing.at.all", None),
    ],
)
def test_paths_resolve_into_the_context(path: str, expected: object) -> None:
    context = {"trigger": {"body": "hello"}, "steps": {"one": {"output": "first"}}}
    assert resolve(path, context) == expected


def test_placeholders_are_interpolated() -> None:
    text, missing = render(
        "Reply to {{ trigger.from }} about {{ steps.one.output }}",
        {"trigger": {"from": "Sam"}, "steps": {"one": {"output": "pricing"}}},
    )
    assert text == "Reply to Sam about pricing"
    assert missing == []


def test_missing_paths_are_reported_not_silently_dropped() -> None:
    """A prompt that quietly loses half its content produces a confident lie."""
    text, missing = render("Summarise {{ steps.absent.output }}", {"steps": {}})
    assert text == "Summarise "
    assert missing == ["steps.absent.output"]


def test_interpolation_is_not_code_execution() -> None:
    """A definition may come from a user or a model; it must never be evaluated."""
    text, missing = render("{{ __import__('os').system('rm -rf /') }}", {})
    # Not a valid path, so it is not even a placeholder — left alone, not run.
    assert "rm -rf" in text
    assert missing == []


def test_tool_arguments_are_interpolated_recursively() -> None:
    arguments, missing = render_arguments(
        {"to": "{{ trigger.from }}", "meta": {"tags": ["{{ trigger.tag }}"]}, "n": 3},
        {"trigger": {"from": "sam@example.com", "tag": "urgent"}},
    )
    assert arguments == {"to": "sam@example.com", "meta": {"tags": ["urgent"]}, "n": 3}
    assert missing == []


# ── Conditions ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("op", "value", "expected"),
    [
        (Operator.CONTAINS, "urgent", True),
        (Operator.CONTAINS, "trivial", False),
        (Operator.NOT_CONTAINS, "trivial", True),
        (Operator.EQUALS, "this is urgent", True),
        (Operator.NOT_EQUALS, "something else", True),
        (Operator.MATCHES, r"urg\w+", True),
        (Operator.IS_NOT_EMPTY, None, True),
        (Operator.IS_EMPTY, None, False),
    ],
)
def test_conditions_evaluate(op: Operator, value: str | None, expected: bool) -> None:
    context = {"steps": {"classify": {"output": "This is urgent"}}}
    condition = Condition(field="steps.classify.output", op=op, value=value)
    assert evaluate(condition, context) is expected


def test_numeric_comparison_handles_non_numbers() -> None:
    context = {"steps": {"score": {"output": "not a number"}}}
    condition = Condition(field="steps.score.output", op=Operator.GREATER_THAN, value=5)
    assert evaluate(condition, context) is False


def test_a_bad_regex_is_a_non_match_not_a_crash() -> None:
    context = {"steps": {"x": {"output": "text"}}}
    condition = Condition(field="steps.x.output", op=Operator.MATCHES, value="[unclosed")
    assert evaluate(condition, context) is False


# ── Validation ────────────────────────────────────────────────────────────────


def test_every_structural_problem_is_reported_at_once() -> None:
    """Fixing one typo per save-and-retry is a miserable way to author a graph."""
    workflow = Workflow(
        name="broken",
        steps=[
            WorkflowStep(id="a", kind=StepKind.AGENT, next="nowhere"),
            WorkflowStep(id="a", kind=StepKind.TOOL),
            WorkflowStep(id="c", kind=StepKind.BRANCH),
        ],
    )
    problems = workflow.validate_graph()

    assert any("unique" in p for p in problems)
    assert any("unknown 'nowhere'" in p for p in problems)
    assert any("no agent" in p for p in problems)
    assert any("no tool" in p for p in problems)
    assert any("no condition" in p for p in problems)


def test_the_starter_catalog_is_valid() -> None:
    for workflow in starter_workflows():
        assert workflow.validate_graph() == []


async def test_an_invalid_workflow_will_not_start(system) -> None:
    with pytest.raises(ValueError, match="at least one step"):
        await system.engine.start(Workflow(name="empty"))


# ── Execution ─────────────────────────────────────────────────────────────────


def _linear() -> Workflow:
    return Workflow(
        id="wfl_linear",
        name="Linear",
        steps=[
            WorkflowStep(
                id="one",
                kind=StepKind.AGENT,
                agent="research",
                prompt="Look into {{ trigger.topic }}",
            ),
            WorkflowStep(
                id="two",
                kind=StepKind.AGENT,
                agent="copywriter",
                prompt="Write up: {{ steps.one.output }}",
            ),
        ],
    )


async def test_a_linear_workflow_runs_to_completion(system) -> None:
    workflow = await system.workflows.save(_linear())
    run = await system.engine.start(workflow, inputs={"topic": "oat milk"})

    assert run.state is WorkflowRunState.SUCCEEDED
    assert [r.step_id for r in run.records] == ["one", "two"]
    assert run.cost_usd > 0


async def test_a_step_sees_the_previous_step_output(system) -> None:
    workflow = await system.workflows.save(_linear())
    run = await system.engine.start(workflow, inputs={"topic": "oat milk"})

    assert run.context["steps"]["one"]["output"]
    assert run.context["steps"]["two"]["output"]


async def test_a_branch_takes_the_true_path(system) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_branch",
            name="Branch",
            steps=[
                WorkflowStep(id="classify", kind=StepKind.AGENT, agent="email", prompt="classify"),
                WorkflowStep(
                    id="check",
                    kind=StepKind.BRANCH,
                    condition=Condition(
                        field="steps.classify.output", op=Operator.CONTAINS, value="REPLY"
                    ),
                    if_true="reply",
                    if_false="ignore",
                ),
                WorkflowStep(id="reply", kind=StepKind.NOTE, label="replied", terminal=True),
                WorkflowStep(id="ignore", kind=StepKind.NOTE, label="ignored"),
            ],
        )
    )
    run = await system.engine.start(workflow)

    steps = [r.step_id for r in run.records]
    assert "reply" in steps
    assert "ignore" not in steps


async def test_a_failing_step_can_route_to_a_handler(system) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_handled",
            name="Handled",
            steps=[
                WorkflowStep(
                    id="boom", kind=StepKind.TOOL, tool="does_not_exist", on_error="recover"
                ),
                WorkflowStep(id="recover", kind=StepKind.NOTE, label="recovered"),
            ],
        )
    )
    run = await system.engine.start(workflow)

    assert run.state is WorkflowRunState.SUCCEEDED
    assert [r.step_id for r in run.records] == ["boom", "recover"]
    assert run.records[0].state == "failed"


async def test_an_unhandled_failure_fails_the_run(system) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_broken",
            name="Broken",
            steps=[WorkflowStep(id="boom", kind=StepKind.TOOL, tool="does_not_exist")],
        )
    )
    run = await system.engine.start(workflow)

    assert run.state is WorkflowRunState.FAILED
    assert run.error


async def test_an_optional_step_failure_continues(system) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_optional",
            name="Optional",
            steps=[
                WorkflowStep(id="boom", kind=StepKind.TOOL, tool="does_not_exist", optional=True),
                WorkflowStep(id="after", kind=StepKind.NOTE, label="carried on"),
            ],
        )
    )
    run = await system.engine.start(workflow)

    assert run.state is WorkflowRunState.SUCCEEDED
    assert [r.step_id for r in run.records] == ["boom", "after"]


async def test_a_tool_step_runs_with_interpolated_arguments(system, tmp_path) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_tool",
            name="Tool",
            steps=[
                WorkflowStep(
                    id="write",
                    kind=StepKind.TOOL,
                    tool="write_file",
                    arguments={"path": "{{ trigger.name }}.txt", "content": "{{ trigger.body }}"},
                )
            ],
        )
    )
    run = await system.engine.start(workflow, inputs={"name": "note", "body": "hello"})

    assert run.state is WorkflowRunState.SUCCEEDED
    assert (tmp_path / "note.txt").read_text() == "hello"


async def test_parallel_steps_all_run(system) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_parallel",
            name="Parallel",
            steps=[
                WorkflowStep(id="fan", kind=StepKind.PARALLEL, steps=["a", "b"], next="join"),
                WorkflowStep(id="a", kind=StepKind.AGENT, agent="research", prompt="a"),
                WorkflowStep(id="b", kind=StepKind.AGENT, agent="research", prompt="b"),
                WorkflowStep(id="join", kind=StepKind.NOTE, label="joined"),
            ],
        )
    )
    run = await system.engine.start(workflow)

    recorded = {r.step_id for r in run.records}
    assert {"a", "b", "join"} <= recorded
    assert run.state is WorkflowRunState.SUCCEEDED


async def test_a_cycle_is_stopped_rather_than_spinning_forever(system) -> None:
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_cycle",
            name="Cycle",
            steps=[
                WorkflowStep(id="a", kind=StepKind.NOTE, label="a", next="b"),
                WorkflowStep(id="b", kind=StepKind.NOTE, label="b", next="a"),
            ],
        )
    )
    run = await system.engine.start(workflow)

    assert run.state is WorkflowRunState.FAILED
    assert "cycle" in (run.error or "")
    assert len(run.records) == MAX_STEPS_PER_RUN


# ── Durable suspension: the point of the milestone ────────────────────────────


def _approval_workflow() -> Workflow:
    return Workflow(
        id="wfl_approval",
        name="Needs approval",
        steps=[
            WorkflowStep(id="draft", kind=StepKind.AGENT, agent="email", prompt="draft a reply"),
            WorkflowStep(
                id="approve", kind=StepKind.APPROVAL, question="Send {{ steps.draft.output }}?"
            ),
            WorkflowStep(id="sent", kind=StepKind.NOTE, label="sent"),
        ],
    )


async def test_an_approval_step_suspends_without_holding_anything_open(system) -> None:
    workflow = await system.workflows.save(_approval_workflow())
    run = await asyncio.wait_for(system.engine.start(workflow), timeout=2)

    # The call *returned* rather than parking on an event.
    assert run.state is WorkflowRunState.AWAITING_APPROVAL
    assert run.awaiting_approval_id
    assert run.cursor == "approve"
    assert system.approvals.pending()[0].arguments["step"] == "approve"


async def test_approving_resumes_the_run(system) -> None:
    workflow = await system.workflows.save(_approval_workflow())
    run = await system.engine.start(workflow)

    await system.approvals.resolve(run.awaiting_approval_id, approved=True)
    resumed = await system.engine.resume(run.id)

    assert resumed.state is WorkflowRunState.SUCCEEDED
    assert [r.step_id for r in resumed.records] == ["draft", "approve", "sent"]


async def test_denying_cancels_the_run(system) -> None:
    workflow = await system.workflows.save(_approval_workflow())
    run = await system.engine.start(workflow)

    await system.approvals.resolve(run.awaiting_approval_id, approved=False, reason="not yet")
    resumed = await system.engine.resume(run.id)

    assert resumed.state is WorkflowRunState.CANCELLED
    assert "denied" in (resumed.error or "")
    assert not any(r.step_id == "sent" for r in resumed.records)


async def test_a_denial_can_be_routed_around(system) -> None:
    """A denial is a decision the graph may handle, not necessarily an end."""
    workflow = await system.workflows.save(
        Workflow(
            id="wfl_denial_route",
            name="Routed denial",
            steps=[
                WorkflowStep(
                    id="approve", kind=StepKind.APPROVAL, question="ok?", if_false="logged"
                ),
                WorkflowStep(id="sent", kind=StepKind.NOTE, label="sent"),
                WorkflowStep(id="logged", kind=StepKind.NOTE, label="declined, logged"),
            ],
        )
    )
    run = await system.engine.start(workflow)
    await system.approvals.resolve(run.awaiting_approval_id, approved=False)
    resumed = await system.engine.resume(run.id)

    assert resumed.state is WorkflowRunState.SUCCEEDED
    assert [r.step_id for r in resumed.records] == ["approve", "logged"]


async def test_resuming_a_still_pending_approval_changes_nothing(system) -> None:
    workflow = await system.workflows.save(_approval_workflow())
    run = await system.engine.start(workflow)

    again = await system.engine.resume(run.id)
    assert again.state is WorkflowRunState.AWAITING_APPROVAL


async def test_a_suspended_run_survives_a_process_restart(settings, clock, tmp_path) -> None:
    """The property the whole design exists for.

    A workflow suspends, the process dies, a *new* engine on the same database
    picks the run up and finishes it. Nothing is carried in memory between the
    two halves except the database file.
    """
    url = f"sqlite+aiosqlite:///{tmp_path}/wf.db"

    first_db = Database(url)
    await first_db.create_all()
    first_store = SqlWorkflowStore(first_db, clock=clock)
    first_system = container.build(
        settings.model_copy(update={"workspace_dir": str(tmp_path)}),
        providers=[ScriptedProvider()],
        clock=clock,
    )
    engine_one = WorkflowEngine(
        store=first_store,
        orchestrator=first_system.orchestrator,
        runtime=first_system.runtime,
        agents=first_system.agents,
        tools=first_system.tools,
        approvals=first_system.approvals,
        bus=first_system.bus,
        clock=clock,
    )
    workflow = await first_store.save(_approval_workflow())
    run = await engine_one.start(workflow)
    approval_id = run.awaiting_approval_id
    assert run.state is WorkflowRunState.AWAITING_APPROVAL
    await first_db.dispose()

    # ---- the process dies here ----

    second_db = Database(url)
    second_store = SqlWorkflowStore(second_db, clock=clock)
    second_system = container.build(
        settings.model_copy(update={"workspace_dir": str(tmp_path)}),
        providers=[ScriptedProvider()],
        clock=clock,
    )
    # The approval broker is also new; the decision is replayed into it, which
    # is what a durable approval store will do for real in M10.
    broker: ApprovalBroker = second_system.approvals
    revived = await broker.create(
        tool="workflow:Needs approval", arguments={"step": "approve"}, run_id=run.id
    )
    stored = await second_store.get_run(run.id)
    assert stored is not None and stored.awaiting_approval_id == approval_id
    stored.awaiting_approval_id = revived.id
    await second_store.save_run(stored)

    engine_two = WorkflowEngine(
        store=second_store,
        orchestrator=second_system.orchestrator,
        runtime=second_system.runtime,
        agents=second_system.agents,
        tools=second_system.tools,
        approvals=broker,
        bus=second_system.bus,
        clock=clock,
    )
    await broker.resolve(revived.id, approved=True)
    finished = await engine_two.resume(run.id)

    assert finished.state is WorkflowRunState.SUCCEEDED
    assert [r.step_id for r in finished.records] == ["draft", "approve", "sent"]
    await second_db.dispose()


async def test_suspended_runs_are_listed_for_recovery(system) -> None:
    workflow = await system.workflows.save(_approval_workflow())
    await system.engine.start(workflow)

    suspended = await system.workflows.suspended_runs()
    assert len(suspended) == 1
    assert suspended[0].state is WorkflowRunState.AWAITING_APPROVAL


# ── Triggers and scheduling ───────────────────────────────────────────────────


async def test_a_due_schedule_fires(system, clock: FrozenClock) -> None:
    workflow = await system.workflows.save(_linear())
    await system.workflows.save_trigger(
        Trigger(workflow_id=workflow.id, kind=TriggerKind.SCHEDULE, interval_seconds=60)
    )
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus, clock=clock)

    assert await scheduler.tick() == 1
    assert len(await system.workflows.runs()) == 1


async def test_a_schedule_does_not_fire_again_until_due(system, clock: FrozenClock) -> None:
    workflow = await system.workflows.save(_linear())
    await system.workflows.save_trigger(
        Trigger(workflow_id=workflow.id, kind=TriggerKind.SCHEDULE, interval_seconds=60)
    )
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus, clock=clock)

    await scheduler.tick()
    assert await scheduler.tick() == 0  # not yet due

    clock.advance(61)
    assert await scheduler.tick() == 1


async def test_a_disabled_trigger_never_fires(system, clock: FrozenClock) -> None:
    workflow = await system.workflows.save(_linear())
    await system.workflows.save_trigger(
        Trigger(workflow_id=workflow.id, kind=TriggerKind.SCHEDULE, enabled=False)
    )
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus, clock=clock)
    assert await scheduler.tick() == 0


async def test_a_disabled_workflow_is_not_started_by_its_trigger(
    system, clock: FrozenClock
) -> None:
    workflow = _linear()
    workflow.enabled = False
    await system.workflows.save(workflow)
    await system.workflows.save_trigger(
        Trigger(workflow_id=workflow.id, kind=TriggerKind.SCHEDULE, interval_seconds=1)
    )
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus, clock=clock)
    assert await scheduler.tick() == 0


async def test_an_event_trigger_starts_a_workflow(system, clock: FrozenClock) -> None:
    """Automation subscribes to the same firehose the UI does."""
    workflow = await system.workflows.save(_linear())
    await system.workflows.save_trigger(
        Trigger(workflow_id=workflow.id, kind=TriggerKind.EVENT, topic="memory.written")
    )
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus, clock=clock)
    await scheduler.start()
    try:
        system.bus.publish("memory.written", {"kind": "decision"})
        for _ in range(200):
            await asyncio.sleep(0.01)
            if await system.workflows.runs():
                break
    finally:
        await scheduler.stop()

    runs = await system.workflows.runs()
    assert runs and runs[0].trigger == "event"


async def test_workflow_events_cannot_trigger_workflows(system, clock: FrozenClock) -> None:
    """Otherwise a workflow that publishes could start itself, forever."""
    workflow = await system.workflows.save(_linear())
    await system.workflows.save_trigger(
        Trigger(workflow_id=workflow.id, kind=TriggerKind.EVENT, topic="workflow.**")
    )
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus, clock=clock)
    await scheduler.start()
    try:
        system.bus.publish("workflow.finished", {"state": "succeeded"})
        await asyncio.sleep(0.15)
    finally:
        await scheduler.stop()

    assert await system.workflows.runs() == []


async def test_recovery_resumes_runs_left_suspended(system) -> None:
    workflow = await system.workflows.save(_approval_workflow())
    run = await system.engine.start(workflow)
    await system.approvals.resolve(run.awaiting_approval_id, approved=True)

    # A fresh scheduler, as if the process had just started.
    scheduler = Scheduler(store=system.workflows, engine=system.engine, bus=system.bus)
    assert await scheduler.recover() == 1

    finished = await system.workflows.get_run(run.id)
    assert finished is not None and finished.state is WorkflowRunState.SUCCEEDED


async def test_lifecycle_events_are_published(system) -> None:
    sub = system.bus.subscribe("workflow.**")
    workflow = await system.workflows.save(_linear())
    await system.engine.start(workflow)

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics[0] == "workflow.started"
    assert topics[-1] == "workflow.finished"


# ── Storage ───────────────────────────────────────────────────────────────────


@pytest.fixture(params=["memory", "sqlite"])
async def store(request: pytest.FixtureRequest, tmp_path, clock: FrozenClock):
    if request.param == "memory":
        yield InMemoryWorkflowStore(clock=clock)
        return
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/wfs.db")
    await db.create_all()
    try:
        yield SqlWorkflowStore(db, clock=clock)
    finally:
        await db.dispose()


async def test_workflows_round_trip(store) -> None:
    saved = await store.save(_approval_workflow())
    fetched = await store.get(saved.id)

    assert fetched is not None
    assert fetched.name == "Needs approval"
    assert [s.id for s in fetched.steps] == ["draft", "approve", "sent"]
    assert fetched.steps[1].kind is StepKind.APPROVAL


async def test_workflows_can_be_updated_and_removed(store) -> None:
    workflow = await store.save(_linear())
    workflow.name = "Renamed"
    await store.save(workflow)

    assert (await store.get(workflow.id)).name == "Renamed"
    assert len(await store.all()) == 1
    assert await store.remove(workflow.id) is True
    assert await store.remove(workflow.id) is False


async def test_runs_round_trip_with_their_context(store) -> None:
    run = WorkflowRun(
        workflow_id="wfl_x",
        workflow_name="X",
        state=WorkflowRunState.AWAITING_APPROVAL,
        cursor="approve",
        context={"trigger": {"body": "hi"}, "steps": {"draft": {"output": "a draft"}}},
        awaiting_approval_id="apr_1",
    )
    await store.save_run(run)
    fetched = await store.get_run(run.id)

    assert fetched is not None
    assert fetched.cursor == "approve"
    assert fetched.context["steps"]["draft"]["output"] == "a draft"
    assert fetched.awaiting_approval_id == "apr_1"


async def test_triggers_round_trip(store) -> None:
    trigger = await store.save_trigger(
        Trigger(workflow_id="wfl_x", kind=TriggerKind.EVENT, topic="memory.**")
    )
    fetched = await store.triggers()

    assert len(fetched) == 1
    assert fetched[0].topic == "memory.**"
    assert await store.remove_trigger(trigger.id) is True
