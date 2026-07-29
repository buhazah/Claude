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
from jarvis.agents.spec import AgentMatch, AgentMetrics, AgentMetricsStore, AgentSpec, Capability
from jarvis.kernel.errors import NotFoundError

_WORD_RE = re.compile(r"[a-z0-9']+")

# Below this, stage one is not trusted and the orchestrator escalates.
# Raised from 0.35 after measuring against real models: one or two keyword
# hits scores 0.4-0.5, and every homonym failure sat in that band looking
# confident. Two hits is not evidence; it is a coincidence waiting to happen.
AMBIGUITY_THRESHOLD = 0.55

# How much one piece of evidence is worth *before* it is divided by how many
# agents claim it. An exclusive keyword is worth as much as a phrase, because
# it is as diagnostic as one; a keyword two agents share is worth half, which
# lands it under the threshold and escalates — the right answer, since two
# agents claiming a word is the definition of an ambiguous word.
KEYWORD_WEIGHT = 2.0
PHRASE_WEIGHT = 3.0
NAME_WEIGHT = 3.0


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


class AgentRegistry:
    """Holds specs and their live metrics; scores requests against them."""

    def __init__(self, specs: list[AgentSpec] | None = None) -> None:
        self._specs: dict[str, AgentSpec] = {}
        self._metrics: dict[str, AgentMetrics] = {}
        # Set by the composition root when a database is configured. Without
        # it, metrics are per-process and routing forgets its track record on
        # every restart — which it did from M1 until M10.
        self.store: AgentMetricsStore | None = None
        # How many agents *here* claim each keyword. Built lazily and thrown
        # away on register, because it is a property of the whole registry:
        # the same word is weak evidence in the full catalog and strong
        # evidence in a mode that narrowed away everyone else who claimed it.
        self._claims: dict[str, int] | None = None
        for spec in specs if specs is not None else CATALOG:
            self.register(spec)

    def register(self, spec: AgentSpec) -> None:
        self._specs[spec.id] = spec
        self._metrics.setdefault(spec.id, AgentMetrics())
        self._claims = None

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

    async def restore(self) -> int:
        """Reload each agent's track record, so routing keeps learning."""
        if self.store is None:
            return 0
        loaded = await self.store.load()
        for agent_id, metrics in loaded.items():
            if agent_id in self._specs:
                self._metrics[agent_id] = metrics
        return len(loaded)

    async def persist(self, agent_id: str) -> None:
        """Write one agent's metrics through. Called after each run."""
        if self.store is not None and agent_id in self._metrics:
            await self.store.save(agent_id, self._metrics[agent_id])

    def metrics(self, agent_id: str) -> AgentMetrics:
        self.get(agent_id)
        return self._metrics[agent_id]

    def by_capability(self, capability: Capability) -> list[AgentSpec]:
        return [s for s in self._specs.values() if capability in s.capabilities]

    def _claimants(self) -> dict[str, int]:
        """For each keyword, how many agents in this registry claim it.

        Two keywords are the same claim when either is a prefix of the other,
        because that is exactly what ``_score`` matches on: Research's
        ``market`` and Marketing's ``marketing`` are one contested word, not
        two independent ones.
        """
        if self._claims is not None:
            return self._claims
        singles = [
            (spec.id, k) for spec in self._specs.values() for k in spec.keywords if " " not in k
        ]
        claims: dict[str, int] = {}
        for spec in self._specs.values():
            for keyword in spec.keywords:
                if " " in keyword:
                    claims[keyword] = sum(1 for s in self._specs.values() if keyword in s.keywords)
                    continue
                owners = {
                    other
                    for other, word in singles
                    if word.startswith(keyword) or keyword.startswith(word)
                }
                claims[keyword] = len(owners)
        self._claims = claims
        return claims

    def _score(self, spec: AgentSpec, text: str, tokens: set[str]) -> tuple[float, list[str]]:
        """Score how much this request *distinguishes* this agent from the rest.

        Not how much text matched. Those are different quantities and only the
        second one is evidence: "calendar" is strong evidence for the Calendar
        Agent because nobody else claims it, while "post" is weak evidence for
        anyone because two agents do. Weighting by exclusivity is what lets the
        ambiguity threshold sit high enough to catch homonyms without
        escalating every precisely-worded request along with them.
        """
        reasons: list[str] = []
        hits = 0.0
        claims = self._claimants()

        for keyword in spec.keywords:
            shared = max(claims.get(keyword, 1), 1)
            if " " in keyword:
                if keyword in text:
                    hits += PHRASE_WEIGHT / shared
                    reasons.append(f"phrase '{keyword}'")
            elif any(token.startswith(keyword) for token in tokens):
                # Prefix matching so 'analyz' catches analyze/analyzing/analysis.
                hits += KEYWORD_WEIGHT / shared
                reasons.append(
                    f"keyword '{keyword}'" if shared == 1 else f"keyword '{keyword}' (shared)"
                )

        if spec.name.lower() in text:
            hits += NAME_WEIGHT
            reasons.append("named directly")

        # No capability bonus. Its value duplicated a keyword for fifteen of
        # thirty agents, so the same word scored twice — and only for agents
        # whose remit happens to be one English noun. Capabilities are the
        # vocabulary modes and permissions filter on, not one users speak.

        if hits == 0:
            return 0.0, reasons

        # Saturating curve. One exclusive keyword lands at 0.57 — just over the
        # threshold, so a precise match decides on its own; a keyword two
        # agents share lands at 0.40 and escalates. More evidence adds less and
        # less, which keeps a keyword-stuffed spec from out-shouting a
        # precisely-matched one.
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
            return [self._fallback()]
        return matches[:limit]

    def _fallback(self) -> AgentMatch:
        """Who owns a request nothing matched.

        Must come from *this* registry. A mode narrows by handing over a
        smaller catalog, so a hardcoded default id would be a hole straight
        through the narrowing: an unmatched request in coding mode would route
        to an agent coding mode deliberately excluded.
        """
        if DEFAULT_AGENT_ID in self._specs:
            return AgentMatch(
                agent_id=DEFAULT_AGENT_ID,
                confidence=0.2,
                reasons=["no specialist matched; chief of staff owns it"],
            )
        first = next(iter(self._specs))
        return AgentMatch(
            agent_id=first,
            confidence=0.15,
            reasons=["no specialist matched; the most general agent here owns it"],
        )

    def is_ambiguous(self, matches: list[AgentMatch]) -> bool:
        """True when stage one is not confident enough to decide alone."""
        if not matches:
            return True
        if matches[0].confidence < AMBIGUITY_THRESHOLD:
            return True
        # Two near-equal leaders means the request probably spans both.
        return len(matches) > 1 and (matches[0].confidence - matches[1].confidence) < 0.08
