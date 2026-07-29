"""Triggers: what starts a workflow without being asked.

Three sources, one dispatcher:

* **manual** — a person or the API.
* **schedule** — every N seconds, checked by a background tick.
* **event** — a bus topic pattern, so "when a memory is written" or "when an
  agent fails" can start work. This is why the event bus exists: automation
  subscribes to the same firehose the UI does, with no new plumbing.

The scheduler also does one thing that is easy to miss and important: on start
it **resumes workflows that were suspended when the process died**. Durable
suspension is only durable if something picks the runs back up.
"""

from __future__ import annotations

import asyncio
import contextlib

import structlog

from jarvis.kernel.bus import EventBus, Subscription
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.workflows.engine import WorkflowEngine
from jarvis.workflows.models import Trigger, TriggerKind
from jarvis.workflows.store import WorkflowStore

log = structlog.get_logger(__name__)

TICK_SECONDS = 1.0
# Shortest gap between two firings of the same event trigger.
EVENT_COOLDOWN_SECONDS = 5.0


class Scheduler:
    """Fires schedule and event triggers, and revives suspended runs."""

    def __init__(
        self,
        *,
        store: WorkflowStore,
        engine: WorkflowEngine,
        bus: EventBus,
        clock: Clock = SYSTEM_CLOCK,
        tick_seconds: float = TICK_SECONDS,
    ) -> None:
        self._store = store
        self._engine = engine
        self._bus = bus
        self._clock = clock
        self._tick = tick_seconds
        self._task: asyncio.Task[None] | None = None
        self._subscription: Subscription | None = None
        self._event_task: asyncio.Task[None] | None = None
        self.fired = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        await self.recover()
        self._task = asyncio.create_task(self._loop())
        self._subscription = self._bus.subscribe("**")
        self._event_task = asyncio.create_task(self._watch_events())

    async def recover(self) -> int:
        """Resume runs left suspended by a previous process.

        Without this, "durable suspension" means the row survives and nothing
        ever looks at it again — which is indistinguishable from losing it.
        """
        revived = 0
        for run in await self._store.suspended_runs():
            if not run.awaiting_approval_id:
                continue
            was = run.state
            with contextlib.suppress(Exception):
                resumed = await self._engine.resume(run.id)
                if resumed.state != was:
                    revived += 1
        if revived:
            log.info("workflow_runs_revived", count=revived)
        return revived

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._tick)
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("scheduler_tick_failed", error=str(exc))

    async def tick(self) -> int:
        """Fire every schedule trigger that is due. Returns how many fired."""
        now = self._clock.now()
        fired = 0
        for trigger in await self._store.triggers():
            if not trigger.enabled or trigger.kind is not TriggerKind.SCHEDULE:
                continue
            due = (
                trigger.last_fired_at is None
                or (now - trigger.last_fired_at).total_seconds() >= trigger.interval_seconds
            )
            if not due:
                continue
            if await self._fire(trigger, {"fired_at": now.isoformat()}):
                fired += 1
        return fired

    async def _watch_events(self) -> None:
        """Start workflows whose trigger topic matches a published event."""
        assert self._subscription is not None
        try:
            async for event in self._subscription.events():
                # A decided approval is what un-sticks a suspended workflow.
                # Handling it here keeps the approval broker unaware that
                # workflows exist.
                if event.topic in ("approval.approved", "approval.denied"):
                    run_id = str(event.payload.get("run_id") or "")
                    if run_id.startswith("wrn_"):
                        with contextlib.suppress(Exception):
                            await self._engine.resume(run_id)
                    continue

                # Workflow events would let a workflow trigger itself; so would
                # any event a workflow's own agents publish. The first is
                # excluded by topic, the second by causality.
                if event.topic.startswith("workflow.") or event.caused_by:
                    continue
                for trigger in await self._store.triggers():
                    if (
                        trigger.enabled
                        and trigger.kind is TriggerKind.EVENT
                        and trigger.topic
                        and _matches(trigger.topic, event.topic)
                        and self._off_cooldown(trigger)
                    ):
                        await self._fire(trigger, {"topic": event.topic, **event.payload})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("event_trigger_watcher_stopped", error=str(exc))

    def _off_cooldown(self, trigger: Trigger) -> bool:
        """Defence in depth against event storms.

        Causality tracking stops a workflow re-triggering itself; this stops a
        *chattier* source — a busy inbox, a noisy integration — from starting a
        run per event.
        """
        if trigger.last_fired_at is None:
            return True
        elapsed = (self._clock.now() - trigger.last_fired_at).total_seconds()
        return elapsed >= min(trigger.interval_seconds, EVENT_COOLDOWN_SECONDS)

    async def _fire(self, trigger: Trigger, inputs: dict[str, object]) -> bool:
        workflow = await self._store.get(trigger.workflow_id)
        if workflow is None or not workflow.enabled:
            return False
        trigger.last_fired_at = self._clock.now()
        await self._store.save_trigger(trigger)
        try:
            await self._engine.start(workflow, inputs=inputs, trigger=trigger.kind.value)
        except Exception as exc:
            log.warning("trigger_fire_failed", trigger=trigger.id, error=str(exc))
            return False
        self.fired += 1
        return True

    async def stop(self) -> None:
        for task in (self._task, self._event_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._task = self._event_task = None
        if self._subscription:
            self._subscription.close()
            self._subscription = None


def _matches(pattern: str, topic: str) -> bool:
    from jarvis.kernel.bus import topic_matches

    return topic_matches(pattern, topic)
