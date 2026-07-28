"""Asynchronous event bus.

Every meaningful state change in Jarvis is published here: token deltas, tool
calls, memory writes, run transitions. The UI's live activity feed, the
observability layer and workflow triggers are all just subscribers, which is
why none of those concerns leak into the runtime code.

Topics are dot-hierarchical and matched with two wildcards:

    ``agent.*``   one segment   → matches ``agent.started`` not ``agent.tool.called``
    ``agent.**``  any depth     → matches both
    ``**``        everything    → the firehose

Delivery is per-subscriber and bounded. A subscriber that cannot keep up drops
*its own* oldest events and reports the loss; publishers are never blocked by a
slow consumer, because a stalled UI must not be able to stall the kernel.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.ids import new_id

log = structlog.get_logger(__name__)

DEFAULT_QUEUE_SIZE = 512


@dataclass(slots=True)
class Event:
    """An immutable fact about something that happened."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("evt"))
    timestamp: str = ""
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "payload": self.payload,
        }


def topic_matches(pattern: str, topic: str) -> bool:
    """Match a topic against a pattern containing ``*`` / ``**`` segments."""
    if pattern == topic:
        return True
    pattern_parts = pattern.split(".")
    topic_parts = topic.split(".")

    def walk(pi: int, ti: int) -> bool:
        while pi < len(pattern_parts):
            part = pattern_parts[pi]
            if part == "**":
                # ``**`` is greedy but must be able to give segments back.
                if pi == len(pattern_parts) - 1:
                    return True
                return any(walk(pi + 1, t) for t in range(ti, len(topic_parts) + 1))
            if ti >= len(topic_parts):
                return False
            if part != "*" and part != topic_parts[ti]:
                return False
            pi += 1
            ti += 1
        return ti == len(topic_parts)

    return walk(0, 0)


class Subscription:
    """A bounded, independently-buffered view of the event stream."""

    def __init__(self, patterns: tuple[str, ...], maxsize: int, on_close: Any) -> None:
        self.patterns = patterns
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0
        self._on_close = on_close
        self._closed = False

    def wants(self, topic: str) -> bool:
        return any(topic_matches(p, topic) for p in self.patterns)

    def offer(self, event: Event) -> None:
        """Non-blocking delivery; drops this subscriber's oldest event if full."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.dropped += 1
            with contextlib.suppress(asyncio.QueueFull):
                self.queue.put_nowait(event)

    async def __aenter__(self) -> Subscription:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._on_close(self)

    async def events(self) -> AsyncIterator[Event]:
        """Yield events until the subscription is closed."""
        while not self._closed:
            try:
                yield await asyncio.wait_for(self.queue.get(), timeout=0.25)
            except TimeoutError:
                continue


class EventBus:
    """In-process pub/sub. The port a Redis/NATS adapter would implement."""

    def __init__(self, clock: Clock = SYSTEM_CLOCK) -> None:
        self._subscriptions: list[Subscription] = []
        self._clock = clock
        self._published = 0

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    @property
    def published_count(self) -> int:
        return self._published

    def subscribe(self, *patterns: str, maxsize: int = DEFAULT_QUEUE_SIZE) -> Subscription:
        sub = Subscription(patterns or ("**",), maxsize, self._unsubscribe)
        self._subscriptions.append(sub)
        return sub

    def _unsubscribe(self, sub: Subscription) -> None:
        with contextlib.suppress(ValueError):
            self._subscriptions.remove(sub)

    def publish(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
        *,
        run_id: str | None = None,
    ) -> Event:
        """Publish synchronously — delivery is a queue put, never awaits a consumer."""
        event = Event(
            topic=topic,
            payload=payload or {},
            timestamp=self._clock.now().isoformat(),
            run_id=run_id,
        )
        self._deliver_local(event)
        return event

    def _deliver_local(self, event: Event) -> None:
        """Fan an event out to this process's subscribers.

        Separate from :meth:`publish` so a distributed bus can inject events
        that arrived from another node without re-broadcasting them.
        """
        self._published += 1
        for sub in list(self._subscriptions):
            if sub.wants(event.topic):
                sub.offer(event)

    async def drain(self) -> None:
        """Yield to the loop so subscribers can observe what was just published."""
        await asyncio.sleep(0)
