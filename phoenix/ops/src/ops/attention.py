"""Which clients need attention, decided by rules rather than by feel.

Deterministic on purpose. A model asked "who should I call today" gives a
different answer on different days, and the whole point of this list is that it
is the same list until something actually changes.

At ten clients everything is loaded into memory and compared. That is not an
oversight — it is the correct amount of engineering for the size, and it makes
every rule below a pure function that a test can pin down exactly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ops.models import Client, Interaction, Task

# A live client we have not spoken to in this long has started to drift.
SILENCE_DAYS = 8
# An audit is two weeks. Past this with no review booked, it is slipping.
AUDIT_STALE_DAYS = 10
# Monthly review means monthly.
REVIEW_DUE_DAYS = 35

URGENT, SOON, WATCH = 3, 2, 1


@dataclass(slots=True)
class Attention:
    client_id: int
    client_name: str
    reason: str
    severity: int
    days: int = 0

    @property
    def label(self) -> str:
        return {URGENT: "urgent", SOON: "soon", WATCH: "watch"}[self.severity]


def _days_since(when: date | None, today: date) -> int | None:
    return None if when is None else (today - when).days


def review(
    clients: Sequence[Client],
    interactions: Sequence[Interaction],
    tasks: Sequence[Task],
    today: date,
) -> list[Attention]:
    """Everything that wants a human today, worst first."""
    last_seen: dict[int, date] = {}
    last_kind: dict[tuple[int, str], date] = {}
    for i in interactions:
        when = i.occurred_at.date()
        if when > last_seen.get(i.client_id, date.min):
            last_seen[i.client_id] = when
        key = (i.client_id, i.kind)
        if when > last_kind.get(key, date.min):
            last_kind[key] = when

    open_by_client: dict[int | None, list[Task]] = {}
    for t in tasks:
        if not t.is_done:
            open_by_client.setdefault(t.client_id, []).append(t)

    out: list[Attention] = []

    def add(client: Client, reason: str, severity: int, days: int = 0) -> None:
        out.append(Attention(client.id, client.name, reason, severity, days))

    for client in clients:
        # An overdue next action beats everything: we told ourselves we would do
        # this, on this date, and did not.
        if client.next_action and client.next_action_due:
            overdue = (today - client.next_action_due).days
            if overdue >= 0:
                add(
                    client,
                    f"{client.next_action} — due {'today' if overdue == 0 else f'{overdue}d ago'}",
                    URGENT if overdue > 0 else SOON,
                    overdue,
                )

        # A conversation with no agreed next step is a conversation that quietly
        # ends. This is the most common way a warm prospect is lost.
        if client.status == "conversation" and not client.next_action:
            add(client, "spoke to them, no next action set", URGENT)

        if client.status == "active":
            silent = _days_since(last_seen.get(client.id), today)
            if silent is None:
                add(client, "paying, never contacted", URGENT)
            elif silent >= SILENCE_DAYS:
                add(client, f"no contact in {silent}d", SOON, silent)

            since_review = _days_since(last_kind.get((client.id, "monthly_review")), today)
            if since_review is None:
                started = _days_since(client.active_since, today)
                if started is not None and started >= REVIEW_DUE_DAYS:
                    add(client, f"no monthly review, active {started}d", SOON, started)
            elif since_review >= REVIEW_DUE_DAYS:
                add(client, f"monthly review {since_review}d ago", SOON, since_review)

        if client.status == "audit":
            running = _days_since(client.audit_started_on, today)
            reviewed = last_kind.get((client.id, "audit_review"))
            if running is not None and running >= AUDIT_STALE_DAYS and reviewed is None:
                add(client, f"audit running {running}d, not yet presented", URGENT, running)
            # The day-five gate. Recorded, so it cannot be quietly skipped.
            if running is not None and running >= 5 and client.reconciliation_confidence is None:
                add(client, "past day five, reconciliation not recorded", URGENT, running)

        if client.status == "churned" and not client.churn_reason:
            add(client, "churned, no exit interview", URGENT)

        for task in open_by_client.get(client.id, []):
            if task.due_on and task.due_on <= today:
                late = (today - task.due_on).days
                add(client, f"task overdue: {task.title}", SOON if late < 3 else URGENT, late)

    out.sort(key=lambda a: (-a.severity, -a.days, a.client_name))
    return out


def unassigned_overdue(tasks: Sequence[Task], today: date) -> list[Task]:
    """Open, overdue, and not attached to any client."""
    return sorted(
        (
            t
            for t in tasks
            if not t.is_done and t.client_id is None and t.due_on and t.due_on <= today
        ),
        key=lambda t: t.due_on or today,
    )


def funnel(clients: Sequence[Client]) -> dict[str, int]:
    """Counts by status, so the pipeline is one glance rather than a query."""
    counts: dict[str, int] = {}
    for client in clients:
        counts[client.status] = counts.get(client.status, 0) + 1
    return counts


def effort_by_category(tasks: Sequence[Task]) -> dict[str, int]:
    """Completed minutes by A/B/C. Only B is ever a candidate for automation."""
    totals = {"A": 0, "B": 0, "C": 0}
    for task in tasks:
        if task.is_done and task.category in totals and task.minutes:
            totals[task.category] += task.minutes
    return totals


def automation_candidates(tasks: Sequence[Task], limit: int = 5) -> list[tuple[str, int, int]]:
    """Category-B activities by total minutes — the automation backlog, derived.

    Category A is the instrument and stays manual however expensive it gets.
    Category C waits for evidence. Only B is sorted by cost, which is why this
    function refuses to look at anything else.
    """
    totals: dict[str, tuple[int, int]] = {}
    for task in tasks:
        if task.is_done and task.category == "B" and task.minutes:
            name = task.activity or task.title
            minutes, count = totals.get(name, (0, 0))
            totals[name] = (minutes + task.minutes, count + 1)
    ranked = sorted(totals.items(), key=lambda kv: -kv[1][0])
    return [(name, minutes, count) for name, (minutes, count) in ranked[:limit]]
