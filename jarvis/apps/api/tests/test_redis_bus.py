"""Redis bus tests.

Skipped unless ``JARVIS_TEST_REDIS_URL`` points at a live server, so the suite
still runs with no network. The behaviour that matters is not "Redis works" —
it is that Jarvis stays correct when Redis is absent, and that a second node
sees the first node's events without the first node seeing them twice.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from jarvis.kernel.clock import FrozenClock
from jarvis.kernel.redis_bus import RedisEventBus

REDIS_URL = os.getenv("JARVIS_TEST_REDIS_URL", "")
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="JARVIS_TEST_REDIS_URL not set")


async def test_falls_back_to_local_only_when_redis_is_unreachable(clock: FrozenClock) -> None:
    """A dead Redis must degrade to single-node, never break the kernel."""
    bus = RedisEventBus("redis://127.0.0.1:1/", clock=clock)
    await bus.start()
    assert bus.connected is False

    sub = bus.subscribe("agent.**")
    bus.publish("agent.started", {"agent": "research"})

    assert sub.queue.qsize() == 1
    await bus.stop()


@needs_redis
async def test_local_subscribers_receive_events_exactly_once(clock: FrozenClock) -> None:
    """The publishing node must not see its own event echoed back from Redis."""
    bus = RedisEventBus(REDIS_URL, clock=clock, node_id="node-a")
    await bus.start()
    assert bus.connected is True

    sub = bus.subscribe("agent.**")
    bus.publish("agent.started", {"agent": "research"})
    await asyncio.sleep(0.3)  # long enough for a round trip to have echoed

    assert sub.queue.qsize() == 1
    await bus.stop()


@needs_redis
async def test_events_cross_between_nodes(clock: FrozenClock) -> None:
    """The whole reason this exists: a worker's event reaches the API process."""
    worker = RedisEventBus(REDIS_URL, clock=clock, node_id="worker")
    api = RedisEventBus(REDIS_URL, clock=clock, node_id="api")
    await worker.start()
    await api.start()
    await asyncio.sleep(0.2)  # let both subscriptions register

    watching = api.subscribe("agent.**")
    worker.publish("agent.completed", {"agent": "research", "tokens": 42})

    event = await asyncio.wait_for(anext(watching.events()), timeout=5)
    assert event.topic == "agent.completed"
    assert event.payload["tokens"] == 42

    await worker.stop()
    await api.stop()


@needs_redis
async def test_a_node_only_receives_topics_it_subscribed_to(clock: FrozenClock) -> None:
    worker = RedisEventBus(REDIS_URL, clock=clock, node_id="worker-2")
    api = RedisEventBus(REDIS_URL, clock=clock, node_id="api-2")
    await worker.start()
    await api.start()
    await asyncio.sleep(0.2)

    watching = api.subscribe("memory.**")
    worker.publish("agent.started", {"agent": "coding"})
    worker.publish("memory.written", {"kind": "decision"})

    event = await asyncio.wait_for(anext(watching.events()), timeout=5)
    assert event.topic == "memory.written"

    await worker.stop()
    await api.stop()
