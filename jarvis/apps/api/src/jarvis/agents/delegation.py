"""Handing work to specialists — the thing the prompts have been promising.

Audit finding F4: `AgentSpec.collaborators` was documented as "agents this one
commonly delegates to, used by the planner", and nothing read it. The Chief of
Staff's prompt said "you decide whether to answer it, decompose it, or hand it
to specialists"; the Planner's said each step "names an owner". Neither was
possible. `Orchestrator.handle` routed to exactly one agent, streamed exactly
that agent's output, and discarded the rest of the candidates.

So every multi-specialist request produced a *description* of the delegation
rather than the delegation, because describing it was the only thing available.
That is the largest gap between what the intelligence layer promises and what
the runtime does, and it is what separates "AI assistant" from "AI Chief of
Staff".

Four constraints shape the design, and each is a failure this would otherwise
have:

**Delegation is opt-in per agent, via `collaborators`.** The field finally
means something: an agent with no collaborators never delegates, so twenty-odd
specialists keep behaving exactly as they did and only the two agents whose
prompts promise coordination pay for it.

**One level. A delegate never delegates.** Without a depth limit this is a
recursion whose base case is the user's budget.

**Only agents in *this* registry.** A mode narrows by handing over a smaller
one (ADR 0010), and a delegator that reached for the full catalog would be a
hole straight through the narrowing — the same defect as the hardcoded routing
fallback in M9.

**It degrades to ordinary routing.** The decomposition is a model call, and
when there is no model — offline, or the provider is down — it returns nothing
parseable and the request runs as a single agent. Offline determinism is a
product requirement, not a test convenience (ADR 0001), and a feature that
turns the echo provider into an error is a feature that breaks the demo.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from jarvis.agents.registry import AgentRegistry
from jarvis.agents.spec import AgentSpec
from jarvis.llm.base import CompletionRequest, Message, Role, RoutingPolicy
from jarvis.llm.router import ModelRouter

log = structlog.get_logger(__name__)

# Enough to cover a genuinely multi-part request, few enough that a confused
# decomposition cannot fan out into a bill.
MAX_ASSIGNMENTS = 4
# Below this many words a request is one thing, whatever it looks like, and
# paying for a decomposition call to discover that is waste.
MIN_WORDS_TO_DECOMPOSE = 8

DECOMPOSE_PROMPT = (
    "You are the dispatcher inside Jarvis. Split the user's request into the "
    "fewest independent assignments that between them complete it, and give "
    "each to one specialist.\n\n"
    'Reply with ONLY a JSON array: [{"agent":"<id>","task":"<what they '
    'should do>"}]\n\n'
    "Rules:\n"
    "- Use ONLY the agent ids listed. Never invent one.\n"
    "- If one specialist could do the whole thing, reply []. That is the "
    "common case and is not a failure.\n"
    f"- At most {MAX_ASSIGNMENTS} assignments.\n"
    "- Each task must be self-contained: the specialist sees only its own "
    "task, not the original request or the other assignments."
)

SYNTHESIS_PROMPT = (
    "Your specialists have reported back. Write the single answer the user "
    "asked for.\n"
    "- Answer the original request. Do not narrate who did what.\n"
    "- Where they disagree, say so and pick.\n"
    "- Where a specialist could not finish, say what is missing."
)


@dataclass(frozen=True, slots=True)
class Assignment:
    agent_id: str
    task: str


@dataclass(frozen=True, slots=True)
class Contribution:
    agent_id: str
    task: str
    output: str
    cost_usd: float = 0.0
    error: str = ""


class Delegator:
    """Decides whether a request should be split, and into what."""

    def __init__(self, router: ModelRouter, *, max_assignments: int = MAX_ASSIGNMENTS) -> None:
        self._router = router
        self._max = max_assignments

    def should_consider(self, spec: AgentSpec, request: str) -> bool:
        """Whether it is worth paying for a decomposition call at all.

        Two cheap gates before any spend: the agent has to be one that
        coordinates, and the request has to be long enough to plausibly contain
        more than one thing. Both are crude, and both are free — which is the
        right trade against a model call on every message.
        """
        return bool(spec.collaborators) and len(request.split()) >= MIN_WORDS_TO_DECOMPOSE

    async def decompose(
        self, request: str, *, spec: AgentSpec, registry: AgentRegistry
    ) -> list[Assignment]:
        """Split a request, or return nothing and let one agent handle it."""
        # The agent's own collaborators first, then the rest of *this* registry
        # — narrowed by whatever mode is active, never the full catalog.
        reachable = [s for s in registry.all() if s.id != spec.id]
        preferred = [s for s in reachable if s.id in spec.collaborators]
        slate = preferred + [s for s in reachable if s.id not in spec.collaborators]
        if not slate:
            return []

        options = "\n".join(f"- {s.id}: {s.tagline}" for s in slate)
        prompt = f"Request: {request}\n\nSpecialists:\n{options}\n\nAssignments:"
        try:
            completion = await self._router.complete(
                CompletionRequest(
                    messages=[Message(role=Role.USER, content=prompt)],
                    system=DECOMPOSE_PROMPT,
                    policy=RoutingPolicy.FAST,
                    max_output_tokens=400,
                    temperature=0.0,
                )
            )
        except Exception as exc:
            log.warning("decompose_failed", error=str(exc))
            return []

        assignments = _parse(completion.text, known={s.id for s in slate})
        # One assignment is not a delegation — it is the same work with an
        # extra model call in front of it, so it is discarded rather than run.
        return assignments[: self._max] if len(assignments) > 1 else []

    async def synthesise(
        self,
        request: str,
        contributions: list[Contribution],
        *,
        spec: AgentSpec,
    ) -> str:
        """Turn what came back into the one answer the user asked for."""
        reports = "\n\n".join(
            f"### {c.agent_id} — {c.task}\n{c.error or c.output}" for c in contributions
        )
        completion = await self._router.complete(
            CompletionRequest(
                messages=[
                    Message(
                        role=Role.USER,
                        content=f"Original request: {request}\n\nReports:\n\n{reports}",
                    )
                ],
                system=f"{spec.system_prompt}\n\n{SYNTHESIS_PROMPT}",
                policy=spec.policy,
                min_privacy=spec.min_privacy,
                max_output_tokens=spec.max_output_tokens,
                temperature=spec.temperature,
            )
        )
        return completion.text.strip()


def _parse(text: str, *, known: set[str]) -> list[Assignment]:
    """Read the model's JSON, ignoring everything that is not an assignment.

    Tolerant of a fenced block and of prose either side, because models add
    both; intolerant of an unknown agent id, because routing work to an agent
    that does not exist fails later and more confusingly than refusing here.
    """
    candidate = text.strip()
    if fence := re.search(r"```(?:json)?\s*(.+?)```", candidate, re.DOTALL):
        candidate = fence.group(1).strip()
    if (start := candidate.find("[")) != -1 and (end := candidate.rfind("]")) > start:
        candidate = candidate[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []

    out: list[Assignment] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        agent = str(entry.get("agent", "")).strip()
        task = str(entry.get("task", "")).strip()
        if agent in known and task and not any(a.agent_id == agent for a in out):
            out.append(Assignment(agent_id=agent, task=task))
    return out
