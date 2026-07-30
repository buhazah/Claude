"""What a recommendation is, and why it ranks where it does.

The load-bearing decision in this whole subsystem: **a recommendation's rank is
arithmetic, not a model's opinion.**

It would be easier to hand a model everything Jarvis knows and ask "what should
they do today". It would also be unauditable, non-deterministic, unavailable
offline, and — worst — unfalsifiable. When it told you the wrong thing there
would be nothing to fix, because there would be no rule to correct.

So detection is a set of small, deterministic signals over state Jarvis already
has, and ranking is `impact × urgency × confidence`. Every recommendation
carries the evidence that produced it. If one is wrong, either the evidence is
wrong (fix the data) or the weighting is wrong (fix the number) — and both are
things a person can actually do.

A model is used later, in the briefing (M11.6), and only to *phrase* what the
arithmetic already decided.

The three axes are deliberately coarse. Five levels each, defined by what they
mean rather than by a scale:

**Impact** — how much worse things get if this is ignored. A blocked launch is
not the same size of problem as an unlinked note, and a ranking that cannot
tell them apart is a to-do list.

**Urgency** — how much the answer changes by waiting. A deadline on Friday is
urgent on Thursday and irrelevant on Saturday. A cold project is important and
almost never urgent, which is exactly why it stays cold.

**Confidence** — how sure the *detector* is that this is real. A pending
approval is certain; "this project looks stalled because nobody edited a file"
is a guess, and the ranking says so rather than pretending otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum


class Impact(IntEnum):
    """How much worse things get if this is ignored."""

    TRIVIAL = 1  # tidiness
    MINOR = 2  # a small loss of quality or time
    MODERATE = 3  # a real cost, absorbable
    MAJOR = 4  # a commitment missed, money lost, a project stalled
    CRITICAL = 5  # money leaving, data at risk, a promise broken


class Urgency(IntEnum):
    """How much the answer changes by waiting."""

    WHENEVER = 1  # no deadline; waiting costs nothing
    SOON = 2  # this month
    THIS_WEEK = 3
    TODAY = 4
    BLOCKING = 5  # something is stopped until this moves


class Signal(StrEnum):
    """Which detector produced this. Named so a wrong one can be found."""

    APPROVAL = "approval"  # a human decision is holding something up
    FAILED_RUN = "failed_run"  # work that ended badly and was never retried
    STALLED_WORKFLOW = "stalled_workflow"
    COLD_PROJECT = "cold_project"  # a page nobody has touched
    OPEN_GOAL = "open_goal"  # stated, then never mentioned again
    DEADLINE = "deadline"  # a date Jarvis has been told about
    BUDGET = "budget"  # spend approaching a ceiling
    REPEATED_MISTAKE = "repeated_mistake"
    LOOSE_KNOWLEDGE = "loose_knowledge"  # orphans and unlinked mentions
    UNANSWERED = "unanswered"  # a question asked and not returned to


@dataclass(frozen=True, slots=True)
class Recommendation:
    """One thing worth doing, and the evidence that says so."""

    id: str
    signal: Signal
    # Imperative and specific. "Decide on the Northbound pricing change", not
    # "Consider reviewing pricing" — a recommendation nobody can act on
    # without first interpreting it is a reminder, not a recommendation.
    headline: str
    impact: Impact
    urgency: Urgency
    # What the detector saw. The reason a wrong recommendation is fixable.
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0
    # A request Jarvis could run to make progress, and who should get it.
    action: str = ""
    agent: str = ""
    # Notes, runs or approvals this points at.
    refs: list[str] = field(default_factory=list)
    at: datetime | None = None

    @property
    def score(self) -> float:
        """Impact × urgency × confidence, out of 25.

        Multiplicative rather than additive, so nothing important-but-distant
        outranks something blocking, and a low-confidence guess cannot climb by
        claiming to be critical.
        """
        return round(float(self.impact) * float(self.urgency) * self.confidence, 3)

    @property
    def why(self) -> str:
        return "; ".join(self.evidence)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "signal": self.signal.value,
            "headline": self.headline,
            "impact": int(self.impact),
            "impact_name": self.impact.name.lower(),
            "urgency": int(self.urgency),
            "urgency_name": self.urgency.name.lower(),
            "confidence": round(self.confidence, 3),
            "score": self.score,
            "evidence": list(self.evidence),
            "action": self.action,
            "agent": self.agent,
            "refs": list(self.refs),
            "at": self.at.isoformat() if self.at else None,
        }
