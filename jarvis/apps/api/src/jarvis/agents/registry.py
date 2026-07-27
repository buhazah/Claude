"""Agent registry and the lexical stage of the routing funnel.

Routing is two-stage by design. Stage one — here — is a cheap, deterministic
score over keywords, capabilities and past performance. It costs nothing, is
unit-testable, and is correct for the large majority of requests. Stage two
(``orchestrator``) only pays for an LLM arbiter when stage one is ambiguous,
which is the difference between a router that is free and one that adds a
model call to every single message.
"""

from __future__ import annotations

import re

from jarvis.agents.catalog import CATALOG, DEFAULT_AGENT_ID
from jarvis.agents.spec import AgentMatch, AgentMetrics, AgentSpec, Capability
from jarvis.kernel.errors import NotFoundError

_WORD_RE = re.compile(r"[a-z0-9']+")

# Below this, stage one is not trusted and the orchestrator escalates.
AMBIGUITY_THRESHOLD = 0.35


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


class AgentRegistry:
    """Holds specs and their live metrics; scores requests against them."""

    def __init__(self, specs: list[AgentSpec] | None = None) -> None:
        self._specs: dict[str, AgentSpec] = {}
        self._metrics: dict[str, AgentMetrics] = {}
        for spec in specs if specs is not None else CATALOG:
            self.register(spec)

    def register(self, spec: AgentSpec) -> None:
        self._specs[spec.id] = spec
        self._metrics.setdefault(spec.id, AgentMetrics())

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, agent_id: object) -> bool:
        return agent_id in self._specs

    def all(self) -> list[AgentSpec]:
        return list(self._specs.values())

    def get(self, agent_id: str) -> AgentSpec:
        try:
            return self._specs[agent_id]
        except KeyError:
            raise NotFoundError(f"unknown agent: {agent_id}") from None

    def metrics(self, agent_id: str) -> AgentMetrics:
        self.get(agent_id)
        return self._metrics[agent_id]

    def by_capability(self, capability: Capability) -> list[AgentSpec]:
        return [s for s in self._specs.values() if capability in s.capabilities]

    def _score(self, spec: AgentSpec, text: str, tokens: set[str]) -> tuple[float, list[str]]:
        reasons: list[str] = []
        hits = 0.0

        for keyword in spec.keywords:
            if " " in keyword:
                # Phrases are strong signals: they rarely collide across agents.
                if keyword in text:
                    hits += 2.0
                    reasons.append(f"phrase '{keyword}'")
            elif any(token.startswith(keyword) for token in tokens):
                # Prefix matching so 'analyz' catches analyze/analyzing/analysis.
                hits += 1.0
                reasons.append(f"keyword '{keyword}'")

        if spec.name.lower() in text:
            hits += 3.0
            reasons.append("named directly")

        for capability in spec.capabilities:
            if capability.value in tokens:
                hits += 0.5
                reasons.append(f"capability '{capability.value}'")

        if hits == 0:
            return 0.0, reasons

        # Saturating curve: three good hits ≈ 0.75, more adds little. Keeps a
        # keyword-stuffed spec from dominating a precisely-matched one.
        base = hits / (hits + 1.5)

        metrics = self._metrics[spec.id]
        if metrics.runs >= 3:
            # Nudge by track record, never enough to overturn a clear match.
            base *= 0.9 + 0.2 * metrics.success_rate
            reasons.append(f"success rate {metrics.success_rate:.0%}")

        return min(base, 0.99), reasons

    def route(self, request: str, *, limit: int = 3) -> list[AgentMatch]:
        """Score every agent against a natural-language request, best first."""
        text = request.lower()
        tokens = set(_tokens(text))
        matches: list[AgentMatch] = []
        for spec in self._specs.values():
            score, reasons = self._score(spec, text, tokens)
            if score > 0:
                matches.append(
                    AgentMatch(agent_id=spec.id, confidence=round(score, 4), reasons=reasons[:4])
                )

        matches.sort(key=lambda m: (-m.confidence, m.agent_id))
        if not matches:
            return [
                AgentMatch(
                    agent_id=DEFAULT_AGENT_ID,
                    confidence=0.2,
                    reasons=["no specialist matched; chief of staff owns it"],
                )
            ]
        return matches[:limit]

    def is_ambiguous(self, matches: list[AgentMatch]) -> bool:
        """True when stage one is not confident enough to decide alone."""
        if not matches:
            return True
        if matches[0].confidence < AMBIGUITY_THRESHOLD:
            return True
        # Two near-equal leaders means the request probably spans both.
        return len(matches) > 1 and (matches[0].confidence - matches[1].confidence) < 0.08
