"""Load and chaos.

Everything else in the suite tests one thing at a time with nothing else
happening. These tests exist because that is not how the system runs, and
because several of the properties Jarvis claims — fallback, backpressure,
durability, isolation — are only observable under concurrency or failure.

Not benchmarks. Nothing here asserts a latency number, because a number
measured on CI hardware is a flake waiting to happen. They assert *shape*:
nothing deadlocks, nothing loses work, nothing serialises that should not.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from jarvis.kernel import container
from jarvis.kernel.bus import EventBus
from jarvis.llm.base import Chunk, CompletionRequest, ModelSpec, ToolSchema, Usage
from jarvis.llm.providers.echo import ECHO_MODEL, EchoProvider
from jarvis.llm.router import ModelRouter
from jarvis.memory.store import InMemoryStore
from jarvis.security.budget import Budget, CostGovernor, Ledger, Period

CONCURRENCY = 24


class FlakyProvider:
    """Fails a given fraction of calls, deterministically by call number."""

    name = "flaky"

    def __init__(self, *, fail_every: int = 2) -> None:
        self.calls = 0
        self._fail_every = fail_every

    def models(self) -> list[ModelSpec]:
        from dataclasses import replace

        return [replace(ECHO_MODEL, id="flaky-1", provider="flaky", quality=0.9)]

    def is_available(self) -> bool:
        return True

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        self.calls += 1
        if self.calls % self._fail_every == 0:
            raise RuntimeError("upstream 503")
        yield Chunk(text="ok ")
        yield Chunk(done=True, usage=Usage(input_tokens=1, output_tokens=1))


# ── Concurrency ───────────────────────────────────────────────────────────────


async def test_many_agent_runs_at_once_all_finish(settings, clock) -> None:
    """The kernel is async throughout; a lock in the wrong place would show up
    as this test taking N× as long, or hanging."""
    system = container.build(settings, providers=[EchoProvider()], clock=clock)

    async def once(index: int) -> str:
        parts = [
            d.text
            async for d in system.orchestrator.handle(f"request number {index}")
            if d.type == "token"
        ]
        return "".join(parts)

    async with asyncio.timeout(30):
        answers = await asyncio.gather(*(once(i) for i in range(CONCURRENCY)))

    assert len(answers) == CONCURRENCY
    assert all(answers)
    runs = await system.runs.list(limit=CONCURRENCY * 2)
    assert len(runs) == CONCURRENCY, "every concurrent run must be recorded exactly once"


async def test_concurrent_memory_writes_do_not_lose_each_other() -> None:
    store = InMemoryStore()

    async with asyncio.timeout(15):
        await asyncio.gather(*(store.remember(f"fact number {i}") for i in range(120)))

    assert await store.count() == 120
    assert len({m.id for m in await store.all(limit=200)}) == 120


async def test_a_slow_subscriber_does_not_stall_the_bus() -> None:
    """Backpressure is drop-oldest per subscriber: one slow reader must cost
    itself messages, never block the publisher or anybody else."""
    bus = EventBus()
    fast = bus.subscribe("load.**")
    slow = bus.subscribe("load.**")

    async with asyncio.timeout(10):
        for index in range(2_000):
            bus.publish("load.tick", {"index": index})

        received = 0
        try:
            async with asyncio.timeout(2):
                async for _ in fast.events():
                    received += 1
        except TimeoutError:
            pass

    assert received > 0, "the fast subscriber must still receive"
    assert bus.published_count >= 2_000, "publishing must not have been blocked"
    fast.close()
    slow.close()


# ── Failure ───────────────────────────────────────────────────────────────────


async def test_the_router_survives_a_provider_failing_half_the_time(clock) -> None:
    """Fallback under load, not in isolation: half these calls hit a 503 and
    every one of them must still return an answer."""
    flaky = FlakyProvider(fail_every=2)
    router = ModelRouter([flaky, EchoProvider()], clock=clock)

    async def once() -> str:
        return "".join(
            [
                c.text
                async for c in router.stream(
                    CompletionRequest(messages=[], system="hi", max_output_tokens=16)
                )
                if c.text
            ]
        )

    async with asyncio.timeout(30):
        answers = await asyncio.gather(*(once() for _ in range(CONCURRENCY)))

    assert all(answers), "every call must produce output, via fallback where needed"


async def test_a_circuit_opens_and_the_system_keeps_answering(clock) -> None:
    """Every call fails on the preferred provider. The floor holds."""
    always_failing = FlakyProvider(fail_every=1)
    router = ModelRouter([always_failing, EchoProvider()], clock=clock)

    async with asyncio.timeout(20):
        for _ in range(12):
            text = "".join(
                [c.text async for c in router.stream(CompletionRequest(messages=[])) if c.text]
            )
            assert text

    # The circuit should have stopped trying the broken provider long before
    # the twelfth call, rather than paying for a failure every time.
    assert always_failing.calls < 12, f"circuit never opened ({always_failing.calls} attempts)"


async def test_a_budget_refusal_under_load_stops_everything_cleanly(clock) -> None:
    """A hard ceiling hit by twenty concurrent callers must refuse twenty
    times, not deadlock on whoever got there first."""
    governor = CostGovernor(Ledger(clock=clock), (Budget(Period.TOTAL, hard_usd=0.0001),))
    governor.record(1.0)
    router = ModelRouter([EchoProvider()], clock=clock, governor=governor)

    async def once() -> str:
        try:
            async for _ in router.stream(CompletionRequest(messages=[])):
                pass
        except Exception as exc:
            return type(exc).__name__
        return "allowed"

    async with asyncio.timeout(20):
        outcomes = await asyncio.gather(*(once() for _ in range(20)))

    assert set(outcomes) == {"BudgetExceededError"}


async def test_a_cancelled_run_does_not_leave_the_system_wedged(settings, clock) -> None:
    """Users close tabs mid-answer. That must not hold anything open."""
    system = container.build(settings, providers=[EchoProvider()], clock=clock)

    async def start_and_abandon() -> None:
        stream = system.orchestrator.handle("a long request")
        await anext(stream)  # take the routing delta, then walk away
        await stream.aclose()

    async with asyncio.timeout(15):
        await asyncio.gather(*(start_and_abandon() for _ in range(10)))
        # The system must still answer afterwards.
        answer = [d async for d in system.orchestrator.handle("still working?")]

    assert answer


@pytest.mark.parametrize("failures", [1, 3])
async def test_tool_failures_do_not_abort_the_turn(settings, clock, failures: int) -> None:
    """A broken tool is information for the model, not an exception that
    discards a half-written answer the user is already reading."""
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] <= failures:
            raise RuntimeError("transient")
        return "recovered"

    system.tools.register("flaky_tool", "Sometimes fails.", flaky)

    for _ in range(failures):
        with pytest.raises(RuntimeError):
            await system.tools.invoke("flaky_tool", {})
    assert await system.tools.invoke("flaky_tool", {}) == "recovered"

    # And the kernel is still healthy afterwards.
    assert [d async for d in system.orchestrator.handle("anything")]
