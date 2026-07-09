"""Automation engine: a persistent cron-style workflow scheduler.

Workflows carry a 5-field cron expression and a prompt. A single async
loop wakes every 30s, finds due workflows, and runs each through the
orchestrator, recording a WorkflowRun. Cron parsing is implemented here
(standard 5-field syntax with ranges, lists, and steps) so there is no
external dependency.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from ..db import SessionLocal, Workflow, WorkflowRun, utcnow
from ..agents.orchestrator import orchestrator

log = logging.getLogger("jarvis.automation")

TICK_SECONDS = 30


# --------------------------------------------------------------- cron parser

def _parse_field(field: str, low: int, high: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/")
            step = int(step_s)
        if part in ("*", ""):
            start, end = low, high
        elif "-" in part:
            start_s, end_s = part.split("-")
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(part)
        values.update(range(start, end + 1, step))
    return {v for v in values if low <= v <= high}


def cron_matches(expr: str, when: datetime) -> bool:
    """True if `when` (minute resolution) satisfies the 5-field cron expr."""
    fields = expr.split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    return (
        when.minute in _parse_field(minute, 0, 59)
        and when.hour in _parse_field(hour, 0, 23)
        and when.day in _parse_field(dom, 1, 31)
        and when.month in _parse_field(month, 1, 12)
        # cron: 0 and 7 both mean Sunday; Python weekday() Mon=0..Sun=6
        and ((when.weekday() + 1) % 7) in _parse_field(dow, 0, 7 - 1) | (
            {0} if 7 in _parse_field(dow, 0, 7) else set()
        )
    )


def next_run_after(expr: str, after: datetime) -> datetime | None:
    """Find the next minute matching the cron expr within ~366 days."""
    if expr == "manual" or len(expr.split()) != 5:
        return None
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        if cron_matches(expr, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    return None


# ------------------------------------------------------------------ engine

class AutomationEngine:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def run_workflow(self, workflow_id: str) -> str:
        """Execute one workflow now and record the run. Returns output."""
        async with SessionLocal() as session:
            wf = await session.get(Workflow, workflow_id)
            if wf is None:
                return "workflow not found"
            run = WorkflowRun(workflow_id=wf.id, status="running")
            session.add(run)
            await session.commit()

            output_parts: list[str] = []
            error = ""
            try:
                async for event in orchestrator.handle(
                    session, wf.user_id, wf.prompt,
                    forced_agent=wf.agent if wf.agent in _known_agents() else None,
                ):
                    if event.type == "final":
                        output_parts.append(event.data.get("text", ""))
                    elif event.type == "error":
                        error = event.data.get("message", "")
            except Exception as exc:  # workflow failures must not crash the loop
                error = f"{type(exc).__name__}: {exc}"
                log.exception("workflow %s failed", wf.id)

            run.status = "failed" if error else "success"
            run.output = "\n".join(p for p in output_parts if p)[:20000]
            run.error = error
            run.finished_at = utcnow()
            wf.last_run_at = utcnow()
            wf.next_run_at = next_run_after(wf.schedule, utcnow())
            await session.commit()
            return run.output or error

    async def _tick(self) -> None:
        now = utcnow().replace(second=0, microsecond=0)
        async with SessionLocal() as session:
            workflows = (
                (await session.execute(select(Workflow).where(Workflow.enabled.is_(True))))
                .scalars()
                .all()
            )
            due_ids = [
                wf.id for wf in workflows
                if wf.schedule != "manual"
                and cron_matches(wf.schedule, now)
                and (wf.last_run_at is None or wf.last_run_at.replace(second=0, microsecond=0) < now)
            ]
        for wf_id in due_ids:
            log.info("running scheduled workflow %s", wf_id)
            await self.run_workflow(wf_id)

    async def _loop(self) -> None:
        self._running = True
        log.info("automation engine started (tick=%ss)", TICK_SECONDS)
        while self._running:
            try:
                await self._tick()
            except Exception as exc:
                log.exception("automation tick error: %s", exc)
            await asyncio.sleep(TICK_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


def _known_agents() -> set[str]:
    from ..agents.definitions import AGENTS
    return set(AGENTS)


engine = AutomationEngine()
