"""Cost governance.

A budget that reports what was spent is a dashboard. A budget is a *control*
only if it is consulted before the money is spent, and only if exceeding it
changes what happens.

Two ceilings, because one is always wrong:

* **Soft.** Crossing it does not stop the work, it puts a human on it — the
  same approval gate that guards a dangerous tool. This is the ceiling that
  should fire in normal operation: it converts "you spent £180 this month"
  from something discovered later into a decision made at the time.
* **Hard.** Crossing it refuses. No approval path, because the point of a hard
  ceiling is to survive the case where the thing burning money is also the
  thing generating approval requests faster than anyone can read them.

The check happens **before** the call, against an estimate, because after is
too late by exactly the amount that matters. The estimate is deliberately
conservative — it assumes the model emits its full `max_output_tokens` — since
a budget that under-estimates is a budget that is exceeded.

Periods roll on wall-clock boundaries rather than sliding windows: "this month"
is what a person means and what an invoice says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

import structlog

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock

log = structlog.get_logger(__name__)


class Period(StrEnum):
    DAY = "day"
    MONTH = "month"
    TOTAL = "total"


class BudgetExceededError(RuntimeError):
    """The hard ceiling. Not a failure of the work — a refusal to pay for it."""

    def __init__(self, message: str, *, spent: float, limit: float) -> None:
        super().__init__(message)
        self.spent = spent
        self.limit = limit


def period_key(period: Period, at: datetime) -> str:
    """Which bucket a moment falls in. Wall clock, not a sliding window."""
    match period:
        case Period.DAY:
            return at.date().isoformat()
        case Period.MONTH:
            return f"{at.year:04d}-{at.month:02d}"
        case Period.TOTAL:
            return "total"


@dataclass
class Ledger:
    """What has been spent, by period."""

    clock: Clock = SYSTEM_CLOCK
    _spend: dict[tuple[Period, str], float] = field(default_factory=dict)
    _calls: dict[tuple[Period, str], int] = field(default_factory=dict)

    def record(self, cost_usd: float) -> None:
        if cost_usd < 0:
            return
        now = self.clock.now()
        for period in Period:
            key = (period, period_key(period, now))
            self._spend[key] = self._spend.get(key, 0.0) + cost_usd
            self._calls[key] = self._calls.get(key, 0) + 1

    def spent(self, period: Period, *, at: datetime | None = None) -> float:
        return self._spend.get((period, period_key(period, at or self.clock.now())), 0.0)

    def calls(self, period: Period, *, at: datetime | None = None) -> int:
        return self._calls.get((period, period_key(period, at or self.clock.now())), 0)

    def snapshot(self) -> dict[str, Any]:
        now = self.clock.now()
        return {
            period.value: {
                "spent_usd": round(self.spent(period, at=now), 6),
                "calls": self.calls(period, at=now),
            }
            for period in Period
        }


@dataclass(frozen=True, slots=True)
class Budget:
    """One ceiling over one period."""

    period: Period
    soft_usd: float = 0.0
    hard_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.hard_usd and self.soft_usd and self.soft_usd > self.hard_usd:
            # Otherwise the soft ceiling is unreachable and the first thing the
            # user ever sees is a hard refusal.
            raise ValueError(
                f"soft ceiling ({self.soft_usd}) is above the hard one ({self.hard_usd})"
            )

    @property
    def enforced(self) -> bool:
        return bool(self.soft_usd or self.hard_usd)


class Verdict(StrEnum):
    ALLOW = "allow"
    APPROVE = "approve"
    REFUSE = "refuse"


@dataclass(slots=True)
class Assessment:
    verdict: Verdict
    reason: str = ""
    period: Period = Period.TOTAL
    spent: float = 0.0
    projected: float = 0.0
    limit: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "period": self.period.value,
            "spent_usd": round(self.spent, 6),
            "projected_usd": round(self.projected, 6),
            "limit_usd": self.limit,
        }


@dataclass
class CostGovernor:
    """Grades a call against the ceilings *before* it is made."""

    ledger: Ledger = field(default_factory=Ledger)
    budgets: tuple[Budget, ...] = ()

    @property
    def enforced(self) -> bool:
        return any(b.enforced for b in self.budgets)

    def assess(self, estimate: float) -> Assessment:
        """What should happen to a call expected to cost ``estimate``.

        The strictest verdict across every budget wins, and a hard refusal is
        reported in preference to a soft one — a user told "approve this" when
        the answer is actually "no" will approve it and then be confused.
        """
        worst = Assessment(Verdict.ALLOW)
        for budget in self.budgets:
            if not budget.enforced:
                continue
            spent = self.ledger.spent(budget.period)
            projected = spent + max(estimate, 0.0)

            if budget.hard_usd and projected > budget.hard_usd:
                return Assessment(
                    Verdict.REFUSE,
                    f"this call would take {budget.period.value} spend to "
                    f"${projected:.4f}, past the ${budget.hard_usd:.2f} hard ceiling",
                    budget.period,
                    spent,
                    projected,
                    budget.hard_usd,
                )
            if budget.soft_usd and projected > budget.soft_usd and worst.verdict is Verdict.ALLOW:
                worst = Assessment(
                    Verdict.APPROVE,
                    f"{budget.period.value} spend would reach ${projected:.4f}, "
                    f"past the ${budget.soft_usd:.2f} ceiling you set",
                    budget.period,
                    spent,
                    projected,
                    budget.soft_usd,
                )
        return worst

    def record(self, cost_usd: float) -> None:
        self.ledger.record(cost_usd)

    def snapshot(self) -> dict[str, Any]:
        return {
            "enforced": self.enforced,
            "spend": self.ledger.snapshot(),
            "budgets": [
                {
                    "period": b.period.value,
                    "soft_usd": b.soft_usd,
                    "hard_usd": b.hard_usd,
                    "spent_usd": round(self.ledger.spent(b.period), 6),
                    "remaining_usd": (
                        round(max(b.hard_usd - self.ledger.spent(b.period), 0.0), 6)
                        if b.hard_usd
                        else None
                    ),
                }
                for b in self.budgets
                if b.enforced
            ],
        }


def budgets_from_settings(
    *, daily_soft: float, daily_hard: float, monthly_soft: float, monthly_hard: float
) -> tuple[Budget, ...]:
    return (
        Budget(Period.DAY, daily_soft, daily_hard),
        Budget(Period.MONTH, monthly_soft, monthly_hard),
    )


__all__ = [
    "Assessment",
    "Budget",
    "BudgetExceededError",
    "CostGovernor",
    "Ledger",
    "Period",
    "Verdict",
    "budgets_from_settings",
    "date",
    "period_key",
]
