from __future__ import annotations

import pytest

from jarvis.kernel.bus import EventBus, topic_matches
from jarvis.kernel.clock import FrozenClock


@pytest.mark.parametrize(
    ("pattern", "topic", "expected"),
    [
        ("agent.started", "agent.started", True),
        ("agent.*", "agent.started", True),
        ("agent.*", "agent.tool.called", False),
        ("agent.**", "agent.tool.called", True),
        ("**", "anything.at.all", True),
        ("*.started", "agent.started", True),
        ("agent.**.called", "agent.tool.called", True),
        ("agent.**.called", "agent.tool.failed", False),
        ("agent.started", "agent.completed", False),
        ("llm.*", "agent.started", False),
    ],
)
def test_topic_matching(pattern: str, topic: str, expected: bool) -> None:
    assert topic_matches(pattern, topic) is expected


def test_publish_fans_out_only_to_interested_subscribers(clock: FrozenClock) -> None:
    bus = EventBus(clock=clock)
    agents = bus.subscribe("agent.**")
    everything = bus.subscribe("**")

    bus.publish("agent.started", {"agent": "research"})
    bus.publish("llm.selected", {"model": "echo-1"})

    assert agents.queue.qsize() == 1
    assert everything.queue.qsize() == 2
    assert bus.published_count == 2


def test_slow_subscriber_drops_its_own_events_without_blocking(clock: FrozenClock) -> None:
    bus = EventBus(clock=clock)
    slow = bus.subscribe("**", maxsize=2)
    healthy = bus.subscribe("**", maxsize=100)

    for i in range(10):
        bus.publish("tick", {"i": i})

    assert slow.queue.qsize() == 2
    assert slow.dropped == 8
    # The slow consumer must not have cost the healthy one anything.
    assert healthy.queue.qsize() == 10
    assert healthy.dropped == 0

    # And it keeps the newest events, not the stalest.
    newest = [slow.queue.get_nowait().payload["i"] for _ in range(2)]
    assert newest == [8, 9]


def test_close_removes_subscription(clock: FrozenClock) -> None:
    bus = EventBus(clock=clock)
    sub = bus.subscribe("**")
    assert bus.subscriber_count == 1
    sub.close()
    assert bus.subscriber_count == 0
    bus.publish("agent.started", {})
    assert sub.queue.qsize() == 0


async def test_events_iterator_yields_published_events(clock: FrozenClock) -> None:
    bus = EventBus(clock=clock)
    async with bus.subscribe("run.*") as sub:
        bus.publish("run.started", {"id": "run_1"})
        event = await anext(sub.events())
    assert event.topic == "run.started"
    assert event.payload["id"] == "run_1"
    assert event.timestamp == clock.now().isoformat()
