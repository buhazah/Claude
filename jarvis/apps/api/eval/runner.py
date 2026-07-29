"""Driving the corpus against a real provider.

This is not a test suite. Tests assert, and "is this prompt any good" has no
boolean answer — so cases are *scored* where a mechanical check is honest, and
*captured* for a human to read where it is not.

Four safety properties, because this is the only code in the project that
spends money:

* **A hard ceiling.** The M10 cost governor is wired with a hard budget and no
  approver, so exceeding it aborts rather than parks.
* **A dry run.** `--dry-run` prints the plan and an upper-bound cost without
  making a single call.
* **Tiers.** Most of the corpus never touches a model. The free suites run in
  full every time; the expensive ones are sampled, so a cheap run is a
  representative run rather than a truncated one.
* **Redaction on the way out.** The report is meant to be pasted into a chat,
  so anything key-shaped from the environment is scrubbed from it.

One thing the runner deliberately does *not* do is retry. A flaky call that
succeeds on the second attempt scores the same as one that succeeded first
time, and then the corpus is measuring persistence rather than quality.
Failures are recorded as failures and marked "not applicable" so they cannot
be mistaken for prompt defects.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from eval.checks import Outcome
from eval.corpus import AGENT_PROBES, MODE_PROBES, select
from eval.scoring import Case, Tier, Verdict, judge
from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.security.budget import BudgetExceededError

MAX_CAPTURE_CHARS = 1_200
MODES = ("personal", "business", "coding", "research")


@dataclass
class Capture:
    """A transcript nobody scored, kept so a human can read it."""

    label: str
    request: str
    agent: str = ""
    text: str = ""
    cost_usd: float = 0.0
    tokens: int = 0
    error: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    providers: list[str] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    agents: list[Capture] = field(default_factory=list)
    modes: list[Capture] = field(default_factory=list)
    spend: dict[str, Any] = field(default_factory=dict)
    aborted: str = ""
    seconds: float = 0.0
    selection: dict[str, Any] = field(default_factory=dict)
    # Errors seen anywhere. Collected because the fallback chain is good at
    # hiding them: the first call fails loudly, the circuit opens, and every
    # call after that degrades to echo in silence.
    failures: list[str] = field(default_factory=list)

    @property
    def reached_a_real_provider(self) -> bool:
        """Whether anything actually hit a paid model.

        Zero spend across dozens of calls with a real provider configured means
        the run measured the echo provider — which is precisely what this
        harness exists to get past. A report that does not say so at the top is
        worse than no report, because it reads as a result.
        """
        if self.providers == ["echo"]:
            return False
        total = self.spend.get("spend", {}).get("total", {})
        return float(total.get("spent_usd", 0.0)) > 0.0

    # Set by the runner. A free run reaching no provider is the requested
    # behaviour, not the silent-degradation failure the banner warns about,
    # and conflating the two would train the reader to ignore the banner.
    free: bool = False

    @property
    def paid_cases(self) -> int:
        if self.free:
            return 0
        return sum(1 for v in self.verdicts if v.case.tier != Tier.LEXICAL)


def plan(cases: tuple[Case, ...]) -> dict[str, int]:
    """What a pass will do, for the dry run."""
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.tier] = counts.get(case.tier, 0) + 1
    return {
        "free (registry only, no model)": counts.get(Tier.LEXICAL, 0),
        "routing previews (may call the arbiter)": counts.get(Tier.ROUTED, 0),
        "agent turns": counts.get(Tier.TURN, 0),
        "documents (outline + one call per section)": counts.get(Tier.DOCUMENT, 0),
        "unscored probes": len(AGENT_PROBES) + len(MODE_PROBES) * len(MODES),
    }


def estimate_ceiling_usd(cases: tuple[Case, ...]) -> float:
    """A deliberately pessimistic upper bound, priced at the dearest model.

    Under-estimating what a run will cost is the one error that matters here,
    so this assumes every call maxes its output allowance on the priciest tier,
    and that every document fans out to six sections.
    """
    steps = plan(cases)
    calls = (
        steps["routing previews (may call the arbiter)"]
        + steps["agent turns"]
        + steps["unscored probes"]
        + steps["documents (outline + one call per section)"] * 7
    )
    return round(calls * (2_000 / 1e6 * 5.0 + 900 / 1e6 * 25.0), 2)


async def _drain(stream: AsyncIterator[Any]) -> tuple[str, str, tuple[str, ...], float, int, str]:
    """Collect a stream into (agent, text, tools, cost, tokens, error)."""
    parts: list[str] = []
    tools: list[str] = []
    agent, cost, tokens, error = "", 0.0, 0, ""
    async for delta in stream:
        if delta.type == "routing":
            agent = str((delta.data or {}).get("chosen", ""))
        elif delta.type == "token":
            parts.append(delta.text)
        elif delta.type == "tool":
            tools.append(str((delta.data or {}).get("name", "")))
        elif delta.type == "done":
            data = delta.data or {}
            agent = agent or str(data.get("agent", ""))
            cost = float(data.get("cost_usd") or 0.0)
            tokens = int(data.get("tokens") or 0)
        elif delta.type == "error":
            error = delta.text
    return agent, "".join(parts).strip(), tuple(tools), cost, tokens, error


class Evaluation:
    def __init__(
        self,
        settings: Settings,
        *,
        suites: tuple[str, ...] = (),
        max_tier: str = Tier.DOCUMENT,
        limit_per_suite: int = 0,
        probes: bool = True,
        free: bool = False,
    ) -> None:
        self.jarvis = container.build(settings)
        self.cases = select(suites=suites, max_tier=max_tier, limit_per_suite=limit_per_suite)
        self.probes = probes
        # A free run still scores every routing case — it just never asks the
        # arbiter. That measures stage one on its own, which is the half that
        # can regress silently (audit F1) and the half worth gating a commit on.
        self.free = free
        self.report = Report(
            providers=self.jarvis.provider_names,
            free=free,
            selection={
                "suites": list(suites) or "all",
                "max_tier": max_tier,
                "limit_per_suite": limit_per_suite or None,
                "cases": len(self.cases),
            },
        )

    async def run(self) -> Report:
        started = time.monotonic()
        await self.jarvis.start()
        try:
            for case in self.cases:
                verdict = await self._one(case)
                self.report.verdicts.append(verdict)
                if verdict.outcome.error:
                    self.report.failures.append(f"{case.id}: {verdict.outcome.error[:200]}")
            if self.probes:
                await self._agent_probes()
                await self._mode_probes()
        except BudgetExceededError as exc:
            # Not a failure of the harness — the ceiling doing its job.
            self.report.aborted = f"budget ceiling reached: {exc}"
        finally:
            self.report.spend = self.jarvis.governor.snapshot()
            self.report.seconds = round(time.monotonic() - started, 1)
            await self.jarvis.stop()
        return self.report

    async def _one(self, case: Case) -> Verdict:
        if case.suite == "memory":
            return judge(case, await self._recall(case))
        if case.tier == Tier.DOCUMENT:
            return judge(case, await self._document(case))
        if case.tier == Tier.ROUTED:
            return judge(case, await self._route(case))
        return judge(case, await self._turn(case))

    # ── Routing: no turn, so nothing is generated and nothing is spent beyond
    # the arbiter when stage one declines to decide. ──────────────────────────

    async def _route(self, case: Case) -> Outcome:
        orchestrator = (
            self.jarvis.orchestrator_for(case.mode) if case.mode else (self.jarvis.orchestrator)
        )
        registry = orchestrator.registry
        lexical = registry.route(case.request)
        escalated = registry.is_ambiguous(lexical)
        matches = lexical if self.free else await orchestrator.plan(case.request)
        return Outcome(
            agent=matches[0].agent_id,
            confidence=round(matches[0].confidence, 4),
            candidates=tuple(m.agent_id for m in matches),
            escalated=escalated,
            extra={"reasons": list(matches[0].reasons)[:3]},
        )

    # ── Memory: seeded then queried, with no model in the loop at all. ────────

    async def _recall(self, case: Case) -> Outcome:
        scope = f"eval:{case.id}"
        for content in case.memories:
            await self.jarvis.memory.remember(content, scope=scope, source="eval")
        recalls = await self.jarvis.memory.search(case.request, limit=4, scope=scope)
        return Outcome(
            text="\n".join(r.memory.content for r in recalls),
            extra={
                "recalled": " || ".join(r.memory.content for r in recalls),
                "scores": [round(r.score, 3) for r in recalls],
            },
        )

    # ── A turn: the agent runs, tools included. ───────────────────────────────

    async def _turn(self, case: Case) -> Outcome:
        orchestrator = (
            self.jarvis.orchestrator_for(case.mode) if case.mode else (self.jarvis.orchestrator)
        )
        spec = orchestrator.registry.get(case.agent) if case.agent else None
        if spec is None:
            agent, text, tools, cost, tokens, error = await _drain(
                orchestrator.handle(case.request)
            )
        else:
            for content in case.memories:
                await self.jarvis.memory.remember(content, scope=spec.scope, source="eval")
            agent, text, tools, cost, tokens, error = await _drain(
                self.jarvis.runtime.stream(spec, case.request, remember=False)
            )
            agent = spec.id
        offered = (
            tuple(schema.name for schema in self.jarvis.tools.schemas_for(spec.tools))
            if spec
            else ()
        )
        return Outcome(
            text=text,
            agent=agent,
            tools_called=tools,
            tools_offered=offered,
            error=error,
            cost_usd=cost,
            tokens=tokens,
        )

    # ── A document: outline, then a call per section. ─────────────────────────

    async def _document(self, case: Case) -> Outcome:
        from jarvis.documents.models import DocumentKind

        outline: list[str] = []
        final = None
        error = ""
        async for event, document, _ in self.jarvis.composer.compose(
            case.request, kind=DocumentKind(case.agent)
        ):
            if event == "outline":
                outline = [s.heading for s in document.sections]
            elif event in ("done", "error"):
                final = document
                if event == "error":
                    error = document.error or "composition failed"

        body = "\n\n".join(s.body for s in final.sections) if final else ""
        retrieved = sum(len(s.citations) for s in final.sections) if final else 0
        return Outcome(
            text=body,
            agent=case.agent,
            error=error,
            cost_usd=final.cost_usd if final else 0.0,
            tokens=final.tokens if final else 0,
            extra={
                "title": final.title if final else "",
                "outline": outline,
                "words": final.words if final else 0,
                "citations": [c.reference for c in final.citations] if final else [],
                "retrieved": retrieved,
                "state": final.state.value if final else None,
            },
        )

    # ── Unscored probes ───────────────────────────────────────────────────────

    async def _agent_probes(self) -> None:
        for probe in AGENT_PROBES:
            spec = self.jarvis.agents.get(probe.agent_id)
            _, text, _, cost, tokens, error = await _drain(
                self.jarvis.runtime.stream(spec, probe.request, remember=False)
            )
            self.report.agents.append(
                Capture(
                    label=probe.agent_id,
                    request=probe.request,
                    agent=probe.agent_id,
                    text=text[:MAX_CAPTURE_CHARS],
                    cost_usd=cost,
                    tokens=tokens,
                    error=error,
                    extra={"looking_for": probe.looking_for},
                )
            )
            if error:
                self.report.failures.append(f"probe {probe.agent_id}: {error[:200]}")

    async def _mode_probes(self) -> None:
        for probe in MODE_PROBES:
            for mode in MODES:
                orchestrator = self.jarvis.orchestrator_for(mode)
                agent, text, _, cost, tokens, error = await _drain(
                    orchestrator.handle(probe.request)
                )
                self.report.modes.append(
                    Capture(
                        label=mode,
                        request=probe.request,
                        agent=agent,
                        text=text[:MAX_CAPTURE_CHARS],
                        cost_usd=cost,
                        tokens=tokens,
                        error=error,
                        extra={"why": probe.why},
                    )
                )


def scrub(text: str) -> str:
    """Remove anything key-shaped in the environment from the report.

    The report is written to be pasted into a chat window, so this is the last
    line of defence between an API key and a transcript. Blunt on purpose.
    """
    cleaned = text
    for name, value in os.environ.items():
        if not value or len(value) < 12:
            continue
        if any(hint in name.upper() for hint in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            cleaned = cleaned.replace(value, f"«{name} redacted»")
    return cleaned


__all__ = ["Capture", "Evaluation", "Report", "asyncio", "estimate_ceiling_usd", "plan", "scrub"]
