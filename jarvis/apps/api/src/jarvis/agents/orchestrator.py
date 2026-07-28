"""Orchestration: deciding who does the work, then making sure it happens.

Stage one (``AgentRegistry.route``) is free and deterministic. The orchestrator
only escalates to an LLM arbiter when stage one is genuinely ambiguous — a weak
top match, or two near-equal leaders — so the common case adds zero latency and
zero cost, while the hard case still gets judgement.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import structlog

from jarvis.agents.registry import AgentRegistry
from jarvis.agents.runtime import AgentDelta, AgentRuntime
from jarvis.agents.spec import AgentMatch, AgentSpec
from jarvis.kernel.bus import EventBus
from jarvis.llm.base import CompletionRequest, Message, Role, RoutingPolicy
from jarvis.llm.router import ModelRouter
from jarvis.runs.models import RunStore, StepKind

log = structlog.get_logger(__name__)

ARBITER_PROMPT = (
    "You route requests to specialist agents inside Jarvis.\n"
    "Given the request and the candidate agents, reply with ONLY the id of the "
    "single best agent. No punctuation, no explanation."
)


class Orchestrator:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        runtime: AgentRuntime,
        router: ModelRouter,
        runs: RunStore,
        bus: EventBus,
        use_arbiter: bool = True,
    ) -> None:
        self._registry = registry
        self._runtime = runtime
        self._router = router
        self._runs = runs
        self._bus = bus
        self._use_arbiter = use_arbiter

    async def _arbitrate(self, request: str, candidates: list[AgentMatch]) -> AgentMatch:
        """Ask a cheap, fast model to break a tie between close candidates."""
        options = "\n".join(
            f"- {m.agent_id}: {self._registry.get(m.agent_id).tagline}" for m in candidates
        )
        prompt = f"Request: {request}\n\nCandidates:\n{options}\n\nBest agent id:"
        try:
            completion = await self._router.complete(
                CompletionRequest(
                    messages=[Message(role=Role.USER, content=prompt)],
                    system=ARBITER_PROMPT,
                    policy=RoutingPolicy.FAST,
                    max_output_tokens=16,
                    temperature=0.0,
                )
            )
        except Exception as exc:
            log.warning("arbiter_failed", error=str(exc))
            return candidates[0]

        # The reply must be *only* an id, as the prompt demands. Scanning for
        # any id anywhere in the text would let a model that restated the
        # request ("research competitors...") masquerade as a decision.
        answer = re.sub(r"[^a-z_]", "", completion.text.strip().lower())
        chosen = next((c for c in candidates if c.agent_id == answer), None)
        if chosen is None:
            log.debug("arbiter_unparsed", reply=completion.text[:80])
            return candidates[0]
        return AgentMatch(
            agent_id=chosen.agent_id,
            confidence=max(chosen.confidence, 0.6),
            reasons=[*chosen.reasons, "confirmed by arbiter"],
        )

    async def plan(self, request: str) -> list[AgentMatch]:
        """Decide which agents should handle a request, best first."""
        matches = self._registry.route(request)
        if self._use_arbiter and self._registry.is_ambiguous(matches) and len(matches) > 1:
            best = await self._arbitrate(request, matches)
            others = [m for m in matches if m.agent_id != best.agent_id]
            matches = [best, *others]
            self._bus.publish(
                "routing.arbitrated", {"chosen": best.agent_id, "request": request[:160]}
            )
        else:
            self._bus.publish(
                "routing.decided",
                {"chosen": matches[0].agent_id, "confidence": matches[0].confidence},
            )
        return matches

    @property
    def registry(self) -> AgentRegistry:
        """The catalog this orchestrator can reach.

        Public because a mode narrows by handing over a different one, and a
        caller that pins an agent must be able to ask whether *this*
        orchestrator has it — not whether the system does.
        """
        return self._registry

    def resolve(self, agent_id: str) -> AgentSpec:
        return self._registry.get(agent_id)

    async def handle(
        self,
        request: str,
        *,
        agent_id: str | None = None,
        history: list[Message] | None = None,
    ) -> AsyncIterator[AgentDelta]:
        """Route a request and stream the chosen agent's work."""
        if agent_id:
            matches = [AgentMatch(agent_id=agent_id, confidence=1.0, reasons=["explicit"])]
        else:
            matches = await self.plan(request)

        spec = self._registry.get(matches[0].agent_id)
        run = self._runs.create(request=request, agent_id=spec.id)
        run.routing = [m.model_dump() for m in matches]
        routing_step = self._runs.start_step(run, StepKind.AGENT, f"route → {spec.id}")
        self._runs.end_step(routing_step, confidence=matches[0].confidence)

        yield AgentDelta(
            "routing",
            data={
                "run_id": run.id,
                "chosen": spec.id,
                "candidates": [m.model_dump() for m in matches],
            },
        )
        async for delta in self._runtime.stream(spec, request, history=history, run=run):
            yield delta
