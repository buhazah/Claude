"""The recommendation engine: run every detector, rank, and stop talking.

Three jobs, and the third is the one that decides whether this is useful.

**Sweep.** Gather the situation once, run every detector over it.

**Rank.** `impact × urgency × confidence`, descending. Arithmetic, so it can be
audited and corrected.

**Shut up.** The failure mode of every proactive assistant is noticing
everything and prioritising nothing, and the user muting it inside a week. So a
sweep returns a *short* list, no more than one recommendation per signal type
unless the top ones genuinely outrank everything else, and anything dismissed
stays dismissed.

Dismissal is why recommendation ids are stable across sweeps. Without that,
"not now" would be meaningless — the next sweep would mint a fresh id and the
same thing would come straight back wearing a new name.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import structlog

from jarvis.chief.models import Recommendation, Signal, Urgency
from jarvis.chief.signals import DETECTORS, Detector
from jarvis.chief.situation import Situation, gather
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock

log = structlog.get_logger(__name__)

# How many recommendations one sweep may surface. Ten is already more than
# anybody acts on in a day; the eleventh is what makes the first ten ignorable.
MAX_RECOMMENDATIONS = 10
# Per signal, unless a second one outranks whatever else is competing. One
# cold project is a nudge; six is a wall of text that hides the approval
# blocking a run.
MAX_PER_SIGNAL = 2
# A dismissal lasts this long, then the thing is allowed to ask again — because
# a genuinely important recommendation that is ignored forever is a bug, and
# "not now" is not the same answer as "never".
DISMISSAL_TTL = timedelta(days=7)


@dataclass(slots=True)
class Sweep:
    """One pass. Everything the report and the briefing need."""

    at: datetime
    recommendations: list[Recommendation] = field(default_factory=list)
    considered: int = 0
    suppressed: int = 0
    dismissed: int = 0
    unavailable: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> list[Recommendation]:
        return [r for r in self.recommendations if r.urgency is Urgency.BLOCKING]

    def by_signal(self) -> dict[str, int]:
        return dict(Counter(r.signal.value for r in self.recommendations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at.isoformat(),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "considered": self.considered,
            "suppressed": self.suppressed,
            "dismissed": self.dismissed,
            # Named rather than swallowed: a list silently missing a third of
            # its inputs is worse than one that says what it could not see.
            "unavailable": list(self.unavailable),
            "by_signal": self.by_signal(),
        }


class RecommendationEngine:
    """Proactive intelligence, without a model in the loop."""

    def __init__(
        self,
        *,
        detectors: tuple[Detector, ...] = DETECTORS,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
        limit: int = MAX_RECOMMENDATIONS,
    ) -> None:
        self._detectors = detectors
        self._bus = bus
        self._clock = clock
        self._limit = limit
        self._dismissed: dict[str, datetime] = {}

    async def sweep(self, jarvis: Any) -> Sweep:
        situation = await gather(jarvis)
        return self.rank(situation)

    def rank(self, situation: Situation) -> Sweep:
        """Run the detectors over a snapshot. Pure, so it is testable alone."""
        found: list[Recommendation] = []
        for detector in self._detectors:
            try:
                found.extend(detector(situation))
            except Exception as exc:
                # One broken detector must not silence the other eight.
                log.warning("detector_failed", detector=detector.__name__, error=str(exc))
                situation.unavailable.append(detector.__name__)

        sweep = Sweep(at=situation.now, considered=len(found), unavailable=situation.unavailable)

        live = [r for r in found if not self._is_dismissed(r.id, situation.now)]
        sweep.dismissed = len(found) - len(live)

        live.sort(key=lambda r: (-r.score, r.signal.value, r.id))
        kept: list[Recommendation] = []
        per_signal: Counter[Signal] = Counter()
        for recommendation in live:
            if per_signal[recommendation.signal] >= MAX_PER_SIGNAL:
                continue
            if len(kept) >= self._limit:
                break
            per_signal[recommendation.signal] += 1
            kept.append(recommendation)

        sweep.recommendations = kept
        sweep.suppressed = len(live) - len(kept)

        if self._bus:
            self._bus.publish(
                "chief.swept",
                {
                    "surfaced": len(kept),
                    "considered": sweep.considered,
                    "blocking": len(sweep.blocking),
                },
            )
        return sweep

    # ── Dismissal ─────────────────────────────────────────────────────────────

    def dismiss(self, recommendation_id: str) -> None:
        """ "Not now." Held for a week, then allowed to ask again.

        Not forever, deliberately. A recommendation important enough to keep
        detecting is important enough to raise again eventually, and a
        permanent dismissal is how a system quietly stops mentioning the thing
        that later goes wrong.
        """
        self._dismissed[recommendation_id] = self._clock.now()
        if self._bus:
            self._bus.publish("chief.dismissed", {"id": recommendation_id})

    def restore(self, dismissals: dict[str, datetime]) -> None:
        """Reload dismissals after a restart, so "not now" survives one."""
        self._dismissed.update(dismissals)

    @property
    def dismissals(self) -> dict[str, datetime]:
        return dict(self._dismissed)

    def _is_dismissed(self, recommendation_id: str, now: datetime) -> bool:
        when = self._dismissed.get(recommendation_id)
        if when is None:
            return False
        if now - when > DISMISSAL_TTL:
            del self._dismissed[recommendation_id]
            return False
        return True
