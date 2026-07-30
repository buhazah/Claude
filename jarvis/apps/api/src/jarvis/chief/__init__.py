"""The Chief of Staff: proactive intelligence and the morning briefing.

Everything here follows one rule, stated in ADR 0014: **arithmetic decides
what matters; a model only ever phrases it.**

Handing everything Jarvis knows to a model and asking "what should they do
today" is one call and reads beautifully. It is also unauditable,
non-deterministic, unavailable offline, and — worst — unfalsifiable: when it
tells you the wrong thing there is nothing to correct, because there is no
rule. So detection is nine small deterministic signals, ranking is
`impact × urgency × confidence`, and every recommendation carries the evidence
that produced it.

| module | what it owns |
|---|---|
| `models` | what a recommendation is, and the three axes it ranks on |
| `situation` | one snapshot of everything the detectors read |
| `signals` | the detectors themselves — no model, ever |
| `engine` | sweep, rank, and stop talking |
| `briefing` | the morning read, prose optional |
"""

from __future__ import annotations

from jarvis.chief.briefing import Briefing, BriefingComposer
from jarvis.chief.engine import RecommendationEngine, Sweep
from jarvis.chief.models import Impact, Recommendation, Signal, Urgency
from jarvis.chief.situation import Situation, gather

__all__ = [
    "Briefing",
    "BriefingComposer",
    "Impact",
    "Recommendation",
    "RecommendationEngine",
    "Signal",
    "Situation",
    "Sweep",
    "Urgency",
    "gather",
]
