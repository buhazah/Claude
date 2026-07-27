"""End-to-end runtime behaviour: agent execution, orchestration, runs, metrics."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

from jarvis.agents.spec import AgentSpec, Capability
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.kernel.errors import ProviderError
from jarvis.llm.base import (
    Chunk,
    CompletionRequest,
    Message,
    ModelSpec,
    Role,
    ToolSchema,
    Usage,
)
from jarvis.llm.providers.echo import ECHO_MODEL
from jarvis.runs.models import RunState, StepKind

BROKEN_MODEL = replace(ECHO_MODEL, id="broken-1", provider="broken")


class BrokenProvider:
    name = "broken"

    def models(self) -> list[ModelSpec]:
        return [BROKEN_MODEL]

    def is_available(self) -> bool:
        return True

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        raise ProviderError("provider is down", provider=self.name)
        yield Chunk()  # pragma: no cover - unreachable, keeps this an async generator


async def _collect(stream: AsyncIterator) -> list:
    return [delta async for delta in stream]


async def test_agent_run_streams_tokens_and_completes(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("research")
    deltas = await _collect(jarvis.runtime.stream(spec, "research the market for oat milk"))

    kinds = [d.type for d in deltas]
    assert "token" in kinds
    assert kinds[-1] == "done"

    text = "".join(d.text for d in deltas if d.type == "token")
    assert "oat milk" in text


async def test_successful_run_is_recorded_with_steps_and_cost(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("coding")
    run = await jarvis.runtime.run(spec, "fix the failing test")

    assert run.state is RunState.SUCCEEDED
    assert run.agent_id == "coding"
    assert run.output
    assert [s.kind for s in run.steps] == [StepKind.MEMORY, StepKind.MODEL]
    assert run.steps[-1].detail["model"] == "echo-1"
    assert run.tokens > 0
    assert run.cost_usd == 0.0  # echo is free


async def test_metrics_are_updated_after_a_run(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("copywriter")
    before = jarvis.agents.metrics("copywriter").runs
    await jarvis.runtime.run(spec, "write a headline for a running shoe")
    metrics = jarvis.agents.metrics("copywriter")

    assert metrics.runs == before + 1
    assert metrics.successes == 1
    assert metrics.success_rate == 1.0


async def test_provider_failure_marks_the_run_failed_and_records_it(
    settings, clock: FrozenClock
) -> None:
    jarvis = container.build(settings, providers=[BrokenProvider()], clock=clock)
    spec = jarvis.agents.get("research")

    deltas = await _collect(jarvis.runtime.stream(spec, "research something"))
    assert deltas[-1].type == "error"

    run = jarvis.runs.list()[0]
    assert run.state is RunState.FAILED
    assert run.error and "down" in run.error
    metrics = jarvis.agents.metrics("research")
    assert metrics.failures == 1
    assert metrics.success_rate == 0.0


async def test_conversations_are_written_to_memory(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("research")
    await jarvis.runtime.run(spec, "what is the market size for oat milk")

    recalls = await jarvis.memory.search("oat milk market", scope="research")
    assert recalls
    assert recalls[0].memory.source.startswith("run:")


async def test_recalled_memory_is_injected_into_the_next_run(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("research")
    await jarvis.memory.remember("The user's company is called Northwind", scope="research")

    deltas = await _collect(jarvis.runtime.stream(spec, "research Northwind's competitors"))
    context = next(d for d in deltas if d.type == "context")
    assert context.data["memories"] >= 1


async def test_remember_false_skips_the_memory_write(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("research")
    before = len(jarvis.memory)
    await _collect(jarvis.runtime.stream(spec, "a throwaway question", remember=False))
    assert len(jarvis.memory) == before


async def test_history_is_carried_into_the_completion(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("chief_of_staff")
    history = [
        Message(role=Role.USER, content="my name is Ada"),
        Message(role=Role.ASSISTANT, content="noted"),
    ]
    run = await jarvis.runtime.run(spec, "what did I just tell you", history=history)
    assert run.state is RunState.SUCCEEDED


async def test_orchestrator_routes_then_executes(jarvis: container.Jarvis) -> None:
    deltas = await _collect(jarvis.orchestrator.handle("write a landing page headline"))

    routing = deltas[0]
    assert routing.type == "routing"
    assert routing.data["chosen"] == "copywriter"
    assert routing.data["candidates"][0]["confidence"] > 0
    assert deltas[-1].type == "done"


async def test_orchestrator_honours_an_explicitly_pinned_agent(jarvis: container.Jarvis) -> None:
    deltas = await _collect(
        jarvis.orchestrator.handle("write a landing page headline", agent_id="legal")
    )
    assert deltas[0].data["chosen"] == "legal"


async def test_routing_decision_is_stored_on_the_run(jarvis: container.Jarvis) -> None:
    await _collect(jarvis.orchestrator.handle("build a revenue forecast"))
    run = jarvis.runs.list()[0]
    assert run.routing[0]["agent_id"] == "financial_analyst"
    assert run.steps[0].kind is StepKind.AGENT


async def test_agent_lifecycle_is_published_on_the_bus(jarvis: container.Jarvis) -> None:
    sub = jarvis.bus.subscribe("agent.started", "agent.completed", "routing.**")
    await _collect(jarvis.orchestrator.handle("schedule a meeting with the team"))

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics == ["routing.decided", "agent.started", "agent.completed"]


async def test_runs_are_listed_newest_first(jarvis: container.Jarvis) -> None:
    spec = jarvis.agents.get("research")
    for i in range(3):
        clock_run = await jarvis.runtime.run(spec, f"question {i}")
        assert clock_run.state is RunState.SUCCEEDED

    runs = jarvis.runs.list()
    assert len(runs) >= 3
    assert runs[0].request == "question 2"


async def test_run_store_evicts_beyond_capacity(clock: FrozenClock) -> None:
    from jarvis.runs.models import RunStore

    store = RunStore(clock=clock, capacity=5)
    for i in range(12):
        store.create(request=f"r{i}", agent_id="research")
    assert len(store.list(limit=100)) == 5


async def test_custom_agent_specs_run_on_the_same_runtime(jarvis: container.Jarvis) -> None:
    spec = AgentSpec(
        id="gardener",
        name="Gardener",
        tagline="Knows the plants.",
        system_prompt="You advise on gardening.",
        capabilities=(Capability.PERSONAL,),
        keywords=("garden", "plant", "soil"),
    )
    jarvis.agents.register(spec)

    assert jarvis.agents.route("when should I plant tomatoes")[0].agent_id == "gardener"
    run = await jarvis.runtime.run(spec, "when should I plant tomatoes")
    assert run.state is RunState.SUCCEEDED


def test_container_registers_the_full_system(jarvis: container.Jarvis) -> None:
    assert jarvis.provider_names == ["echo"]
    assert len(jarvis.agents) >= 30
    assert len(jarvis.router.catalog()) >= 1
    assert {t.name for t in jarvis.tools.all()} >= {"memory_search", "memory_write"}


def test_container_always_includes_echo_even_with_no_keys(settings) -> None:
    providers = container.build_providers(settings)
    assert [p.name for p in providers] == ["echo"]


def test_container_registers_configured_providers(settings) -> None:
    settings = settings.model_copy(
        update={
            "anthropic_api_key": "sk-test",
            "openai_api_key": "sk-test",
            "enable_local_llm": True,
        }
    )
    names = [p.name for p in container.build_providers(settings)]
    assert names == ["anthropic", "openai", "local", "echo"]


@pytest.mark.parametrize("agent_id", ["chief_of_staff", "ceo", "security", "voice", "vision"])
async def test_every_agent_archetype_executes(jarvis: container.Jarvis, agent_id: str) -> None:
    run = await jarvis.runtime.run(jarvis.agents.get(agent_id), "handle this for me")
    assert run.state is RunState.SUCCEEDED


class ScriptedProvider:
    """A provider that returns a fixed string, for testing the arbiter."""

    name = "scripted"

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self._model = replace(ECHO_MODEL, id="scripted-1", provider="scripted")

    def models(self) -> list[ModelSpec]:
        return [self._model]

    def is_available(self) -> bool:
        return True

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        yield Chunk(text=self._reply)
        yield Chunk(done=True, usage=Usage(input_tokens=5, output_tokens=2))


def _arbitrating(settings, clock: FrozenClock, reply: str) -> container.Jarvis:
    return container.build(
        settings.model_copy(update={"use_llm_arbiter": True}),
        providers=[ScriptedProvider(reply)],
        clock=clock,
    )


async def test_arbiter_decision_is_honoured(settings, clock: FrozenClock) -> None:
    system = _arbitrating(settings, clock, "marketing")
    # "brand strategy" is genuinely ambiguous between marketing and creative.
    matches = await system.orchestrator.plan("work on the brand")
    assert matches[0].agent_id == "marketing"
    assert "confirmed by arbiter" in matches[0].reasons


async def test_arbiter_reply_that_is_not_a_bare_id_is_ignored(settings, clock: FrozenClock) -> None:
    """A model that restates the request must not be read as a decision."""
    system = _arbitrating(settings, clock, "I think we should work on the brand")
    lexical_first = system.agents.route("work on the brand")[0]

    matches = await system.orchestrator.plan("work on the brand")
    assert matches[0].agent_id == lexical_first.agent_id
    assert "confirmed by arbiter" not in matches[0].reasons


async def test_arbiter_failure_falls_back_to_lexical_routing(settings, clock: FrozenClock) -> None:
    system = container.build(
        settings.model_copy(update={"use_llm_arbiter": True}),
        providers=[BrokenProvider()],
        clock=clock,
    )
    matches = await system.orchestrator.plan("work on the brand")
    assert matches[0].agent_id in {"marketing", "creative_director"}
    assert "confirmed by arbiter" not in matches[0].reasons
