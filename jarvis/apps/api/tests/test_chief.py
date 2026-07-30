"""The Chief of Staff: delegation, and proactive intelligence.

Two halves that answer the same complaint. Until now Jarvis was reactive and
single-threaded: it did what it was asked, by one agent, and noticed nothing
in between. The prompts said otherwise — audit finding F4 — which made it a
system that described coordination it could not perform.

The tests below are mostly about restraint rather than capability. Anyone can
make a system that delegates; the hard part is not delegating when one agent
would do. Anyone can make a system that notices things; the hard part is not
saying all of them, because a proactive assistant that surfaces forty
observations gets muted inside a week and then notices nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from jarvis.agents.delegation import Assignment, Delegator, _parse
from jarvis.agents.registry import AgentRegistry
from jarvis.chief.engine import DISMISSAL_TTL, MAX_PER_SIGNAL, RecommendationEngine
from jarvis.chief.models import Impact, Recommendation, Signal, Urgency
from jarvis.chief.signals import (
    budget_pressure,
    cold_projects,
    deadlines,
    failed_runs,
    open_goals,
    pending_approvals,
    repeated_mistakes,
)
from jarvis.chief.situation import ProjectPage, Situation
from jarvis.kernel.clock import FrozenClock
from jarvis.memory.models import Memory, MemoryKind

NOW = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


def _memory(content: str, *, kind: MemoryKind, days_ago: int = 0, scope: str = "global") -> Memory:
    return Memory(
        content=content, kind=kind, scope=scope, created_at=NOW - timedelta(days=days_ago)
    )


@dataclass
class _Run:
    id: str
    request: str
    agent_id: str
    state: str
    error: str | None = None


@dataclass
class _Approval:
    id: str
    tool: str
    agent_id: str


# ── Ranking ───────────────────────────────────────────────────────────────────


def test_rank_is_arithmetic_anyone_can_check() -> None:
    """The load-bearing decision of the whole subsystem. If ranking were a
    model's opinion there would be nothing to correct when it was wrong."""
    blocking = Recommendation(
        id="a", signal=Signal.APPROVAL, headline="x", impact=Impact.MAJOR, urgency=Urgency.BLOCKING
    )
    someday = Recommendation(
        id="b",
        signal=Signal.COLD_PROJECT,
        headline="y",
        impact=Impact.CRITICAL,
        urgency=Urgency.WHENEVER,
        confidence=0.6,
    )
    assert blocking.score == 20.0
    assert someday.score == 3.0
    assert blocking.score > someday.score, "nothing distant outranks something blocking"


def test_a_low_confidence_guess_cannot_climb_by_claiming_to_be_critical() -> None:
    """Multiplicative, not additive. Otherwise every detector learns that the
    way to the top of the list is to assert importance."""
    certain = Recommendation(
        id="a",
        signal=Signal.APPROVAL,
        headline="x",
        impact=Impact.MODERATE,
        urgency=Urgency.TODAY,
        confidence=1.0,
    )
    guess = Recommendation(
        id="b",
        signal=Signal.COLD_PROJECT,
        headline="y",
        impact=Impact.CRITICAL,
        urgency=Urgency.TODAY,
        confidence=0.2,
    )
    assert certain.score > guess.score


# ── Detectors ─────────────────────────────────────────────────────────────────


def test_a_pending_approval_is_blocking_and_certain() -> None:
    """The only signal with no guesswork in it: a run is literally parked."""
    found = pending_approvals(
        Situation(now=NOW, approvals=[_Approval("apr_1", "browser_click", "shopping")])
    )
    assert found[0].urgency is Urgency.BLOCKING
    assert found[0].confidence == 1.0
    assert "browser_click" in found[0].headline


def test_a_failure_followed_by_success_is_not_reported() -> None:
    """What matters is not that something failed. It is that nothing happened
    afterwards."""
    handled = Situation(
        now=NOW,
        runs=[
            _Run("run_1", "deploy the thing", "coding", "failed", "boom"),
            _Run("run_2", "deploy the thing", "coding", "succeeded"),
        ],
    )
    assert failed_runs(handled) == []

    abandoned = Situation(
        now=NOW, runs=[_Run("run_1", "deploy the thing", "coding", "failed", "boom")]
    )
    assert len(failed_runs(abandoned)) == 1
    assert "boom" in failed_runs(abandoned)[0].why


def test_a_cold_project_is_important_and_never_urgent() -> None:
    """The whole trap, encoded. A cold project is never pressing, which is
    exactly how it got cold — so the ranking must not let urgency carry it."""
    situation = Situation(
        now=NOW,
        projects=[
            ProjectPage(
                path="Projects/Northbound.md",
                title="Northbound",
                updated=NOW - timedelta(days=90),
                memories=12,
            )
        ],
    )
    found = cold_projects(situation)
    assert found[0].impact is Impact.MAJOR
    assert found[0].urgency is Urgency.SOON
    assert "Northbound" in found[0].headline
    assert "12 note(s)" in found[0].why


def test_a_project_touched_last_week_is_not_cold() -> None:
    situation = Situation(
        now=NOW,
        projects=[ProjectPage(path="p.md", title="P", updated=NOW - timedelta(days=5))],
    )
    assert cold_projects(situation) == []


def test_a_goal_being_worked_on_stays_quiet() -> None:
    """Noticing drift means noticing *silence*, not noticing goals."""
    worked_on = Situation(
        now=NOW,
        memories=[
            _memory("Goal: ship the pricing page by Q3", kind=MemoryKind.GOAL, days_ago=40),
            _memory("Drafted the pricing copy today", kind=MemoryKind.FACT, days_ago=2),
        ],
    )
    assert open_goals(worked_on) == []

    drifted = Situation(
        now=NOW,
        memories=[_memory("Goal: ship the pricing page by Q3", kind=MemoryKind.GOAL, days_ago=40)],
    )
    assert len(drifted_found := open_goals(drifted)) == 1
    assert "pricing" in drifted_found[0].headline.lower()


def test_a_recent_goal_is_not_drift() -> None:
    fresh = Situation(
        now=NOW, memories=[_memory("Goal: launch in August", kind=MemoryKind.GOAL, days_ago=2)]
    )
    assert open_goals(fresh) == []


def test_only_dates_inside_the_horizon_are_deadlines() -> None:
    """A loose date parser turns every "in 2019" into a deadline, and an engine
    that cries wolf is one nobody reads."""
    situation = Situation(
        now=NOW,
        memories=[
            _memory("The lease renewal is due 2026-08-03", kind=MemoryKind.EVENT),
            _memory("We incorporated on 2019-04-01", kind=MemoryKind.FACT),
            _memory("Conference is 2027-01-01", kind=MemoryKind.EVENT),
        ],
    )
    found = deadlines(situation)
    assert len(found) == 1
    assert "2026-08-03" in found[0].headline
    assert found[0].urgency is Urgency.THIS_WEEK, "five days out is this week, not today"


def test_three_failures_in_one_place_is_a_process_problem() -> None:
    """A single mistake is an event. Telling the difference is something only a
    system with history can do."""
    once = Situation(
        now=NOW,
        memories=[_memory("The deploy broke again", kind=MemoryKind.MISTAKE, scope="coding")],
    )
    assert repeated_mistakes(once) == []

    thrice = Situation(
        now=NOW,
        memories=[
            _memory(f"Failure number {i}", kind=MemoryKind.MISTAKE, scope="coding")
            for i in range(3)
        ],
    )
    found = repeated_mistakes(thrice)
    assert len(found) == 1
    assert "3 recorded failures" in found[0].headline


def test_budget_pressure_fires_before_the_ceiling_refuses_work() -> None:
    quiet = Situation(
        now=NOW, budget={"budgets": [{"period": "day", "hard_usd": 25, "spent_usd": 4}]}
    )
    assert budget_pressure(quiet) == []

    tight = Situation(
        now=NOW, budget={"budgets": [{"period": "day", "hard_usd": 25, "spent_usd": 23.5}]}
    )
    found = budget_pressure(tight)
    assert found[0].urgency is Urgency.TODAY
    assert "94%" in found[0].headline


# ── The engine ────────────────────────────────────────────────────────────────


def _busy_situation() -> Situation:
    return Situation(
        now=NOW,
        approvals=[_Approval(f"apr_{i}", f"tool_{i}", "coding") for i in range(4)],
        runs=[_Run(f"run_{i}", f"task {i}", f"agent_{i}", "failed", "boom") for i in range(4)],
        projects=[
            ProjectPage(path=f"Projects/{i}.md", title=f"P{i}", updated=NOW - timedelta(days=100))
            for i in range(6)
        ],
        memories=[
            _memory(f"Goal number {i} about widgets", kind=MemoryKind.GOAL, days_ago=60)
            for i in range(5)
        ],
    )


def test_a_sweep_is_short_and_says_what_it_held_back() -> None:
    """The failure mode of every proactive assistant is noticing everything and
    prioritising nothing. A list of forty is a list nobody reads."""
    engine = RecommendationEngine(clock=FrozenClock(NOW), limit=10)
    sweep = engine.rank(_busy_situation())

    assert sweep.considered > 10
    assert len(sweep.recommendations) <= 10
    assert sweep.suppressed > 0, "the report must admit what it did not show"

    for count in sweep.by_signal().values():
        assert count <= MAX_PER_SIGNAL, "one signal must not crowd out the others"


def test_blocking_work_leads_regardless_of_what_else_is_happening() -> None:
    engine = RecommendationEngine(clock=FrozenClock(NOW))
    sweep = engine.rank(_busy_situation())
    assert sweep.recommendations[0].signal is Signal.APPROVAL
    assert sweep.blocking


def test_a_broken_detector_does_not_silence_the_others() -> None:
    def explodes(situation: Situation) -> list[Recommendation]:
        raise RuntimeError("nope")

    engine = RecommendationEngine(detectors=(explodes, pending_approvals), clock=FrozenClock(NOW))
    sweep = engine.rank(Situation(now=NOW, approvals=[_Approval("apr_1", "shell", "coding")]))
    assert len(sweep.recommendations) == 1
    assert "explodes" in sweep.unavailable


def test_a_source_that_could_not_be_read_is_named_not_swallowed() -> None:
    """A recommendation list silently missing a third of its inputs is worse
    than one that says what it could not see."""
    engine = RecommendationEngine(clock=FrozenClock(NOW))
    sweep = engine.rank(Situation(now=NOW, unavailable=["vault"]))
    assert sweep.unavailable == ["vault"]
    assert "vault" in sweep.to_dict()["unavailable"]


def test_the_same_thing_keeps_the_same_id_across_sweeps() -> None:
    """Without this, dismissing something would be meaningless — the next sweep
    would mint a fresh id and it would come straight back."""
    engine = RecommendationEngine(clock=FrozenClock(NOW))
    situation = Situation(now=NOW, approvals=[_Approval("apr_1", "shell", "coding")])
    assert engine.rank(situation).recommendations[0].id == (
        engine.rank(situation).recommendations[0].id
    )


def test_dismissal_holds_for_a_week_and_then_lets_it_ask_again() -> None:
    """ "Not now" is not the same answer as "never". A recommendation important
    enough to keep detecting is important enough to raise again."""
    clock = FrozenClock(NOW)
    engine = RecommendationEngine(clock=clock)
    situation = Situation(now=NOW, approvals=[_Approval("apr_1", "shell", "coding")])

    first = engine.rank(situation).recommendations[0]
    engine.dismiss(first.id)
    assert engine.rank(situation).recommendations == []

    later = Situation(now=NOW + DISMISSAL_TTL + timedelta(days=1), approvals=situation.approvals)
    assert engine.rank(later).recommendations, "a week later it is allowed to ask again"


def test_an_empty_system_recommends_nothing() -> None:
    """No news is a valid answer, and inventing something to say is how a
    recommendation engine trains people to ignore it."""
    engine = RecommendationEngine(clock=FrozenClock(NOW))
    assert engine.rank(Situation(now=NOW)).recommendations == []


# ── Delegation (audit F4) ─────────────────────────────────────────────────────


class _Router:
    """A router that says exactly what the test wants, once."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    async def complete(self, request: Any) -> Any:
        self.calls += 1

        class _Completion:
            text = self.reply

        return _Completion()


def test_only_agents_whose_prompts_promise_coordination_delegate() -> None:
    """`collaborators` finally means something, and it is what keeps twenty-odd
    specialists behaving exactly as they did."""
    registry = AgentRegistry()
    delegator = Delegator(_Router("[]"))
    long_request = "research the market and then write me the positioning for it"

    assert delegator.should_consider(registry.get("chief_of_staff"), long_request)
    assert not delegator.should_consider(registry.get("copywriter"), long_request)


def test_a_short_request_never_pays_for_a_decomposition_call() -> None:
    registry = AgentRegistry()
    delegator = Delegator(_Router("[]"))
    assert not delegator.should_consider(registry.get("chief_of_staff"), "handle it")


@pytest.mark.asyncio
async def test_one_assignment_is_not_a_delegation() -> None:
    """It is the same work with an extra model call in front of it."""
    registry = AgentRegistry()
    router = _Router('[{"agent":"research","task":"look into it"}]')
    assignments = await Delegator(router).decompose(
        "look into the oat milk market for me please",
        spec=registry.get("chief_of_staff"),
        registry=registry,
    )
    assert assignments == []


@pytest.mark.asyncio
async def test_a_real_split_produces_assignments() -> None:
    registry = AgentRegistry()
    router = _Router(
        '```json\n[{"agent":"research","task":"size the market"},'
        '{"agent":"copywriter","task":"draft the positioning"}]\n```'
    )
    assignments = await Delegator(router).decompose(
        "size the oat milk market and draft positioning from what you find",
        spec=registry.get("chief_of_staff"),
        registry=registry,
    )
    assert assignments == [
        Assignment("research", "size the market"),
        Assignment("copywriter", "draft the positioning"),
    ]


@pytest.mark.asyncio
async def test_delegation_cannot_reach_outside_a_narrowed_registry() -> None:
    """A mode narrows by handing over a smaller registry (ADR 0010). A
    delegator reaching for the full catalog would be a hole straight through
    it — the same defect as the hardcoded routing fallback in M9."""
    from jarvis.agents.catalog import CATALOG_BY_ID

    narrowed = AgentRegistry(
        [CATALOG_BY_ID["chief_of_staff"], CATALOG_BY_ID["coding"], CATALOG_BY_ID["architect"]]
    )
    router = _Router(
        '[{"agent":"coding","task":"fix it"},{"agent":"marketing","task":"promote it"},'
        '{"agent":"architect","task":"check the design"}]'
    )
    assignments = await Delegator(router).decompose(
        "fix the bug, check the design, and tell everybody about the release",
        spec=narrowed.get("chief_of_staff"),
        registry=narrowed,
    )
    assert [a.agent_id for a in assignments] == ["coding", "architect"]
    assert "marketing" not in {a.agent_id for a in assignments}


@pytest.mark.asyncio
async def test_a_narrowing_that_leaves_one_survivor_cancels_the_delegation() -> None:
    """Two rules composing correctly: the mode removes an agent, which leaves a
    single assignment, and a single assignment is not a delegation. The request
    falls back to one agent rather than to a one-item fan-out."""
    from jarvis.agents.catalog import CATALOG_BY_ID

    narrowed = AgentRegistry([CATALOG_BY_ID["chief_of_staff"], CATALOG_BY_ID["coding"]])
    router = _Router(
        '[{"agent":"coding","task":"fix it"},{"agent":"marketing","task":"promote it"}]'
    )
    assignments = await Delegator(router).decompose(
        "fix the bug and then tell everybody about the release",
        spec=narrowed.get("chief_of_staff"),
        registry=narrowed,
    )
    assert assignments == []


def test_an_invented_agent_id_is_refused_rather_than_dispatched() -> None:
    """Routing work to an agent that does not exist fails later and more
    confusingly than refusing here."""
    parsed = _parse(
        '[{"agent":"wizard","task":"do magic"},{"agent":"coding","task":"fix it"}]',
        known={"coding"},
    )
    assert [a.agent_id for a in parsed] == ["coding"]


def test_unparseable_output_means_no_delegation_rather_than_an_error() -> None:
    """Offline determinism is a product requirement (ADR 0001). The echo
    provider returns prose, and a feature that turns that into an error is a
    feature that breaks the demo."""
    assert _parse("[echo: I would split this into...]", known={"coding"}) == []
    assert _parse("", known={"coding"}) == []
    assert _parse('{"agent":"coding"}', known={"coding"}) == []


@pytest.mark.asyncio
async def test_offline_a_delegating_agent_still_answers(tmp_path: Any) -> None:
    """End to end on the echo provider: the decomposition returns nothing
    parseable and the request runs as a single agent, exactly as before."""
    from jarvis.config import Settings
    from jarvis.kernel import container

    jarvis = container.build(Settings(environment="test", enable_scheduler=False))
    deltas = [
        delta
        async for delta in jarvis.orchestrator.handle(
            "sort out the board pack and the hiring plan and the office lease"
        )
    ]
    kinds = {delta.type for delta in deltas}
    assert "delegation" not in kinds
    assert "done" in kinds


@pytest.mark.asyncio
async def test_delegation_streams_who_was_asked_what_then_one_answer() -> None:
    """The user asked one question and wants one answer, not four drafts and a
    summary — but the work should be visible while it happens."""
    from jarvis.config import Settings
    from jarvis.kernel import container

    jarvis = container.build(Settings(environment="test", enable_scheduler=False))
    assert jarvis.delegator is not None
    jarvis.delegator._router = _Router(
        '[{"agent":"research","task":"size the market"},'
        '{"agent":"copywriter","task":"draft positioning"}]'
    )

    deltas = [
        delta
        async for delta in jarvis.orchestrator.handle(
            "size the oat milk market and draft the positioning from it",
            agent_id="chief_of_staff",
        )
    ]
    by_type: dict[str, list[Any]] = {}
    for delta in deltas:
        by_type.setdefault(delta.type, []).append(delta)

    assigned = by_type["delegation"][0].data["assignments"]
    assert [a["agent"] for a in assigned] == ["research", "copywriter"]
    assert len(by_type["delegation_result"]) == 2
    assert by_type["done"][0].data["delegated_to"] == ["research", "copywriter"]
    # The specialists' prose is not streamed — only the synthesised answer is.
    assert "".join(d.text for d in by_type["token"])


@pytest.mark.asyncio
async def test_the_api_ranks_and_dismisses() -> None:
    from fastapi.testclient import TestClient

    from jarvis.config import Settings
    from jarvis.main import create_app

    with TestClient(create_app(Settings(environment="test", enable_scheduler=False))) as client:
        body = client.get("/v1/recommendations").json()
        assert "recommendations" in body
        assert "considered" in body
        assert client.post("/v1/recommendations/rec_made_up/dismiss").status_code == 204
