"""The attention rules. Deterministic, so every one of them can be pinned."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from ops import attention
from ops.models import Client, Interaction, Task

TODAY = date(2026, 8, 20)


def _client(**kw) -> Client:
    base = {"id": 1, "name": "Northbound", "status": "active", "trigger": "none"}
    return Client(**{**base, **kw})


def _interaction(client_id: int, days_ago: int, kind: str = "weekly") -> Interaction:
    when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time(), tzinfo=UTC)
    return Interaction(id=days_ago + 1, client_id=client_id, kind=kind, occurred_at=when)


def _reasons(clients, interactions=(), tasks=()) -> list[str]:
    return [a.reason for a in attention.review(clients, interactions, tasks, TODAY)]


def test_overdue_next_action_is_urgent():
    c = _client(next_action="send the audit", next_action_due=TODAY - timedelta(days=3))
    items = attention.review([c], [_interaction(1, 1)], [], TODAY)
    assert items[0].severity == attention.URGENT
    assert "3d ago" in items[0].reason


def test_next_action_due_today_is_soon_not_urgent():
    c = _client(next_action="call them", next_action_due=TODAY)
    items = attention.review([c], [_interaction(1, 1)], [], TODAY)
    assert items[0].severity == attention.SOON
    assert "due today" in items[0].reason


def test_future_next_action_is_silent():
    c = _client(next_action="call them", next_action_due=TODAY + timedelta(days=2))
    assert _reasons([c], [_interaction(1, 1)]) == []


def test_conversation_with_no_next_action_is_flagged():
    c = _client(status="conversation")
    assert "spoke to them, no next action set" in _reasons([c])


def test_active_client_never_contacted():
    assert "paying, never contacted" in _reasons([_client(status="active")])


def test_active_client_gone_quiet():
    c = _client(status="active")
    reasons = _reasons([c], [_interaction(1, 9)])
    assert any("no contact in 9d" in r for r in reasons)


def test_recent_contact_is_not_flagged():
    c = _client(status="active", active_since=TODAY - timedelta(days=10))
    assert _reasons([c], [_interaction(1, 2)]) == []


def test_monthly_review_overdue():
    c = _client(status="active", active_since=TODAY - timedelta(days=60))
    reasons = _reasons([c], [_interaction(1, 1)])
    assert any("no monthly review" in r for r in reasons)


def test_monthly_review_recent_is_quiet():
    c = _client(status="active", active_since=TODAY - timedelta(days=60))
    interactions = [_interaction(1, 1), _interaction(1, 10, kind="monthly_review")]
    assert _reasons([c], interactions) == []


def test_audit_past_day_five_without_reconciliation():
    c = _client(status="audit", audit_started_on=TODAY - timedelta(days=6))
    reasons = _reasons([c])
    assert any("reconciliation not recorded" in r for r in reasons)


def test_audit_with_reconciliation_recorded_clears_the_gate():
    c = _client(
        status="audit",
        audit_started_on=TODAY - timedelta(days=6),
        reconciliation_confidence=0.94,
    )
    assert not any("reconciliation not recorded" in r for r in _reasons([c]))


def test_stale_audit_not_yet_presented():
    c = _client(
        status="audit",
        audit_started_on=TODAY - timedelta(days=12),
        reconciliation_confidence=0.94,
    )
    assert any("not yet presented" in r for r in _reasons([c]))


def test_presented_audit_is_quiet():
    c = _client(
        status="audit",
        audit_started_on=TODAY - timedelta(days=12),
        reconciliation_confidence=0.94,
    )
    assert _reasons([c], [_interaction(1, 1, kind="audit_review")]) == []


def test_churn_without_an_exit_interview_is_urgent():
    c = _client(status="churned", churned_on=TODAY - timedelta(days=2))
    items = attention.review([c], [], [], TODAY)
    assert items[0].reason == "churned, no exit interview"
    assert items[0].severity == attention.URGENT


def test_churn_with_reason_recorded_is_quiet():
    c = _client(status="churned", churn_reason="they hired in-house")
    assert _reasons([c]) == []


def test_overdue_task_escalates_with_age():
    c = _client(status="active")
    fresh = Task(id=1, client_id=1, title="send report", due_on=TODAY - timedelta(days=1))
    stale = Task(id=2, client_id=1, title="fix tracking", due_on=TODAY - timedelta(days=5))
    items = attention.review([c], [_interaction(1, 1)], [fresh, stale], TODAY)
    by_reason = {a.reason: a.severity for a in items}
    assert by_reason["task overdue: send report"] == attention.SOON
    assert by_reason["task overdue: fix tracking"] == attention.URGENT


def test_completed_tasks_never_appear():
    c = _client(status="active")
    done = Task(
        id=1,
        client_id=1,
        title="send report",
        due_on=TODAY - timedelta(days=5),
        done_at=datetime.now(UTC),
        minutes=20,
        category="B",
    )
    assert _reasons([c], [_interaction(1, 1)], [done]) == []


def test_sorted_worst_first():
    quiet = _client(id=1, name="Alpha", status="active")
    loud = _client(id=2, name="Beta", status="conversation")
    items = attention.review([quiet, loud], [_interaction(1, 9)], [], TODAY)
    assert items[0].client_name == "Beta"
    assert items[0].severity == attention.URGENT


def test_unassigned_overdue_excludes_client_tasks():
    loose = Task(id=1, client_id=None, title="register domain", due_on=TODAY - timedelta(days=1))
    owned = Task(id=2, client_id=1, title="send report", due_on=TODAY - timedelta(days=1))
    assert [t.id for t in attention.unassigned_overdue([loose, owned], TODAY)] == [1]


def test_effort_only_counts_completed_work():
    done = Task(id=1, title="a", done_at=datetime.now(UTC), minutes=30, category="B")
    open_task = Task(id=2, title="b", minutes=None, category=None)
    assert attention.effort_by_category([done, open_task]) == {"A": 0, "B": 30, "C": 0}


def test_automation_backlog_is_category_b_only():
    tasks = [
        Task(
            id=1,
            title="x",
            activity="report_edit",
            done_at=datetime.now(UTC),
            minutes=100,
            category="B",
        ),
        Task(
            id=2,
            title="y",
            activity="creative_review",
            done_at=datetime.now(UTC),
            minutes=300,
            category="A",
        ),
        Task(
            id=3,
            title="z",
            activity="provisioning",
            done_at=datetime.now(UTC),
            minutes=50,
            category="B",
        ),
    ]
    backlog = attention.automation_candidates(tasks)
    assert [name for name, _, _ in backlog] == ["report_edit", "provisioning"]
    # The 300-minute category-A activity is the most expensive and is correctly absent:
    # it is the instrument, and hours are not an argument for automating it.
    assert "creative_review" not in [name for name, _, _ in backlog]


def test_backlog_aggregates_repeats_of_one_activity():
    tasks = [
        Task(
            id=i,
            title="t",
            activity="report_edit",
            done_at=datetime.now(UTC),
            minutes=20,
            category="B",
        )
        for i in range(1, 4)
    ]
    assert attention.automation_candidates(tasks) == [("report_edit", 60, 3)]


def test_funnel_counts_by_status():
    clients = [
        _client(id=1, status="prospect"),
        _client(id=2, status="active"),
        _client(id=3, status="active"),
    ]
    assert attention.funnel(clients) == {"prospect": 1, "active": 2}
