"""Rendering a run into something worth reading — and pasting.

Optimised for a human skimming for problems, not for a dashboard. Failures
first, then the transcripts, then the totals. The routing table shows the
*wrong* answers before the right ones for the same reason.
"""

from __future__ import annotations

from eval.runner import Capture, Report, scrub


def _fence(text: str) -> str:
    return text if text.strip() else "(empty)"


def render(report: Report) -> str:
    accepted, wrong, total = report.routing_score
    out: list[str] = [
        "# Jarvis evaluation — real models",
        "",
        f"- providers: {', '.join(report.providers) or 'none'}",
        f"- wall clock: {report.seconds}s",
        f"- spend: ${report.spend.get('spend', {}).get('total', {}).get('spent_usd', 0):.4f} "
        f"over {report.spend.get('spend', {}).get('total', {}).get('calls', 0)} calls",
    ]
    if report.aborted:
        out += ["", f"> **Run aborted** — {report.aborted}", ""]

    # Loudest thing on the page when it applies. The fallback chain means a
    # broken key produces a full, plausible-looking report of echo output, and
    # a reader skimming for content will not notice the $0.00.
    if not report.reached_a_real_provider:
        out += [
            "",
            "> # ⚠ NOTHING IN THIS REPORT CAME FROM A REAL MODEL",
            ">",
            "> Total spend is $0.00. Every call fell through to the offline "
            "`echo` provider, so the transcripts below are echoes of their own "
            "prompts and the routing score is stage-one lexical scoring only — "
            "the arbiter never ran.",
            ">",
            "> **This is a configuration failure, not a result.** The usual "
            "cause is a key that carries a stray newline from copy-paste, which "
            "the transport rejects as an illegal header value.",
            "",
        ]
        if report.failures:
            out += ["**What actually failed:**", "", "```"]
            out += report.failures[:5]
            out += ["```", ""]

    # ── Routing ───────────────────────────────────────────────────────────────
    out += [
        "",
        "## 1. Routing",
        "",
        f"**{accepted}/{total} landed on a defensible agent. "
        f"{wrong} landed somewhere actively wrong.**",
        "",
        "The second number is the one that matters — `accept` is a set of "
        "reasonable answers, `avoid` is a set of clear mistakes.",
        "",
    ]

    misses = [r for r in report.routing if not r.accepted]
    if misses:
        out += [
            "### Misses",
            "",
            "| request | chose | confidence | wrong? | expected one of |",
            "|---|---|---|---|---|",
        ]
        for r in misses:
            flag = "**yes**" if r.avoided else "no"
            out.append(
                f"| {r.case.request} | `{r.chosen}` | {r.confidence} | {flag} | "
                f"{', '.join(sorted(r.case.accept))} |"
            )
        out.append("")

    out += [
        "<details><summary>All routing decisions</summary>",
        "",
        "| request | chose | conf | candidates |",
        "|---|---|---|---|",
    ]
    for r in report.routing:
        mark = "" if r.accepted else " ⚠"
        out.append(
            f"| {r.case.request} | `{r.chosen}`{mark} | {r.confidence} | "
            f"{', '.join(r.candidates)} |"
        )
    out += ["", "</details>", ""]

    # ── Agents ────────────────────────────────────────────────────────────────
    out += ["## 2. Agent prompts", ""]
    for capture in report.agents:
        out += [
            f"### `{capture.label}` — ${capture.cost_usd:.4f}, {capture.tokens} tokens",
            "",
            f"*Reading for:* {capture.extra.get('looking_for', '')}",
            "",
            f"> {capture.request}",
            "",
            "```",
            _fence(capture.text),
            "```",
            "",
        ]

    # ── Modes ─────────────────────────────────────────────────────────────────
    out += [
        "## 3. Modes",
        "",
        "If the four answers to one request are interchangeable, the briefings "
        "are decoration and should be rewritten or dropped.",
        "",
    ]
    by_request: dict[str, list[Capture]] = {}
    for capture in report.modes:
        by_request.setdefault(capture.request, []).append(capture)

    for request, captures in by_request.items():
        out += [f"### > {request}", "", f"*Expecting:* {captures[0].extra.get('why', '')}", ""]
        for capture in captures:
            out += [
                f"**{capture.label}** → `{capture.agent}` (${capture.cost_usd:.4f})",
                "",
                "```",
                _fence(capture.text),
                "```",
                "",
            ]

    # ── Documents ─────────────────────────────────────────────────────────────
    out += ["## 4. Documents", ""]
    for capture in report.documents:
        extra = capture.extra
        out += [
            f"### {extra.get('title') or '(untitled)'} — {capture.label}",
            "",
            f"> {capture.request}",
            "",
            f"- state: **{extra.get('state')}** · {extra.get('words')} words · "
            f"${capture.cost_usd:.4f}",
            "- outline:",
        ]
        out += [f"  {i}. {h}" for i, h in enumerate(extra.get("outline", []), start=1)] or [
            "  (none)"
        ]
        citations = extra.get("citations", [])
        out += [
            "",
            f"- citations used: {len(citations)}"
            + (f" — {'; '.join(citations)}" if citations else " (knowledge base is empty)"),
            "",
            "First section:",
            "",
            "```",
            _fence(capture.text),
            "```",
            "",
        ]

    # ── Tools ─────────────────────────────────────────────────────────────────
    out += ["## 5. Tool loop", ""]
    for capture in report.tools:
        called = capture.extra.get("tools_called", [])
        out += [
            f"- tools actually called: {', '.join(called) if called else '**none**'}",
            f"- cost: ${capture.cost_usd:.4f}, {capture.tokens} tokens",
            "",
            "```",
            _fence(capture.text),
            "```",
            "",
        ]

    out += [
        "## Spend",
        "",
        "```",
        str(report.spend),
        "```",
        "",
    ]
    return scrub("\n".join(out))
