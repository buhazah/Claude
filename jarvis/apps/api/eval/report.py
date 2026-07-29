"""Rendering a run into something worth reading — and pasting.

Optimised for a human skimming for problems, not for a dashboard. The order is
the order of alarm: what broke, then what moved since the baseline, then the
scorecard, then the failures case by case, then the transcripts nobody scored.

The one rule this file follows everywhere: **never report a number without
reporting how much of it is proxy.** A weighted score next to a raw score next
to a skipped-check count is three numbers where one would read better, and the
one would be believed further than it deserves.
"""

from __future__ import annotations

from typing import Any

from eval.runner import Capture, Report, scrub
from eval.scoring import Drift, Verdict, summarise


def _fence(text: str) -> str:
    return text if text.strip() else "(empty)"


def _bar(value: float, width: int = 14) -> str:
    filled = round(value * width)
    return "█" * filled + "·" * (width - filled)


def _header(report: Report) -> list[str]:
    spend = report.spend.get("spend", {}).get("total", {})
    out = [
        "# Jarvis evaluation",
        "",
        f"- providers: {', '.join(report.providers) or 'none'}",
        f"- cases: {len(report.verdicts)} ({report.paid_cases} of them cost something)",
        f"- selection: {report.selection}",
        f"- wall clock: {report.seconds}s",
        f"- spend: ${float(spend.get('spent_usd', 0)):.4f} over {spend.get('calls', 0)} calls",
    ]
    if report.aborted:
        out += ["", f"> **Run aborted** — {report.aborted}", ""]

    # Loudest thing on the page when it applies. The fallback chain means a
    # broken key produces a full, plausible-looking report of echo output, and
    # a reader skimming for content will not notice the $0.00.
    if report.free:
        out += [
            "",
            "> **Free run.** No model was called. Routing was scored on stage one "
            "alone — the arbiter never ran, so requests that lexical scoring "
            "cannot decide are shown falling back to the Chief of Staff rather "
            "than being arbitrated. Treat the routing numbers as a floor.",
            "",
        ]
    elif not report.reached_a_real_provider:
        out += [
            "",
            "> # ⚠ NOTHING IN THIS REPORT CAME FROM A REAL MODEL",
            ">",
            "> Total spend is $0.00. Every call fell through to the offline "
            "`echo` provider, so the transcripts below are echoes of their own "
            "prompts, the arbiter never ran, and only the free suites — routing "
            "scored lexically, and memory recall — mean anything at all.",
            ">",
            "> **This is a configuration failure, not a result.** The usual "
            "cause is a key that carries a stray newline from copy-paste, which "
            "the transport rejects as an illegal header value.",
            "",
        ]
        if report.failures:
            out += ["**What actually failed:**", "", "```", *report.failures[:5], "```", ""]
    return out


def _scorecard_table(verdicts: list[Verdict]) -> list[str]:
    metrics = summarise(verdicts)
    out = [
        "## Scorecard",
        "",
        "`weighted` discounts each case by how much its author trusted the check "
        "to mean anything. Where it sits well below `raw`, the suite is leaning "
        "on proxies and should be read, not trusted.",
        "",
        "| suite | cases | pass | fatal | raw | weighted | conf | skipped | cost |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for name, m in metrics.items():
        fatal = f"**{m.fatal}**" if m.fatal else "0"
        out.append(
            f"| {name} | {m.cases} | {m.passed}/{m.scored} | {fatal} | "
            f"{m.mean_score:.2f} | `{_bar(m.weighted_score)}` {m.weighted_score:.2f} | "
            f"{m.mean_confidence:.2f} | {m.skipped_checks} | ${m.cost_usd:.4f} |"
        )
    total_fatal = sum(m.fatal for m in metrics.values())
    out += [
        "",
        f"**{total_fatal} fatal** — a case that landed somewhere the corpus calls "
        "actively wrong, or failed a check marked required. This is the number to "
        "read first; the averages hide it by design.",
        "",
    ]
    return out


def _drift_table(comparison: dict[str, Any]) -> list[str]:
    suites: dict[str, dict[str, float]] = comparison["suites"]
    drift: list[Drift] = comparison["drift"]

    out = [
        "## Against the baseline",
        "",
        "| suite | before | after | Δ | fatal before → after |",
        "|---|--:|--:|--:|:--|",
    ]
    for name, row in suites.items():
        delta = row["delta"]
        arrow = "→" if abs(delta) < 1e-9 else ("▲" if delta > 0 else "▼")
        out.append(
            f"| {name} | {row['before']:.2f} | {row['after']:.2f} | "
            f"{arrow} {delta:+.2f} | {row['fatal_before']} → {row['fatal_after']} |"
        )
    out.append("")

    broke = [d for d in drift if d.direction == "broke"]
    fixed = [d for d in drift if d.direction == "fixed"]
    if broke:
        out += [
            f"### {len(broke)} case(s) broke",
            "",
            *[f"- `{d.case_id}` — {d.before:.2f} → {d.after:.2f}, now fatal" for d in broke],
            "",
        ]
    if fixed:
        out += [
            f"### {len(fixed)} case(s) fixed",
            "",
            *[f"- `{d.case_id}` — was fatal, now {d.after:.2f}" for d in fixed],
            "",
        ]

    moved = [d for d in drift if d.direction in ("improved", "regressed")]
    if moved:
        out += [
            f"<details><summary>{len(moved)} case(s) moved without changing verdict</summary>",
            "",
            "| case | before | after |",
            "|---|--:|--:|",
            *[f"| `{d.case_id}` | {d.before:.2f} | {d.after:.2f} |" for d in moved],
            "",
            "</details>",
            "",
        ]
    if not drift:
        out += ["Nothing moved.", ""]
    if comparison["only_in_current"]:
        out += [
            f"*{len(comparison['only_in_current'])} case(s) are new since the "
            "baseline and were not compared.*",
            "",
        ]
    return out


def _failures(verdicts: list[Verdict]) -> list[str]:
    """Every case that landed somewhere wrong, worst first."""
    fatal = [v for v in verdicts if v.fatal]
    missed = [v for v in verdicts if not v.fatal and v.unmet]

    out: list[str] = ["## What failed", ""]
    if not fatal and not missed:
        out += ["Nothing. Read the transcripts anyway.", ""]
        return out

    if fatal:
        out += [
            "### Fatal",
            "",
            "| case | suite | request | why |",
            "|---|---|---|---|",
        ]
        for v in fatal:
            request = v.case.request.replace("|", "\\|")[:80]
            out.append(f"| `{v.case.id}` | {v.case.suite} | {request} | {v.fatal} |")
        out.append("")

    if missed:
        out += [
            f"<details><summary>{len(missed)} case(s) with soft misses</summary>",
            "",
            "| case | request | score | unmet |",
            "|---|---|--:|---|",
        ]
        for v in missed:
            request = v.case.request.replace("|", "\\|")[:60]
            unmet = "; ".join(v.unmet)[:120].replace("|", "\\|")
            out.append(f"| `{v.case.id}` | {request} | {v.score:.2f} | {unmet} |")
        out += ["", "</details>", ""]

    skipped = [v for v in verdicts if v.skipped and not v.met and not v.unmet]
    if skipped:
        out += [
            f"*{len(skipped)} case(s) had every check come back not-applicable and "
            "contributed nothing to any score — usually an errored turn or a tool "
            "the agent was never offered. They are not failures and are not "
            "counted as passes either.*",
            "",
        ]
    return out


def _routing_detail(verdicts: list[Verdict]) -> list[str]:
    routing = [v for v in verdicts if v.case.suite == "routing"]
    if not routing:
        return []
    escalated = sum(1 for v in routing if v.outcome.escalated)
    out = [
        "## Routing detail",
        "",
        f"**{escalated}/{len(routing)} escalated to the arbiter "
        f"({escalated / len(routing):.0%}).**",
        "",
        "The two-stage design is only worth having while this stays low. It is "
        "not an error rate — an escalation on a genuinely contested request is "
        "correct — but it is the number that went to 78% in M10 without anything "
        "else moving (audit F1).",
        "",
        "<details><summary>All routing decisions</summary>",
        "",
        "| request | chose | conf | esc | candidates |",
        "|---|---|--:|:-:|---|",
    ]
    for v in routing:
        mark = " ⚠" if v.fatal else ("" if v.passed else " ?")
        request = v.case.request.replace("|", "\\|")[:60]
        out.append(
            f"| {request} | `{v.outcome.agent}`{mark} | {v.outcome.confidence:.2f} | "
            f"{'↑' if v.outcome.escalated else ''} | {', '.join(v.outcome.candidates)} |"
        )
    out += ["", "</details>", ""]
    return out


def _transcripts(report: Report) -> list[str]:
    out = [
        "## Transcripts nobody scored",
        "",
        "These have no mechanical verdict, which is the point. Read them.",
        "",
    ]
    for capture in report.agents:
        out += [
            f"### `{capture.label}` — ${capture.cost_usd:.4f}, {capture.tokens} tokens",
            "",
            f"*Reading for:* {capture.extra.get('looking_for', '')}",
            "",
            f"> {capture.request}",
            "",
            "```",
            _fence(capture.error or capture.text),
            "```",
            "",
        ]

    if report.modes:
        out += [
            "### The same request in four modes",
            "",
            "If the four answers are interchangeable, the mode briefings are "
            "decoration and should be rewritten or dropped.",
            "",
        ]
        by_request: dict[str, list[Capture]] = {}
        for capture in report.modes:
            by_request.setdefault(capture.request, []).append(capture)
        for request, captures in by_request.items():
            out += [f"#### > {request}", "", f"*Expecting:* {captures[0].extra.get('why', '')}", ""]
            for capture in captures:
                out += [
                    f"**{capture.label}** → `{capture.agent}` (${capture.cost_usd:.4f})",
                    "",
                    "```",
                    _fence(capture.error or capture.text),
                    "```",
                    "",
                ]
    return out


def render(report: Report, *, comparison: dict[str, Any] | None = None) -> str:
    out = _header(report)
    out += _failures(report.verdicts)
    if comparison:
        out += _drift_table(comparison)
    out += _scorecard_table(report.verdicts)
    out += _routing_detail(report.verdicts)
    out += _transcripts(report)
    out += ["## Spend", "", "```", str(report.spend), "```", ""]
    return scrub("\n".join(out))
