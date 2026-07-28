"""Redis-backed event bus.

The in-process bus is correct for a single worker. Once Jarvis runs more than
one — an API process plus background workers — an event published by a worker
must still reach the UI stream held open by the API process. Redis pub/sub
gives that with no broker to operate.

``RedisEventBus`` extends ``EventBus`` rather than replacing it, so:

* local subscribers are still served synchronously and in-process, keeping
  streaming latency identical;
* remote fan-out is an *addition*, published to Redis and mirrored back in by a
  reader task;
* if Redis goes down, local delivery keeps working and the process degrades to
  single-node behaviour instead of failing.

Delivery is at-most-once, which is the right trade for observability events. A
run's durable record is the run table, not the event stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import structlog

from jarvis.kernel.bus import Event, EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock

log = structlog.get_logger(__name__)

CHANNEL = "jarvis:events"


class RedisEventBus(EventBus):
    def __init__(
        self,
        url: str,
        *,
        clock: Clock = SYSTEM_CLOCK,
        node_id: str | None = None,
    ) -> None:
        super().__init__(clock=clock)
        self._url = url
        self._node_id = node_id or f"node-{id(self):x}"
        self._redis: Any = None
        self._reader: asyncio.Task[None] | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        """Connect and begin mirroring remote events. Safe to call if Redis is down."""
        try:
            from redis.asyncio import Redis
        except ImportError:  # pragma: no cover - the extra is optional by design
            log.warning("redis_extra_missing", hint="pip install 'jarvis-api[redis]'")
            return

        try:
            self._redis = Redis.from_url(self._url, decode_responses=True)
            await self._redis.ping()
            self._connected = True
            self._reader = asyncio.create_task(self._consume())
            log.info("redis_bus_connected", url=self._url, node=self._node_id)
        except Exception as exc:
            log.warning("redis_bus_unavailable", error=str(exc))
            self._redis = None
            self._connected = False

    async def _consume(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                except (ValueError, KeyError):
                    continue
                # Our own publishes were already delivered locally; re-delivering
                # them would double every event on the originating node.
                if payload.get("node") == self._node_id:
                    continue
                self._deliver_local(
                    Event(
                        topic=payload["topic"],
                        payload=payload.get("payload", {}),
                        id=payload.get("id", ""),
                        timestamp=payload.get("timestamp", ""),
                        run_id=payload.get("run_id"),
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("redis_bus_reader_stopped", error=str(exc))
            self._connected = False
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(CHANNEL)
                await pubsub.aclose()

    def publish(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
        *,
        run_id: str | None = None,
    ) -> Event:
        event = super().publish(topic, payload, run_id=run_id)
        if self._redis is not None and self._connected:
            # Fire-and-forget: publishing must never block the caller, and an
            # observability event is not worth failing a request over.
            task = asyncio.create_task(self._fanout(event))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        return event

    async def _fanout(self, event: Event) -> None:
        try:
            await self._redis.publish(
                CHANNEL, json.dumps({**event.to_dict(), "node": self._node_id})
            )
        except Exception as exc:
            log.warning("redis_publish_failed", error=str(exc))
            self._connected = False

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader
            self._reader = None
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()
            self._redis = None
        self._connected = False
