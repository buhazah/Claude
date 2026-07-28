"""The agentic loop: models asking for tools, and Jarvis running them."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

from jarvis.agents.spec import AgentSpec, Capability
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.base import Chunk, CompletionRequest, ModelSpec, Role, ToolCall, ToolSchema, Usage
from jarvis.llm.providers.echo import ECHO_MODEL
from jarvis.runs.models import RunState, StepKind
from jarvis.tools.registry import Grant, Permission

SCRIPTED_MODEL = replace(ECHO_MODEL, id="scripted-1", provider="scripted")


class ScriptedProvider:
    """Replays a fixed script of turns, so the loop's shape is deterministic.

    Each entry is either text (a final answer) or a list of tool calls. This is
    how a real model behaves — it cannot be simulated with the echo provider,
    which never asks for anything.
    """

    name = "scripted"

    def __init__(self, script: list[str | list[ToolCall]]) -> None:
        self._script = script
        self.turns = 0
        self.seen_requests: list[CompletionRequest] = []

    def models(self) -> list[ModelSpec]:
        return [SCRIPTED_MODEL]

    def is_available(self) -> bool:
        return True

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        self.seen_requests.append(request)
        turn = self._script[min(self.turns, len(self._script) - 1)]
        self.turns += 1

        if isinstance(turn, str):
            yield Chunk(text=turn)
        else:
            for call in turn:
                yield Chunk(tool_call=call)
        yield Chunk(done=True, usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.0001))


def _system(settings, clock: FrozenClock, script: list, **overrides):
    return container.build(
        settings.model_copy(update=overrides),
        providers=[ScriptedProvider(script)],
        clock=clock,
    )


TOOL_AGENT = AgentSpec(
    id="tooler",
    name="Tooler",
    tagline="Uses tools.",
    system_prompt="You use tools to answer.",
    capabilities=(Capability.OPERATIONS,),
    keywords=("tool",),
    tools=("read_file", "write_file", "run_command"),
)


async def _collect(stream: AsyncIterator) -> list:
    return [delta async for delta in stream]


async def test_a_tool_call_is_executed_and_its_result_fed_back(settings, clock, tmp_path) -> None:
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="write_file", arguments={"path": "note.txt", "content": "hi"})],
            "I wrote the file.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)

    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "write a note"))
    kinds = [d.type for d in deltas]

    assert "tool" in kinds and "tool_result" in kinds
    assert (tmp_path / "note.txt").read_text() == "hi"

    result = next(d for d in deltas if d.type == "tool_result")
    assert result.data["ok"] is True

    # The final answer is the model's second turn, after seeing the result.
    assert "I wrote the file." in "".join(d.text for d in deltas if d.type == "token")


async def test_the_tool_result_is_replayed_to_the_model(settings, clock, tmp_path) -> None:
    (tmp_path / "data.txt").write_text("the answer is 42")
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="read_file", arguments={"path": "data.txt"})],
            "It says 42.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)
    await _collect(system.runtime.stream(TOOL_AGENT, "what does data.txt say"))

    provider = next(iter(system.router.providers.values()))
    second = provider.seen_requests[1]  # type: ignore[attr-defined]

    assistant = next(m for m in second.messages if m.role is Role.ASSISTANT and m.tool_calls)
    assert assistant.tool_calls[0].name == "read_file"

    tool_message = next(m for m in second.messages if m.role is Role.TOOL)
    assert "42" in tool_message.content
    assert tool_message.tool_call_id == "c1"


async def test_tool_calls_are_recorded_as_run_steps(settings, clock, tmp_path) -> None:
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="list_files", arguments={})],
            "Nothing there.",
        ],
        workspace_dir=str(tmp_path),
    )
    spec = TOOL_AGENT.model_copy(update={"tools": ("list_files",)})
    system.agents.register(spec)

    run = await system.runtime.run(spec, "what is in the workspace")
    kinds = [s.kind for s in run.steps]

    assert kinds == [StepKind.MEMORY, StepKind.MODEL, StepKind.TOOL, StepKind.MODEL]
    assert run.state is RunState.SUCCEEDED


async def test_a_failing_tool_is_reported_to_the_model_not_raised(
    settings, clock, tmp_path
) -> None:
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="read_file", arguments={"path": "missing.txt"})],
            "That file does not exist.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)

    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "read missing.txt"))
    assert not any(d.type == "error" for d in deltas)

    run = (await system.runs.list())[0]
    assert run.state is RunState.SUCCEEDED


async def test_an_unknown_tool_does_not_kill_the_run(settings, clock, tmp_path) -> None:
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="does_not_exist", arguments={})],
            "I could not do that.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)

    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "do something"))
    result = next(d for d in deltas if d.type == "tool_result")

    assert result.data["ok"] is False
    assert (await system.runs.list())[0].state is RunState.SUCCEEDED


async def test_several_tool_calls_in_one_turn_all_execute(settings, clock, tmp_path) -> None:
    system = _system(
        settings,
        clock,
        [
            [
                ToolCall(id="c1", name="write_file", arguments={"path": "a.txt", "content": "A"}),
                ToolCall(id="c2", name="write_file", arguments={"path": "b.txt", "content": "B"}),
            ],
            "Both written.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)
    await _collect(system.runtime.stream(TOOL_AGENT, "write two files"))

    assert (tmp_path / "a.txt").read_text() == "A"
    assert (tmp_path / "b.txt").read_text() == "B"


async def test_the_loop_stops_at_the_iteration_ceiling(settings, clock, tmp_path) -> None:
    """A model that never stops asking must be cut off, and say so."""
    system = _system(
        settings,
        clock,
        [[ToolCall(id="c1", name="list_files", arguments={})]],  # asks forever
        workspace_dir=str(tmp_path),
    )
    spec = TOOL_AGENT.model_copy(update={"tools": ("list_files",)})
    system.agents.register(spec)

    from jarvis.agents.runtime import MAX_TOOL_ITERATIONS

    run = await system.runtime.run(spec, "loop forever")
    provider = next(iter(system.router.providers.values()))

    assert provider.turns == MAX_TOOL_ITERATIONS  # type: ignore[attr-defined]
    assert "stopped after" in run.output
    assert run.state is RunState.SUCCEEDED


async def test_cost_accumulates_across_tool_rounds(settings, clock, tmp_path) -> None:
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="list_files", arguments={})],
            "Done.",
        ],
        workspace_dir=str(tmp_path),
    )
    spec = TOOL_AGENT.model_copy(update={"tools": ("list_files",)})
    system.agents.register(spec)

    run = await system.runtime.run(spec, "look around")
    # Two model turns at 15 tokens each, not one.
    assert run.tokens == 30
    assert run.cost_usd == pytest.approx(0.0002)


async def test_a_run_with_no_tool_calls_is_a_single_turn(settings, clock, tmp_path) -> None:
    system = _system(settings, clock, ["Just an answer."], workspace_dir=str(tmp_path))
    system.agents.register(TOOL_AGENT)

    run = await system.runtime.run(TOOL_AGENT, "no tools needed")
    provider = next(iter(system.router.providers.values()))

    assert provider.turns == 1  # type: ignore[attr-defined]
    assert [s.kind for s in run.steps] == [StepKind.MEMORY, StepKind.MODEL]


# ── Approvals ─────────────────────────────────────────────────────────────────


async def test_a_dangerous_tool_suspends_until_approved(settings, clock, tmp_path) -> None:
    """The whole point of the permission wall: the run parks, then resumes."""
    import asyncio

    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="run_command", arguments={"command": "echo hello"})],
            "It printed hello.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)

    async def approve_when_asked() -> None:
        for _ in range(200):
            await asyncio.sleep(0.01)
            if pending := system.approvals.pending():
                await system.approvals.resolve(pending[0].id, approved=True)
                return
        raise AssertionError("no approval was ever requested")

    approver = asyncio.create_task(approve_when_asked())
    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "run echo"))
    await approver

    result = next(d for d in deltas if d.type == "tool_result")
    assert result.data["ok"] is True
    assert "hello" in result.data["result"]


async def test_a_denied_tool_reports_refusal_and_the_run_continues(
    settings, clock, tmp_path
) -> None:
    import asyncio

    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="run_command", arguments={"command": "rm -rf /"})],
            "Understood, I will not do that.",
        ],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)

    async def deny_when_asked() -> None:
        for _ in range(200):
            await asyncio.sleep(0.01)
            if pending := system.approvals.pending():
                await system.approvals.resolve(
                    pending[0].id, approved=False, reason="absolutely not"
                )
                return

    denier = asyncio.create_task(deny_when_asked())
    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "delete everything"))
    await denier

    result = next(d for d in deltas if d.type == "tool_result")
    assert result.data["ok"] is False
    assert "denied" in result.data["result"] or "absolutely not" in result.data["result"]
    assert (await system.runs.list())[0].state is RunState.SUCCEEDED


async def test_an_unanswered_approval_expires_into_denial(settings, clock, tmp_path) -> None:
    """Fail closed: nobody home must never mean yes."""
    system = _system(
        settings,
        clock,
        [
            [ToolCall(id="c1", name="run_command", arguments={"command": "echo hi"})],
            "I could not run it.",
        ],
        workspace_dir=str(tmp_path),
        approval_timeout_s=0.05,
    )
    system.agents.register(TOOL_AGENT)

    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "run echo"))
    result = next(d for d in deltas if d.type == "tool_result")

    assert result.data["ok"] is False
    assert "expired" in result.data["result"]


async def test_approval_events_are_published(settings, clock, tmp_path) -> None:
    import asyncio

    system = _system(
        settings,
        clock,
        [[ToolCall(id="c1", name="run_command", arguments={"command": "echo hi"})], "done"],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)
    sub = system.bus.subscribe("approval.**")

    async def approve() -> None:
        for _ in range(200):
            await asyncio.sleep(0.01)
            if pending := system.approvals.pending():
                await system.approvals.resolve(pending[0].id, approved=True)
                return

    task = asyncio.create_task(approve())
    await _collect(system.runtime.stream(TOOL_AGENT, "run echo"))
    await task

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics == ["approval.requested", "approval.approved"]


async def test_deciding_twice_does_not_flip_the_outcome(settings, clock) -> None:
    system = _system(settings, clock, ["x"])
    import asyncio

    async def request() -> None:
        await system.approvals.request(tool="run_command", arguments={}, timeout_s=5)

    task = asyncio.create_task(request())
    for _ in range(200):
        await asyncio.sleep(0.01)
        if system.approvals.pending():
            break

    approval = system.approvals.pending()[0]
    await system.approvals.resolve(approval.id, approved=True)
    again = await system.approvals.resolve(approval.id, approved=False)
    await task

    assert again.state.value == "approved"


async def test_auto_approve_grants_skip_the_gate(settings, clock, tmp_path) -> None:
    system = _system(
        settings,
        clock,
        [[ToolCall(id="c1", name="run_command", arguments={"command": "echo hi"})], "done"],
        workspace_dir=str(tmp_path),
    )
    system.agents.register(TOOL_AGENT)
    system.tools._grants = [Grant("*", Permission.DANGEROUS, auto_approve=True)]

    deltas = await _collect(system.runtime.stream(TOOL_AGENT, "run echo"))
    result = next(d for d in deltas if d.type == "tool_result")

    assert result.data["ok"] is True
    assert system.approvals.pending() == []


def test_tool_calls_serialise_for_the_wire() -> None:
    call = ToolCall(id="c1", name="write_file", arguments={"path": "a.txt"})
    assert json.loads(call.model_dump_json())["arguments"]["path"] == "a.txt"
