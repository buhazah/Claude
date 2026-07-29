"""The corpus.

Assembled here so the runner never has to know how it is organised, and so
anything can ask "how much of this is free" without importing five modules.

Organised by what a case tests, not by which agent it hits, because the
question the corpus answers is "did the change help", and that question is
asked per dimension: routing, planning, tool selection, memory, research,
execution, workflows, documents, coding, business.
"""

from __future__ import annotations

from collections import Counter

from eval.corpus.agents import AGENT_CASES
from eval.corpus.documents import DOCUMENT_CASES
from eval.corpus.everyday import EVERYDAY_CASES
from eval.corpus.grounding import GROUNDING_CASES
from eval.corpus.probes import AGENT_PROBES, MODE_PROBES, AgentProbe, ModeProbe
from eval.corpus.routing import ROUTING_CASES
from eval.scoring import Case, Suite, Tier

CASES: tuple[Case, ...] = (
    *ROUTING_CASES,
    *EVERYDAY_CASES,
    *AGENT_CASES,
    *GROUNDING_CASES,
    *DOCUMENT_CASES,
)

_ids = Counter(case.id for case in CASES)
if duplicates := [case_id for case_id, n in _ids.items() if n > 1]:
    raise ValueError(f"duplicate case ids in the corpus: {duplicates}")


def by_tier() -> dict[str, int]:
    counts = Counter(case.tier for case in CASES)
    return {tier: counts.get(tier, 0) for tier in Tier.ORDER}


def by_suite() -> dict[str, int]:
    counts = Counter(case.suite for case in CASES)
    return {suite: counts.get(suite, 0) for suite in Suite.ALL}


def select(
    *,
    suites: tuple[str, ...] = (),
    max_tier: str = Tier.DOCUMENT,
    limit_per_suite: int = 0,
) -> tuple[Case, ...]:
    """Pick a subset to run.

    Sampling is by stride rather than by prefix, so a capped run still spans
    every section of a suite. Taking the first N would mean the everyday cases
    never ran and the traps ran every time — the opposite of what a sample is
    for.
    """
    ceiling = Tier.ORDER.index(max_tier)
    chosen = [
        case
        for case in CASES
        if (not suites or case.suite in suites) and Tier.ORDER.index(case.tier) <= ceiling
    ]
    if not limit_per_suite:
        return tuple(chosen)

    grouped: dict[str, list[Case]] = {}
    for case in chosen:
        grouped.setdefault(case.suite, []).append(case)

    sampled: list[Case] = []
    for group in grouped.values():
        if len(group) <= limit_per_suite:
            sampled.extend(group)
            continue
        stride = len(group) / limit_per_suite
        sampled.extend(group[int(i * stride)] for i in range(limit_per_suite))
    return tuple(sorted(sampled, key=lambda c: c.id))


__all__ = [
    "AGENT_PROBES",
    "CASES",
    "MODE_PROBES",
    "AgentProbe",
    "ModeProbe",
    "by_suite",
    "by_tier",
    "select",
]
