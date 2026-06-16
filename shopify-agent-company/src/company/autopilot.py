"""Autopilot: run the company's scheduled tasks on a loop, unattended.

Each entry in config/store.yaml `schedule` is {name, every_minutes, task}.
Autopilot sends each task to the master agent when due. Whether any resulting
action executes or merely gets proposed is governed by per-agent `autonomy`
in the same config — autopilot does not bypass those guardrails.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .master import run_task
from .settings import StoreConfig


@dataclass
class Job:
    name: str
    every_minutes: int
    task: str
    next_run: float = 0.0  # epoch seconds; 0 => due immediately on start


def _load_jobs(cfg: StoreConfig) -> list[Job]:
    jobs = []
    for entry in cfg.schedule:
        jobs.append(
            Job(
                name=entry["name"],
                every_minutes=int(entry["every_minutes"]),
                task=entry["task"],
            )
        )
    return jobs


async def run_autopilot(cfg: StoreConfig, tick_seconds: int = 30) -> None:
    jobs = _load_jobs(cfg)
    if not jobs:
        print("No schedule defined in config — nothing for autopilot to run.")
        return

    print(f"🛫 Autopilot started with {len(jobs)} scheduled job(s):")
    for j in jobs:
        print(f"   • {j.name} — every {j.every_minutes} min")
    print("   Ctrl-C to stop.\n")

    while True:
        now = time.time()
        for job in jobs:
            if now >= job.next_run:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{ts}] ▶ running '{job.name}'")
                try:
                    await run_task(cfg, job.task)
                except Exception as exc:  # keep the loop alive on a single failure
                    print(f"[{job.name}] error: {exc}")
                job.next_run = time.time() + job.every_minutes * 60
        await asyncio.sleep(tick_seconds)
