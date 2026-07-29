"""Run the evaluation.

    python -m eval --dry-run          # what it would do, and the worst-case cost
    python -m eval --budget 5         # do it, refusing past $5

Writes the report to stdout and, with --out, to a file. The key is read from
the environment and never written anywhere.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

from eval.report import render
from eval.runner import Evaluation, estimate_ceiling_usd, plan
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
    parser.add_argument("--out", type=pathlib.Path, help="also write the report here")
    return parser.parse_args()


def main() -> int:
    args = _parse()

    steps = plan()
    total = sum(steps.values())
    print("Evaluation plan", file=sys.stderr)
    for label, count in steps.items():
        print(f"  {count:>4}  {label}", file=sys.stderr)
    print(f"  {total:>4}  model calls, before tool-loop and section fan-out", file=sys.stderr)
    print(
        f"\nWorst case if every call maxes its output on the dearest model: "
        f"~${estimate_ceiling_usd():.2f}",
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

    if not (settings.anthropic_api_key or settings.openai_api_key or settings.enable_local_llm):
        print(
            "No provider key configured — this would evaluate the echo provider, "
            "which is exactly what the harness exists to get past.\n"
            "Set JARVIS_ANTHROPIC_API_KEY (or JARVIS_OPENAI_API_KEY) and retry.",
            file=sys.stderr,
        )
        return 2

    report = asyncio.run(Evaluation(settings).run())
    rendered = render(report)

    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Written to {args.out}", file=sys.stderr)
    print(rendered)

    accepted, wrong, count = report.routing_score
    print(
        f"\nRouting: {accepted}/{count} defensible, {wrong} actively wrong.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
