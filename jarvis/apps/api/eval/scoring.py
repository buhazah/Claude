"""The case model, the verdict, and the scorecard that makes runs comparable.

One `Case` type covers all ten dimensions rather than a class per suite. That
is a deliberate trade: the fields a routing case ignores are dead weight in its
declaration, but every case scores, samples, reports and *diffs against a
baseline* through one path. With ten suites and several hundred cases, a type
per suite would mean ten scoring functions to keep honest with each other, and
the thing being measured is whether the numbers moved — which is only
meaningful if every suite computes them the same way.

Scoring has three levels, and they are not interchangeable:

* **Fatal.** The case landed somewhere the corpus calls actively wrong: a
  routing `avoid`, or a failed `must`. One fatal is worth more attention than
  ten soft misses, so it is counted separately and never averaged away.
* **Must.** All of these have to hold for the case to pass.
* **Should.** Partial credit. These are the checks where a miss is a matter of
  degree — length, structure, tone.

`confidence` is the corpus author's estimate of how much the verdict is worth,
not the model's confidence in its answer. A routing case checked against a
deterministic scorer is 1.0. A rubric that approximates "did it reason well"
with keyword presence is 0.5, and says so. Metrics are reported both raw and
confidence-weighted, because a corpus that hides how much of its signal is
proxy is a corpus that will eventually be believed too much.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.checks import Check, Outcome

SCORECARD_VERSION = 1


class Suite:
    """The ten dimensions Phase 11 asked for coverage of."""

    ROUTING = "routing"
    PLANNING = "planning"
    TOOLS = "tools"
    MEMORY = "memory"
    RESEARCH = "research"
    EXECUTION = "execution"
    WORKFLOWS = "workflows"
    DOCUMENTS = "documents"
    CODING = "coding"
    BUSINESS = "business"

    ALL = (
        ROUTING,
        PLANNING,
        TOOLS,
        MEMORY,
        RESEARCH,
        EXECUTION,
        WORKFLOWS,
        DOCUMENTS,
        CODING,
        BUSINESS,
    )


class Tier:
    """How much a case costs to judge — which is how a budget picks what to run.

    LEXICAL cases never touch a model at all, so the whole routing suite can run
    on every commit. That is the point of separating them: the expensive suites
    are sampled, the free ones are exhaustive.
    """

    LEXICAL = "lexical"  # registry scoring only. Free.
    ROUTED = "routed"  # full plan(), may call the arbiter. One cheap call.
    TURN = "turn"  # run the agent. One call, more with tools.
    DOCUMENT = "document"  # outline plus a call per section.

    ORDER = (LEXICAL, ROUTED, TURN, DOCUMENT)


@dataclass(frozen=True, slots=True)
class Case:
    """One evaluation case, in the shape Phase 11 specified.

    - *expected behaviour* → `behaviour`, prose, and the `must`/`should` checks
      that approximate it mechanically
    - *expected agent* → `accept` / `avoid`
    - *expected tools* → the `called` / `never_called` checks
    - *success criteria* → `must`
    - *confidence score* → `confidence`
    """

    id: str
    suite: str
    request: str
    behaviour: str = ""
    # Agents that would be a defensible answer. Empty means routing is not what
    # this case is testing.
    accept: frozenset[str] = field(default_factory=frozenset)
    # Agents that would be a clear mistake. The sharper instrument of the two.
    avoid: frozenset[str] = field(default_factory=frozenset)
    # Pin the turn to one agent instead of routing to it. Used when the case is
    # about what an agent produces, not about who gets asked.
    agent: str = ""
    mode: str = ""
    # Seeded into memory before the turn, in the agent's own scope.
    memories: tuple[str, ...] = ()
    must: tuple[Check, ...] = ()
    should: tuple[Check, ...] = ()
    confidence: float = 1.0
    tier: str = Tier.LEXICAL

    def __post_init__(self) -> None:
        if self.suite not in Suite.ALL:
            raise ValueError(f"{self.id}: unknown suite {self.suite!r}")
        if not 0.0 < self.confidence <= 1.0:
            raise ValueError(f"{self.id}: confidence must be in (0, 1]")


@dataclass
class Verdict:
    """What one case did."""

    case: Case
    outcome: Outcome
    met: list[str] = field(default_factory=list)
    unmet: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    fatal: str = ""

    @property
    def passed(self) -> bool:
        return not self.fatal and not self.unmet

    @property
    def score(self) -> float:
        """Fraction of applicable checks met, with a fatal forcing zero.

        A case whose every check was skipped scores 1.0 only if nothing was
        fatal — there is nothing to hold against it — but it contributes no
        weight to the suite mean, so an outage cannot inflate a score.
        """
        if self.fatal:
            return 0.0
        applicable = len(self.met) + len(self.unmet)
        return len(self.met) / applicable if applicable else 1.0

    @property
    def weight(self) -> float:
        """How much this verdict counts. Nothing applicable means no signal."""
        return 0.0 if not (self.met or self.unmet or self.fatal) else self.case.confidence


def judge(case: Case, outcome: Outcome) -> Verdict:
    """Apply a case's checks to what actually happened."""
    verdict = Verdict(case=case, outcome=outcome)

    if case.avoid and outcome.agent and outcome.agent in case.avoid:
        verdict.fatal = f"routed to `{outcome.agent}`, which the case calls actively wrong"
    elif case.accept and outcome.agent and outcome.agent not in case.accept:
        # A miss, not a fatal: `accept` is a set of defensible answers, and
        # landing outside it is a matter of taste unless `avoid` says otherwise.
        verdict.unmet.append(f"routed to `{outcome.agent}`, expected one of {sorted(case.accept)}")
    elif case.accept and outcome.agent:
        verdict.met.append(f"routed to `{outcome.agent}`")

    if outcome.error:
        verdict.skipped.append(f"turn errored: {outcome.error[:120]}")

    for check in case.must:
        result = check(outcome)
        if result is None:
            verdict.skipped.append(check.label)
        elif result:
            verdict.met.append(check.label)
        else:
            verdict.unmet.append(check.label)
            if not verdict.fatal:
                verdict.fatal = f"required: {check.label}"

    for check in case.should:
        result = check(outcome)
        if result is None:
            verdict.skipped.append(check.label)
        elif result:
            verdict.met.append(check.label)
        else:
            verdict.unmet.append(check.label)

    return verdict


@dataclass
class SuiteMetrics:
    suite: str
    cases: int = 0
    scored: int = 0
    passed: int = 0
    fatal: int = 0
    skipped_checks: int = 0
    mean_score: float = 0.0
    weighted_score: float = 0.0
    mean_confidence: float = 0.0
    cost_usd: float = 0.0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.scored if self.scored else 0.0


def summarise(verdicts: Iterable[Verdict]) -> dict[str, SuiteMetrics]:
    """Per-suite metrics. This is the thing that gets compared between runs."""
    grouped: dict[str, list[Verdict]] = {}
    for verdict in verdicts:
        grouped.setdefault(verdict.case.suite, []).append(verdict)

    metrics: dict[str, SuiteMetrics] = {}
    for suite, group in sorted(grouped.items()):
        scored = [v for v in group if v.weight > 0]
        weights = [v.weight for v in scored]
        entry = SuiteMetrics(
            suite=suite,
            cases=len(group),
            scored=len(scored),
            passed=sum(1 for v in scored if v.passed),
            fatal=sum(1 for v in group if v.fatal),
            skipped_checks=sum(len(v.skipped) for v in group),
            mean_score=round(statistics.fmean([v.score for v in scored]), 4) if scored else 0.0,
            weighted_score=(
                round(sum(v.score * v.weight for v in scored) / sum(weights), 4) if weights else 0.0
            ),
            mean_confidence=round(statistics.fmean(weights), 3) if weights else 0.0,
            cost_usd=round(sum(v.outcome.cost_usd for v in group), 6),
        )
        metrics[suite] = entry
    return metrics


# ── The scorecard: how a prompt change stops being a guess ────────────────────


def scorecard(verdicts: list[Verdict], *, note: str = "") -> dict[str, object]:
    """A machine-readable record of one run, small enough to commit.

    Transcripts are deliberately absent. The scorecard exists to be diffed, and
    a diff of two hundred model outputs is unreadable; a diff of two hundred
    scores is exactly the question "did the change help".
    """
    metrics = summarise(verdicts)
    return {
        "version": SCORECARD_VERSION,
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": note,
        "totals": {
            "cases": len(verdicts),
            "fatal": sum(1 for v in verdicts if v.fatal),
            "passed": sum(1 for v in verdicts if v.weight > 0 and v.passed),
            "cost_usd": round(sum(v.outcome.cost_usd for v in verdicts), 6),
        },
        "suites": {name: vars(m) for name, m in metrics.items()},
        "cases": {
            v.case.id: {
                "score": round(v.score, 4),
                "fatal": bool(v.fatal),
                "agent": v.outcome.agent,
            }
            for v in verdicts
        },
    }


@dataclass(frozen=True, slots=True)
class Drift:
    """One case that changed verdict between two runs."""

    case_id: str
    before: float
    after: float
    was_fatal: bool
    now_fatal: bool

    @property
    def direction(self) -> str:
        if self.now_fatal and not self.was_fatal:
            return "broke"
        if self.was_fatal and not self.now_fatal:
            return "fixed"
        return "improved" if self.after > self.before else "regressed"


def compare(baseline: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    """What moved. The whole point of keeping a scorecard.

    Reports per-suite deltas and every case that changed verdict, so a prompt
    edit is answerable with "these eleven cases improved and these two broke"
    rather than with an overall average that hides both.
    """
    before_suites: dict[str, Any] = dict(baseline.get("suites", {}))  # type: ignore[call-overload]
    after_suites: dict[str, Any] = dict(current.get("suites", {}))  # type: ignore[call-overload]
    suites: dict[str, dict[str, float]] = {}
    for name in sorted(set(before_suites) | set(after_suites)):
        was = before_suites.get(name, {})
        now = after_suites.get(name, {})
        suites[name] = {
            "before": round(float(was.get("weighted_score", 0.0)), 4),
            "after": round(float(now.get("weighted_score", 0.0)), 4),
            "delta": round(
                float(now.get("weighted_score", 0.0)) - float(was.get("weighted_score", 0.0)), 4
            ),
            "fatal_before": int(was.get("fatal", 0)),
            "fatal_after": int(now.get("fatal", 0)),
        }

    before_cases: dict[str, Any] = dict(baseline.get("cases", {}))  # type: ignore[call-overload]
    after_cases: dict[str, Any] = dict(current.get("cases", {}))  # type: ignore[call-overload]
    drift: list[Drift] = []
    for case_id, now in after_cases.items():
        was = before_cases.get(case_id)
        if was is None:
            continue  # a new case has nothing to have moved from
        if abs(float(now["score"]) - float(was["score"])) < 1e-9 and now["fatal"] == was["fatal"]:
            continue
        drift.append(
            Drift(
                case_id=case_id,
                before=round(float(was["score"]), 4),
                after=round(float(now["score"]), 4),
                was_fatal=bool(was["fatal"]),
                now_fatal=bool(now["fatal"]),
            )
        )

    drift.sort(key=lambda d: (d.after - d.before, d.case_id))
    return {
        "suites": suites,
        "drift": drift,
        "only_in_current": sorted(set(after_cases) - set(before_cases)),
        "only_in_baseline": sorted(set(before_cases) - set(after_cases)),
    }


def load_scorecard(path: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != SCORECARD_VERSION:
        raise ValueError(
            f"{path} is a version {data.get('version')} scorecard; "
            f"this harness writes version {SCORECARD_VERSION}"
        )
    return data
