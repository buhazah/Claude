from __future__ import annotations

import pytest

from jarvis.agents.catalog import CATALOG, CATALOG_BY_ID, DEFAULT_AGENT_ID
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.spec import AgentMetrics
from jarvis.kernel.errors import NotFoundError


def test_catalog_ids_are_unique_and_specs_are_complete() -> None:
    ids = [spec.id for spec in CATALOG]
    assert len(ids) == len(set(ids))
    assert len(CATALOG) >= 30
    for spec in CATALOG:
        assert spec.name and spec.tagline
        assert spec.responsibilities, f"{spec.id} has no responsibilities"
        assert spec.keywords, f"{spec.id} has no routing keywords"
        assert len(spec.system_prompt) > 200, f"{spec.id} prompt is too thin"
        assert spec.id in spec.memory_scopes


def test_collaborators_reference_real_agents() -> None:
    for spec in CATALOG:
        for collaborator in spec.collaborators:
            assert collaborator in CATALOG_BY_ID, f"{spec.id} → unknown {collaborator}"


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("research competitors in the supplement market", "research"),
        ("fix the failing test in the auth module", "coding"),
        ("draft a reply to the email from Sarah", "email"),
        ("schedule a meeting with the design team next week", "calendar"),
        ("build a revenue forecast for next year", "financial_analyst"),
        ("review this contract for risky clauses", "legal"),
        ("write a landing page headline", "copywriter"),
        ("plan a trip to Tokyo in March", "travel"),
        ("remember that I prefer async standups", "memory"),
        ("automate this workflow when a form is submitted", "automation"),
        ("find leads for my supplement brand", "sales"),
        ("design the onboarding screen", "designer"),
        ("what should our pricing strategy be as a company", "ceo"),
    ],
)
def test_lexical_routing_picks_the_right_specialist(request_text: str, expected: str) -> None:
    registry = AgentRegistry()
    assert registry.route(request_text)[0].agent_id == expected


def test_unmatched_request_falls_back_to_the_chief_of_staff() -> None:
    registry = AgentRegistry()
    matches = registry.route("xyzzy plugh frobnicate")
    assert matches[0].agent_id == DEFAULT_AGENT_ID
    assert matches[0].confidence < 0.5


def test_route_returns_reasons_for_the_decision() -> None:
    matches = AgentRegistry().route("research the competitor landscape")
    assert matches[0].reasons
    assert any("research" in reason for reason in matches[0].reasons)


def test_route_respects_the_limit() -> None:
    assert len(AgentRegistry().route("write code and analyze data", limit=2)) == 2


def test_naming_an_agent_directly_dominates_keyword_matches() -> None:
    registry = AgentRegistry()
    assert registry.route("ask the life coach about my week")[0].agent_id == "life_coach"


def test_close_leaders_are_reported_as_ambiguous() -> None:
    registry = AgentRegistry()
    unmatched = registry.route("zzzz nothing here")
    assert registry.is_ambiguous(unmatched) is True

    clear = registry.route("fix the bug in the python function and write a test")
    assert registry.is_ambiguous(clear) is False


def test_track_record_nudges_but_does_not_overturn_routing() -> None:
    registry = AgentRegistry()
    metrics = registry.metrics("research")
    for _ in range(10):
        metrics.record(ok=False, latency_ms=100, cost_usd=0.0, tokens=10)

    # A failing agent scores lower, but still wins a request squarely in its remit.
    assert registry.route("research competitors in the supplement market")[0].agent_id == "research"


def test_unknown_agent_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        AgentRegistry().get("does_not_exist")


def test_metrics_track_success_rate_and_percentiles() -> None:
    metrics = AgentMetrics()
    assert metrics.success_rate == 1.0  # optimistic prior before any data

    for latency in range(1, 21):
        metrics.record(ok=latency % 5 != 0, latency_ms=latency * 10, cost_usd=0.01, tokens=100)

    assert metrics.runs == 20
    assert metrics.successes == 16
    assert metrics.success_rate == pytest.approx(0.8)
    assert metrics.avg_latency_ms == pytest.approx(105.0)
    assert metrics.p95_latency_ms == pytest.approx(190.0)
    assert metrics.total_cost_usd == pytest.approx(0.2)


def test_metrics_latency_window_is_bounded() -> None:
    metrics = AgentMetrics()
    for _ in range(250):
        metrics.record(ok=True, latency_ms=1.0, cost_usd=0.0, tokens=1)
    assert len(metrics.recent_latencies_ms) == 100
    assert metrics.runs == 250
