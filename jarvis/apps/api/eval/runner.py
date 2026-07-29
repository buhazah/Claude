"""Driving the corpus against a real provider.

This is not a test suite. Tests assert, and "is this prompt any good" has no
boolean answer — so the routing cases are scored (there is a right answer) and
everything else is *captured* for a human to read.

Three safety properties, because this is the first code in the project that
spends money:

* **A hard ceiling.** The M10 cost governor is wired with a hard budget and no
  approver, so exceeding it aborts rather than parks. Until now every call cost
  zero and the ceilings had never fired in anger.
* **A dry run.** `--dry-run` prints the plan and an upper-bound cost without
  making a single call.
* **Redaction on the way out.** The report is meant to be pasted into a chat,
  so anything key-shaped from the environment is scrubbed from it.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

from eval.cases import (
    AGENT_PROBES,
    DOCUMENT_PROBES,
    MODE_PROBES,
    ROUTING_CASES,
    TOOL_PROBE,
    RoutingCase,
)
from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.security.budget import BudgetExceededError

MAX_CAPTURE_CHARS = 1_200
MODES = ("personal", "business", "coding", "research")


@dataclass
class RoutingResult:
    case: RoutingCase
    chosen: str
    confidence: float
    reasons: list[str]
    candidates: list[str]

    @property
    def accepted(self) -> bool:
        return self.chosen in self.case.accept

    @property
    def avoided(self) -> bool:
        """True when routing landed somewhere actively wrong."""
        return self.chosen in self.case.avoid


@dataclass
class Capture:
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
    model_hint: str = ""
    providers: list[str] = field(default_factory=list)
    routing: list[RoutingResult] = field(default_factory=list)
    agents: list[Capture] = field(default_factory=list)
    modes: list[Capture] = field(default_factory=list)
    documents: list[Capture] = field(default_factory=list)
    tools: list[Capture] = field(default_factory=list)
    spend: dict[str, Any] = field(default_factory=dict)
    aborted: str = ""
    seconds: float = 0.0
    # Errors seen on any capture. Collected because the fallback chain is good
    # at hiding them: the first call fails loudly, the circuit opens, and every
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

    @property
    def routing_score(self) -> tuple[int, int, int]:
        """(accepted, wrong, total). Wrong is the number that matters."""
        return (
            sum(1 for r in self.routing if r.accepted),
            sum(1 for r in self.routing if r.avoided),
            len(self.routing),
        )


def plan() -> dict[str, int]:
    """What a full pass will do, for the dry run."""
    return {
        "routing previews (may call the arbiter)": len(ROUTING_CASES),
        "agent turns": len(AGENT_PROBES),
        "mode turns": len(MODE_PROBES) * len(MODES),
        "documents (outline + one call per section)": len(DOCUMENT_PROBES),
        "tool-loop turns": 1,
    }


def estimate_ceiling_usd() -> float:
    """A deliberately pessimistic upper bound, priced at the dearest model.

    Under-estimating what a run will cost is the one error that matters here,
    so this assumes every call maxes its output allowance on Opus.
    """
    calls = sum(plan().values()) + len(DOCUMENT_PROBES) * 6  # sections
    return round(calls * (2_000 / 1e6 * 5.0 + 900 / 1e6 * 25.0), 2)


async def _drain(stream: Any) -> tuple[str, str, float, int]:
    """Collect a stream into (agent, text, cost, tokens)."""
    parts: list[str] = []
    agent, cost, tokens = "", 0.0, 0
    async for delta in stream:
        if delta.type == "routing":
            agent = str((delta.data or {}).get("chosen", ""))
        elif delta.type == "token":
            parts.append(delta.text)
        elif delta.type == "done":
            data = delta.data or {}
            agent = agent or str(data.get("agent", ""))
            cost = float(data.get("cost_usd") or 0.0)
            tokens = int(data.get("tokens") or 0)
        elif delta.type == "error":
            return agent, f"[error] {delta.text}", cost, tokens
    return agent, "".join(parts).strip(), cost, tokens


class Evaluation:
    def __init__(self, settings: Settings) -> None:
        self.jarvis = container.build(settings)
        self.report = Report(providers=self.jarvis.provider_names)

    async def run(self) -> Report:
        started = time.monotonic()
        await self.jarvis.start()
        try:
            await self._routing()
            await self._agents()
            await self._modes()
            await self._documents()
            await self._tools()
        except BudgetExceededError as exc:
            # Not a failure of the harness — the ceiling doing its job.
            self.report.aborted = f"budget ceiling reached: {exc}"
        finally:
            self.report.spend = self.jarvis.governor.snapshot()
            self.report.seconds = round(time.monotonic() - started, 1)
            await self.jarvis.stop()
        return self.report

    async def _routing(self) -> None:
        for case in ROUTING_CASES:
            matches = await self.jarvis.orchestrator.plan(case.request)
            best = matches[0]
            self.report.routing.append(
                RoutingResult(
                    case=case,
                    chosen=best.agent_id,
                    confidence=round(best.confidence, 3),
                    reasons=list(best.reasons)[:3],
                    candidates=[m.agent_id for m in matches],
                )
            )

    async def _agents(self) -> None:
        for probe in AGENT_PROBES:
            spec = self.jarvis.agents.get(probe.agent_id)
            _, text, cost, tokens = await _drain(
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
                    extra={"looking_for": probe.looking_for},
                )
            )
            if text.startswith("[error]"):
                self.report.failures.append(f"{probe.agent_id}: {text[:300]}")

    async def _modes(self) -> None:
        for probe in MODE_PROBES:
            for mode in MODES:
                orchestrator = self.jarvis.orchestrator_for(mode)
                agent, text, cost, tokens = await _drain(orchestrator.handle(probe.request))
                self.report.modes.append(
                    Capture(
                        label=mode,
                        request=probe.request,
                        agent=agent,
                        text=text[:MAX_CAPTURE_CHARS],
                        cost_usd=cost,
                        tokens=tokens,
                        extra={"why": probe.why},
                    )
                )

    async def _documents(self) -> None:
        for request, kind in DOCUMENT_PROBES:
            from jarvis.documents.models import DocumentKind

            outline: list[str] = []
            final = None
            async for event, document, _ in self.jarvis.composer.compose(
                request, kind=DocumentKind(kind)
            ):
                if event == "outline":
                    outline = [s.heading for s in document.sections]
                elif event in ("done", "error"):
                    final = document

            self.report.documents.append(
                Capture(
                    label=kind,
                    request=request,
                    text=(
                        final.sections[0].body[:MAX_CAPTURE_CHARS]
                        if final and final.sections
                        else ""
                    ),
                    cost_usd=final.cost_usd if final else 0.0,
                    tokens=final.tokens if final else 0,
                    extra={
                        "title": final.title if final else "",
                        "outline": outline,
                        "words": final.words if final else 0,
                        "citations": [c.reference for c in final.citations] if final else [],
                        "state": final.state.value if final else "never finished",
                    },
                )
            )

    async def _tools(self) -> None:
        spec = self.jarvis.agents.get("coding")
        calls: list[str] = []
        subscription = self.jarvis.bus.subscribe("tool.called")

        async def watch() -> None:
            async for event in subscription.events():
                calls.append(str(event.payload.get("tool", "")))

        watcher = asyncio.create_task(watch())
        _, text, cost, tokens = await _drain(
            self.jarvis.runtime.stream(spec, TOOL_PROBE, remember=False)
        )
        await asyncio.sleep(0.1)
        watcher.cancel()
        subscription.close()

        self.report.tools.append(
            Capture(
                label="tool loop",
                request=TOOL_PROBE,
                agent="coding",
                text=text[:MAX_CAPTURE_CHARS],
                cost_usd=cost,
                tokens=tokens,
                extra={"tools_called": calls},
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
