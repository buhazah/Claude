"""The evaluation harness is code, and code that grades other code has to be
graded itself.

The failure this file exists to prevent is the worst one an eval harness has:
**scoring that flatters**. A check that returns True when it could not decide,
a suite average that counts an outage as a pass, a baseline diff that reports
"nothing moved" because it silently compared nothing — each of those produces a
green number that means nothing, and a green number that means nothing is worse
than a red one, because it stops the search.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eval.checks import Outcome, called, called_nothing, mentions, no_filler, options
from eval.corpus import CASES, by_suite, by_tier, select
from eval.scoring import Case, Suite, Tier, compare, judge, load_scorecard, scorecard, summarise

# ── The corpus itself ─────────────────────────────────────────────────────────


def test_the_corpus_is_large_and_covers_every_dimension() -> None:
    counts = by_suite()
    assert len(CASES) >= 250, f"corpus has shrunk to {len(CASES)}"
    for suite, count in counts.items():
        assert count > 0, f"suite {suite} has no cases"


def test_every_case_id_is_unique() -> None:
    # Also asserted at import time, because a duplicate id silently overwrites
    # a row in the scorecard and the baseline diff then compares the wrong pair.
    assert len({case.id for case in CASES}) == len(CASES)


def test_every_case_names_agents_that_exist() -> None:
    from jarvis.agents.catalog import CATALOG_BY_ID
    from jarvis.documents.models import DocumentKind

    kinds = {k.value for k in DocumentKind}
    for case in CASES:
        for agent_id in case.accept | case.avoid:
            assert agent_id in CATALOG_BY_ID, f"{case.id} names unknown agent {agent_id}"
        if case.agent:
            known = case.agent in CATALOG_BY_ID or case.agent in kinds
            assert known, f"{case.id} pins unknown agent/kind {case.agent}"


def test_accept_and_avoid_never_overlap() -> None:
    """A case that both accepts and avoids an agent can never be satisfied, and
    would sit in the report forever as an unexplainable failure."""
    for case in CASES:
        assert not (case.accept & case.avoid), f"{case.id} both accepts and avoids the same agent"


def test_expensive_cases_carry_a_rubric() -> None:
    """A turn that costs money and checks nothing is a transcript, and
    transcripts belong in the probes where they are read rather than scored."""
    for case in CASES:
        if case.tier in (Tier.TURN, Tier.DOCUMENT):
            assert case.must or case.should, f"{case.id} spends money and asserts nothing"
            assert case.behaviour, f"{case.id} spends money without saying what good looks like"


def test_most_of_the_corpus_is_free() -> None:
    """The economics that make this runnable. If the free share collapses, the
    corpus stops being something anyone runs."""
    tiers = by_tier()
    free = tiers[Tier.LEXICAL] + tiers[Tier.ROUTED]
    assert free / len(CASES) > 0.6


# ── Selection ─────────────────────────────────────────────────────────────────


def test_sampling_spreads_across_a_suite_rather_than_taking_a_prefix() -> None:
    """Taking the first N would mean the everyday cases never ran and the traps
    ran every time — the opposite of what a sample is for."""
    sampled = select(suites=(Suite.ROUTING,), limit_per_suite=10)
    assert len(sampled) == 10
    ids = [c.id for c in sampled]
    assert any(i.startswith("everyday-") for i in ids), "sample never reached the long tail"
    assert any(i.startswith("route-") for i in ids), "sample never reached the curated cases"


def test_a_free_selection_excludes_everything_that_spends() -> None:
    for case in select(max_tier=Tier.ROUTED):
        assert case.tier in (Tier.LEXICAL, Tier.ROUTED)


# ── Checks ────────────────────────────────────────────────────────────────────


def test_a_check_on_an_errored_turn_is_not_applicable_rather_than_failed() -> None:
    """A provider outage must not read as a prompt regression. This is the
    single most important behaviour in the harness."""
    broken = Outcome(text="", error="502 from the provider")
    assert mentions("anything")(broken) is None
    assert no_filler()(broken) is None


def test_a_tool_check_is_not_applicable_when_the_tool_was_never_offered() -> None:
    """An agent cannot fail to use a tool it does not have — that is a wiring
    defect, which the catalog test owns, not a selection defect."""
    without = Outcome(text="done", tools_offered=())
    assert called("list_files")(without) is None

    with_other = Outcome(text="done", tools_offered=("read_file",))
    assert called("list_files")(with_other) is None

    offered = Outcome(text="done", tools_offered=("list_files",), tools_called=())
    assert called("list_files")(offered) is False


def test_knowing_when_not_to_call_a_tool_is_measured_too() -> None:
    quiet = Outcome(text="60", tools_offered=("memory_search",), tools_called=())
    chatty = Outcome(text="60", tools_offered=("memory_search",), tools_called=("memory_search",))
    assert called_nothing()(quiet) is True
    assert called_nothing()(chatty) is False


def test_options_counts_listed_items_not_paragraphs() -> None:
    three = Outcome(text="1. Sleep better\n2. Wake up sharper\n3. Stop counting sheep")
    one = Outcome(text="Sleep better. It is a great headline and here is why it works.")
    assert options(3)(three) is True
    assert options(3)(one) is False


def test_a_check_that_raises_is_not_applicable_rather_than_fatal() -> None:
    from eval.checks import Check

    exploding = Check("boom", lambda o: 1 / 0)  # type: ignore[arg-type,return-value]
    assert exploding(Outcome(text="hello")) is None


# ── Judging ───────────────────────────────────────────────────────────────────


def _case(**kwargs: object) -> Case:
    base = {"id": "t-1", "suite": Suite.ROUTING, "request": "x"}
    return Case(**{**base, **kwargs})  # type: ignore[arg-type]


def test_landing_on_an_avoided_agent_is_fatal() -> None:
    case = _case(accept=frozenset({"legal"}), avoid=frozenset({"coding"}))
    verdict = judge(case, Outcome(agent="coding"))
    assert verdict.fatal
    assert verdict.score == 0.0


def test_landing_outside_accept_is_a_miss_not_a_fatal() -> None:
    """`accept` is a set of defensible answers. Landing outside it is a matter
    of taste unless `avoid` says otherwise, and treating it as fatal would
    measure conformity to the corpus author."""
    case = _case(accept=frozenset({"legal"}), avoid=frozenset({"coding"}))
    verdict = judge(case, Outcome(agent="research"))
    assert not verdict.fatal
    assert verdict.unmet


def test_a_failed_must_is_fatal_and_a_failed_should_is_not() -> None:
    hard = _case(suite=Suite.BUSINESS, must=(mentions("three"),), tier=Tier.TURN)
    soft = _case(suite=Suite.BUSINESS, should=(mentions("three"),), tier=Tier.TURN)
    outcome = Outcome(text="only one option here")
    assert judge(hard, outcome).fatal
    assert not judge(soft, outcome).fatal


def test_a_case_whose_checks_all_skipped_contributes_no_weight() -> None:
    """Otherwise an outage inflates the suite average: every check comes back
    not-applicable, the score defaults to 1.0, and the run looks perfect."""
    case = _case(suite=Suite.BUSINESS, must=(mentions("anything"),), tier=Tier.TURN, confidence=1.0)
    verdict = judge(case, Outcome(text="", error="502"))
    assert verdict.weight == 0.0

    metrics = summarise([verdict])
    assert metrics[Suite.BUSINESS].scored == 0
    assert metrics[Suite.BUSINESS].weighted_score == 0.0


def test_confidence_weights_the_suite_score() -> None:
    """A proxy check and a deterministic one must not count the same."""
    trusted = judge(
        _case(id="a", suite=Suite.BUSINESS, must=(mentions("x"),), confidence=1.0, tier=Tier.TURN),
        Outcome(text="x"),
    )
    proxy = judge(
        _case(id="b", suite=Suite.BUSINESS, must=(mentions("x"),), confidence=0.2, tier=Tier.TURN),
        Outcome(text="nothing"),
    )
    metrics = summarise([trusted, proxy])[Suite.BUSINESS]
    assert metrics.mean_score == pytest.approx(0.5)
    assert metrics.weighted_score > metrics.mean_score, "the low-confidence miss should count less"


# ── The scorecard and the diff ────────────────────────────────────────────────


def test_a_scorecard_round_trips_and_rejects_a_foreign_version(tmp_path: Path) -> None:
    verdicts = [judge(_case(accept=frozenset({"legal"})), Outcome(agent="legal"))]
    path = tmp_path / "card.json"
    path.write_text(json.dumps(scorecard(verdicts, note="baseline")))
    assert load_scorecard(path)["note"] == "baseline"

    path.write_text(json.dumps({"version": 99}))
    with pytest.raises(ValueError, match="version 99"):
        load_scorecard(path)


def test_the_diff_names_what_broke_and_what_was_fixed() -> None:
    before = scorecard(
        [
            judge(_case(id="kept", accept=frozenset({"legal"})), Outcome(agent="legal")),
            judge(_case(id="broke", accept=frozenset({"legal"})), Outcome(agent="legal")),
            judge(
                _case(id="fixed", accept=frozenset({"legal"}), avoid=frozenset({"coding"})),
                Outcome(agent="coding"),
            ),
        ]
    )
    after = scorecard(
        [
            judge(_case(id="kept", accept=frozenset({"legal"})), Outcome(agent="legal")),
            judge(
                _case(id="broke", accept=frozenset({"legal"}), avoid=frozenset({"coding"})),
                Outcome(agent="coding"),
            ),
            judge(_case(id="fixed", accept=frozenset({"legal"})), Outcome(agent="legal")),
            judge(_case(id="brand-new", accept=frozenset({"legal"})), Outcome(agent="legal")),
        ]
    )
    result = compare(before, after)
    directions = {d.case_id: d.direction for d in result["drift"]}
    assert directions == {"broke": "broke", "fixed": "fixed"}
    assert result["only_in_current"] == ["brand-new"]


def test_a_new_case_is_not_reported_as_an_improvement() -> None:
    """A case with no baseline has nothing to have moved from. Counting it as a
    win is how a corpus talks itself into believing every change helped."""
    before = scorecard([])
    after = scorecard([judge(_case(id="new", accept=frozenset({"legal"})), Outcome(agent="legal"))])
    assert compare(before, after)["drift"] == []


# ── The regression gate ───────────────────────────────────────────────────────


def test_stage_one_routing_does_not_regress_against_the_committed_baseline() -> None:
    """The corpus earning its keep.

    `eval/baseline.json` is a committed floor produced by `make eval-baseline`.
    This scores every routing case against the registry alone — no arbiter, no
    model, no network — and fails if a change made stage one worse.

    Scored on `fatal` rather than on the average, deliberately. An average can
    absorb a new confident mis-route by improving three vague ones, and a
    confident mis-route is the failure that reaches a user.
    """
    from eval.checks import Outcome
    from eval.scoring import scorecard

    from jarvis.agents.registry import AgentRegistry

    baseline = load_scorecard(Path(__file__).parent.parent / "eval" / "baseline.json")
    registry = AgentRegistry()

    verdicts = []
    for case in select(suites=(Suite.ROUTING,)):
        matches = registry.route(case.request)
        verdicts.append(
            judge(
                case,
                Outcome(
                    agent=matches[0].agent_id,
                    confidence=matches[0].confidence,
                    candidates=tuple(m.agent_id for m in matches),
                    escalated=registry.is_ambiguous(matches),
                ),
            )
        )

    current = scorecard(verdicts)
    was = baseline["suites"][Suite.ROUTING]  # type: ignore[index]
    now = current["suites"][Suite.ROUTING]  # type: ignore[index]

    broke = [d.case_id for d in compare(baseline, current)["drift"] if d.direction == "broke"]
    assert not broke, f"these routing cases now land somewhere actively wrong: {broke}"
    assert now["fatal"] <= was["fatal"], (
        f"stage one got worse: {was['fatal']} fatal → {now['fatal']}"
    )
    assert now["weighted_score"] >= was["weighted_score"] - 0.02, (
        f"routing quality dropped: {was['weighted_score']:.3f} → {now['weighted_score']:.3f}"
    )
