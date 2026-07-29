from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import FrozenClock
from jarvis.kernel.errors import AllProvidersFailedError, ProviderError
from jarvis.llm.base import (
    Chunk,
    CompletionRequest,
    Message,
    Modality,
    ModelSpec,
    Privacy,
    Role,
    RoutingPolicy,
    ToolSchema,
    Usage,
)
from jarvis.llm.providers.echo import EchoProvider
from jarvis.llm.router import CIRCUIT_THRESHOLD, ModelRouter


def _model(
    id: str,
    *,
    provider: str,
    quality: float,
    cost: float,
    latency: float,
    context: int = 200_000,
    privacy: Privacy = Privacy.CLOUD,
    modalities: tuple[Modality, ...] = (Modality.TEXT,),
    tools: bool = True,
) -> ModelSpec:
    return ModelSpec(
        id=id,
        provider=provider,
        context_window=context,
        max_output=8192,
        input_cost_per_mtok=cost,
        output_cost_per_mtok=cost * 4,
        quality=quality,
        latency_score=latency,
        privacy=privacy,
        modalities=modalities,
        supports_tools=tools,
    )


class FakeProvider:
    """A provider whose models and failure behaviour the test controls."""

    def __init__(
        self,
        name: str,
        models: list[ModelSpec],
        *,
        fail: Exception | None = None,
        fail_after_tokens: int = 0,
        available: bool = True,
    ) -> None:
        self.name = name
        self._models = models
        self._fail = fail
        self._fail_after_tokens = fail_after_tokens
        self._available = available
        self.calls = 0

    def models(self) -> list[ModelSpec]:
        return self._models

    def is_available(self) -> bool:
        return self._available

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        self.calls += 1
        for i in range(self._fail_after_tokens):
            yield Chunk(text=f"t{i} ")
        if self._fail:
            raise self._fail
        yield Chunk(text=f"from {model.id}")
        yield Chunk(done=True, usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.001))


def _request(**kwargs: object) -> CompletionRequest:
    kwargs.setdefault("messages", [Message(role=Role.USER, content="hello")])
    return CompletionRequest(**kwargs)  # type: ignore[arg-type]


def test_quality_policy_prefers_the_strongest_model() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("strong", provider="p", quality=0.98, cost=15.0, latency=0.4),
                    _model("cheap", provider="p", quality=0.6, cost=0.2, latency=0.95),
                ],
            )
        ]
    )
    assert router.select(_request(policy=RoutingPolicy.QUALITY)).id == "strong"


def test_cheap_policy_prefers_the_cheapest_model() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("strong", provider="p", quality=0.98, cost=15.0, latency=0.4),
                    _model("cheap", provider="p", quality=0.6, cost=0.2, latency=0.95),
                ],
            )
        ]
    )
    assert router.select(_request(policy=RoutingPolicy.CHEAP)).id == "cheap"


def test_fast_policy_prefers_the_lowest_latency_model() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("slow", provider="p", quality=0.95, cost=1.0, latency=0.2),
                    _model("quick", provider="p", quality=0.7, cost=1.0, latency=0.99),
                ],
            )
        ]
    )
    assert router.select(_request(policy=RoutingPolicy.FAST)).id == "quick"


def test_privacy_floor_eliminates_cloud_models() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("cloud", provider="p", quality=0.99, cost=1.0, latency=0.9),
                    _model(
                        "onprem",
                        provider="p",
                        quality=0.5,
                        cost=0.0,
                        latency=0.3,
                        privacy=Privacy.LOCAL,
                    ),
                ],
            )
        ]
    )
    selected = router.select(_request(policy=RoutingPolicy.QUALITY, min_privacy=Privacy.LOCAL))
    assert selected.id == "onprem"


def test_context_window_is_a_hard_constraint() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model(
                        "small", provider="p", quality=0.99, cost=0.1, latency=0.99, context=1000
                    ),
                    _model(
                        "large", provider="p", quality=0.5, cost=9.0, latency=0.2, context=200_000
                    ),
                ],
            )
        ]
    )
    selected = router.select(_request(estimated_input_tokens=50_000, max_output_tokens=4000))
    assert selected.id == "large"


def test_tool_support_is_a_hard_constraint() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model(
                        "no-tools", provider="p", quality=0.99, cost=0.1, latency=0.99, tools=False
                    ),
                    _model("tools", provider="p", quality=0.5, cost=5.0, latency=0.3),
                ],
            )
        ]
    )
    assert router.select(_request(needs_tools=True)).id == "tools"


def test_vision_requirement_filters_text_only_models() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("text", provider="p", quality=0.99, cost=0.1, latency=0.9),
                    _model(
                        "vision",
                        provider="p",
                        quality=0.6,
                        cost=2.0,
                        latency=0.5,
                        modalities=(Modality.TEXT, Modality.VISION),
                    ),
                ],
            )
        ]
    )
    selected = router.select(_request(required_modalities=(Modality.VISION,)))
    assert selected.id == "vision"


def test_no_eligible_model_raises() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p", [_model("m", provider="p", quality=0.9, cost=1, latency=0.5, context=100)]
            )
        ]
    )
    with pytest.raises(AllProvidersFailedError):
        router.select(_request(estimated_input_tokens=999_999))


def test_pinned_model_overrides_scoring() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("best", provider="p", quality=0.99, cost=0.1, latency=0.99),
                    _model("pinned", provider="p", quality=0.1, cost=99.0, latency=0.1),
                ],
            )
        ]
    )
    assert router.select(_request(model_id="pinned")).id == "pinned"


def test_unavailable_provider_is_skipped() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "keyless",
                [_model("a", provider="keyless", quality=0.99, cost=0.1, latency=0.9)],
                available=False,
            ),
            FakeProvider(
                "ready", [_model("b", provider="ready", quality=0.4, cost=5.0, latency=0.2)]
            ),
        ]
    )
    assert router.select(_request()).id == "b"


async def test_ranking_is_deterministic_across_calls() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "p",
                [
                    _model("a", provider="p", quality=0.8, cost=1.0, latency=0.5),
                    _model("b", provider="p", quality=0.8, cost=1.0, latency=0.5),
                ],
            )
        ]
    )
    first = [c.model.id for c in router.rank(_request())]
    second = [c.model.id for c in router.rank(_request())]
    assert first == second == ["a", "b"]


async def test_failure_before_first_token_falls_back_to_next_model() -> None:
    failing = FakeProvider(
        "bad",
        [_model("bad-1", provider="bad", quality=0.99, cost=0.1, latency=0.99)],
        fail=ProviderError("boom", provider="bad"),
    )
    good = FakeProvider(
        "good", [_model("good-1", provider="good", quality=0.5, cost=1.0, latency=0.5)]
    )
    router = ModelRouter([failing, good])

    text = "".join([c.text async for c in router.stream(_request())])
    assert "from good-1" in text
    assert failing.calls == 1 and good.calls == 1


async def test_failure_after_first_token_does_not_splice_two_models() -> None:
    failing = FakeProvider(
        "bad",
        [_model("bad-1", provider="bad", quality=0.99, cost=0.1, latency=0.99)],
        fail=ProviderError("died mid-stream", provider="bad"),
        fail_after_tokens=2,
    )
    good = FakeProvider(
        "good", [_model("good-1", provider="good", quality=0.5, cost=1.0, latency=0.5)]
    )
    router = ModelRouter([failing, good])

    with pytest.raises(ProviderError):
        async for _ in router.stream(_request()):
            pass
    assert good.calls == 0


async def test_all_candidates_failing_raises_with_the_failure_map() -> None:
    router = ModelRouter(
        [
            FakeProvider(
                "a",
                [_model("a-1", provider="a", quality=0.9, cost=1.0, latency=0.5)],
                fail=ProviderError("a down", provider="a"),
            ),
            FakeProvider(
                "b",
                [_model("b-1", provider="b", quality=0.8, cost=1.0, latency=0.5)],
                fail=ProviderError("b down", provider="b"),
            ),
        ]
    )
    with pytest.raises(AllProvidersFailedError) as exc:
        async for _ in router.stream(_request(), max_fallbacks=5):
            pass
    assert set(exc.value.failures) == {"a-1", "b-1"}


async def test_circuit_opens_after_repeated_failures_and_recovers_after_cooldown() -> None:
    clock = FrozenClock()
    bad = FakeProvider(
        "bad",
        [_model("bad-1", provider="bad", quality=0.99, cost=0.1, latency=0.99)],
        fail=ProviderError("boom", provider="bad"),
    )
    good = FakeProvider(
        "good", [_model("good-1", provider="good", quality=0.5, cost=1.0, latency=0.5)]
    )
    router = ModelRouter([bad, good], clock=clock)

    for _ in range(CIRCUIT_THRESHOLD):
        async for _chunk in router.stream(_request()):
            pass
    calls_at_trip = bad.calls
    assert calls_at_trip == CIRCUIT_THRESHOLD

    # Circuit open: the failing provider is no longer attempted at all.
    async for _chunk in router.stream(_request()):
        pass
    assert bad.calls == calls_at_trip

    clock.advance(61)
    async for _chunk in router.stream(_request()):
        pass
    assert bad.calls == calls_at_trip + 1


async def test_stream_publishes_selection_and_completion_events() -> None:
    bus = EventBus(clock=FrozenClock())
    router = ModelRouter([EchoProvider()], bus=bus)
    sub = bus.subscribe("llm.**")

    async for _ in router.stream(_request()):
        pass

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics == ["llm.selected", "llm.completed"]


async def test_complete_reports_the_model_that_actually_ran() -> None:
    failing = FakeProvider(
        "bad",
        [_model("bad-1", provider="bad", quality=0.99, cost=0.1, latency=0.99)],
        fail=ProviderError("boom", provider="bad"),
    )
    good = FakeProvider(
        "good", [_model("good-1", provider="good", quality=0.5, cost=1.0, latency=0.5)]
    )
    router = ModelRouter([failing, good])

    completion = await router.complete(_request())
    assert completion.model_id == "good-1"
    assert completion.provider == "good"
    assert completion.usage.output_tokens == 5


async def test_echo_provider_is_deterministic() -> None:
    router = ModelRouter([EchoProvider()])
    first = await router.complete(_request())
    second = await router.complete(_request())
    assert first.text == second.text
    assert first.usage.cost_usd == 0.0
