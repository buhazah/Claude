"""Run the evaluation.

    python -m eval --dry-run                 # the plan and a worst-case cost
    python -m eval --free                    # everything that costs nothing
    python -m eval --budget 5                # everything, refusing past $5
    python -m eval --suite routing memory    # only these
    python -m eval --sample 20               # at most 20 cases per suite
    python -m eval --baseline before.json    # and say what moved

The key is read from the environment and never written anywhere. `--free`
needs no key at all: the routing and memory suites run against the registry
and the store, so they are worth running on every commit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

from eval.corpus import CASES, by_suite, by_tier
from eval.report import render
from eval.runner import Evaluation, estimate_ceiling_usd, plan
from eval.scoring import Drift, Suite, Tier, compare, load_scorecard, scorecard
from jarvis.config import Settings


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m eval", description=__doc__)
    parser.add_argument(
        "--budget",
        type=float,
        default=5.0,
        help="hard ceiling in USD; the run aborts rather than exceeding it (default: 5)",
    )
    parser.add_argument("--dry-run", action="store_true", help="plan and cost, no calls")
    parser.add_argument(
        "--free",
        action="store_true",
        help="only the suites that cost nothing — no key required",
    )
    parser.add_argument(
        "--suite",
        nargs="+",
        default=[],
        choices=Suite.ALL,
        metavar="NAME",
        help=f"restrict to these suites ({', '.join(Suite.ALL)})",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        metavar="N",
        help="at most N cases per suite, spread across the whole suite",
    )
    parser.add_argument("--no-probes", action="store_true", help="skip the unscored transcripts")
    parser.add_argument("--out", type=pathlib.Path, help="also write the report here")
    parser.add_argument(
        "--scorecard",
        type=pathlib.Path,
        help="write a machine-readable scorecard here, to diff against later",
    )
    parser.add_argument(
        "--baseline",
        type=pathlib.Path,
        help="an earlier scorecard; the report says what moved since",
    )
    parser.add_argument("--note", default="", help="recorded in the scorecard, e.g. what changed")
    return parser.parse_args()


def main() -> int:
    args = _parse()
    # A free run still includes every routing case; it just runs stage one
    # alone. Excluding them would leave the free tier measuring only recall.
    max_tier = Tier.ROUTED if args.free else Tier.DOCUMENT
    suites = tuple(args.suite)

    from eval.corpus import select

    cases = select(suites=suites, max_tier=max_tier, limit_per_suite=args.sample)
    steps = plan(cases)

    print(f"Corpus: {len(CASES)} cases", file=sys.stderr)
    for suite, count in by_suite().items():
        print(f"  {count:>4}  {suite}", file=sys.stderr)
    print(f"\nBy cost tier: {by_tier()}", file=sys.stderr)
    print(f"\nThis run: {len(cases)} cases", file=sys.stderr)
    for label, count in steps.items():
        print(f"  {count:>4}  {label}", file=sys.stderr)
    print(
        f"\nWorst case if every call maxes its output on the dearest model: "
        f"~${estimate_ceiling_usd(cases):.2f}",
        file=sys.stderr,
    )
    print(f"Hard ceiling for this run: ${args.budget:.2f}\n", file=sys.stderr)

    if args.dry_run:
        print("Dry run — nothing was called.", file=sys.stderr)
        return 0

    # A hard ceiling with no approver: exceeding it must abort the run, not
    # park it waiting for a human who is watching a terminal, not a UI.
    settings = Settings(
        environment="eval",
        log_level="WARNING",
        enable_scheduler=False,
        # Every model call is priced against this one ceiling. `total` is the
        # natural period for a single run.
        monthly_budget_hard_usd=args.budget,
        daily_budget_hard_usd=args.budget,
    )

    has_key = bool(
        settings.anthropic_api_key or settings.openai_api_key or settings.enable_local_llm
    )
    if not has_key and not args.free:
        print(
            "No provider key configured — this would evaluate the echo provider, "
            "which is exactly what the harness exists to get past.\n"
            "Set JARVIS_ANTHROPIC_API_KEY (or JARVIS_OPENAI_API_KEY) and retry, "
            "or run `--free` for the suites that need no model.",
            file=sys.stderr,
        )
        return 2

    report = asyncio.run(
        Evaluation(
            settings,
            suites=suites,
            max_tier=max_tier,
            limit_per_suite=args.sample,
            probes=not args.no_probes and has_key and not args.free,
            free=args.free,
        ).run()
    )

    card = scorecard(report.verdicts, note=args.note)
    comparison = None
    if args.baseline:
        try:
            comparison = compare(load_scorecard(args.baseline), card)
        except (OSError, ValueError) as exc:
            print(f"Could not read the baseline: {exc}", file=sys.stderr)

    rendered = render(report, comparison=comparison)

    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
        # Resolved, not as given: a relative path leaves the reader to work out
        # where it landed, and on Windows they will guess wrong.
        print(f"\nReport written to:\n  {args.out.resolve()}\n", file=sys.stderr)
    if args.scorecard:
        args.scorecard.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        print(f"Scorecard written to:\n  {args.scorecard.resolve()}\n", file=sys.stderr)
    print(rendered)

    totals = card["totals"]
    assert isinstance(totals, dict)
    print(
        f"\n{totals['passed']}/{totals['cases']} passed, "
        f"{totals['fatal']} fatal, ${totals['cost_usd']:.4f} spent.",
        file=sys.stderr,
    )

    # The exit code answers "did this change make things worse", not "is the
    # corpus perfect". A corpus with no failures left in it has stopped being
    # an evaluation and become a formality, so an absolute fatal count is the
    # wrong gate the moment a baseline exists — what matters is what *moved*.
    if comparison is not None:
        drift: list[Drift] = comparison["drift"]  # type: ignore[assignment]
        broke = [d.case_id for d in drift if d.direction == "broke"]
        if broke:
            print(f"REGRESSION: {len(broke)} case(s) broke — {', '.join(broke)}", file=sys.stderr)
            return 1
        print("No regression against the baseline.", file=sys.stderr)
        return 0
    if args.scorecard:
        # Writing a scorecard with nothing to compare it to *is* establishing
        # the reference. Failing here would mean a corpus could never adopt a
        # baseline until it had no failures left, which is the same as saying
        # it could never adopt one.
        return 0
    return 1 if totals["fatal"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
