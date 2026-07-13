"""Master orchestrator.

Given a user request it: (1) recalls relevant memory, (2) decides whether
the request is simple (answer directly) or complex (decompose into a plan
of sub-tasks, each routed to a specialized agent), (3) executes sub-tasks
respecting dependencies, (4) synthesizes a final answer, and (5) reflects
by extracting new memories. It streams progress events for the UI.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from ..db import User
from ..llm.base import LLMError
from ..llm.router import RouteProfile, router
from ..memory.manager import memory_manager
from .definitions import AGENTS
from .runtime import get_agent

log = logging.getLogger("jarvis.orchestrator")

_LENGTH_DIRECTIVES = {
    "short": "Keep the response brief and to the point — a sentence or two, no preamble.",
    "medium": "Keep the response moderately concise — a short paragraph or a few bullets.",
    "long": "Give a thorough, detailed response with full explanation and examples.",
}


@dataclass
class SubTask:
    id: int
    agent: str
    instruction: str
    depends_on: list[int] = field(default_factory=list)
    result: str = ""
    status: str = "pending"


@dataclass
class Event:
    type: str  # plan|task_start|task_done|token|final|error|status
    data: dict


def _agent_catalog() -> str:
    return "\n".join(f"- {a.key}: {a.role}" for a in AGENTS.values())


# Instant keyword routing so everyday messages skip the extra "planning" LLM
# round-trip. Order matters — first match wins.
_ROUTE_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("debug", "traceback", "stack trace", "compile", "refactor", "function ", "def ",
      "python", "javascript", "typescript", "regex", "sql query"), "coding"),
    (("contract", "clause", "nda", "lawsuit", "legal ", "terms of service", "liability"), "legal"),
    (("budget", "revenue", "profit", "cash flow", "runway", "valuation", "unit economics"), "finance"),
    (("workout", "exercise routine", "training plan", "reps", "gym"), "fitness"),
    (("essay", "blog post", "article", "cover letter", "draft a"), "writing"),
    (("tweet", "instagram", "linkedin post", "caption", "hashtag"), "social"),
]


def _fast_route(request: str) -> str:
    """Pick a specialized agent by keyword, defaulting to the generalist assistant."""
    r = request.lower()
    for keys, agent in _ROUTE_HINTS:
        if any(k in r for k in keys):
            return agent
    return "assistant"


def _looks_simple(request: str) -> bool:
    """True when a request is clearly single-intent and needs no multi-agent plan."""
    r = request.strip()
    if len(r) > 320:
        return False
    lowered = r.lower()
    compound = (" and then ", "step by step", "after that", "\n- ", "\n1.", "\n2.",
                "then, ", "; then", "also, ", "as well as")
    if any(sig in lowered for sig in compound):
        return False
    # Several sentences usually means several intents — let the planner handle it.
    if r.count(". ") + r.count("? ") + r.count("! ") > 2:
        return False
    return True


def _parse_json_object(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class Orchestrator:
    async def _plan(self, user_id: str, request: str, memory_context: str) -> dict:
        """Decide simple vs complex and, if complex, produce a task graph."""
        prompt = (
            "You are the master orchestrator of JARVIS. Decide how to handle the user's "
            "request. Available specialized agents:\n"
            f"{_agent_catalog()}\n\n"
            f"{memory_context}\n\n"
            f'USER REQUEST: \"\"\"{request}\"\"\"\n\n'
            "Respond with STRICT JSON only:\n"
            "{\n"
            '  \"mode\": \"simple\" | \"complex\",\n'
            '  \"agent\": \"<agent key for simple mode, or the best single agent>\",\n'
            '  \"reason\": \"<one sentence>\",\n'
            '  \"tasks\": [ {\"id\": 1, \"agent\": \"<key>\", \"instruction\": \"<what to do>\", '
            '\"depends_on\": [<ids>]} ]\n'
            "}\n"
            "Use \"simple\" for anything one agent can answer in a single pass (most chat). "
            "Use \"complex\" only when the request genuinely needs multiple specialized agents "
            "or sequential steps. For simple mode, tasks may be an empty list."
        )
        try:
            resp = await router.complete(
                [{"role": "user", "content": prompt}],
                profile=RouteProfile(complexity=7, latency_sensitive=True),
                max_tokens=1200, temperature=0.2,
            )
        except LLMError as exc:
            return {"mode": "simple", "agent": "assistant", "reason": f"planner unavailable: {exc}", "tasks": []}
        plan = _parse_json_object(resp.text) or {}
        if plan.get("mode") not in {"simple", "complex"}:
            plan["mode"] = "simple"
        if plan.get("agent") not in AGENTS:
            plan["agent"] = "assistant"
        return plan

    async def _synthesize(self, request: str, subtasks: list[SubTask], memory_context: str) -> str:
        digest = "\n\n".join(
            f"[{t.agent}] {t.instruction}\nResult: {t.result}" for t in subtasks
        )
        prompt = (
            "You are JARVIS. Synthesize the specialized agents' results into one cohesive, "
            "direct answer to the user. Do not mention the agents or the orchestration; "
            "speak as a single assistant.\n\n"
            f"{memory_context}\n\nUSER REQUEST: {request}\n\nAGENT RESULTS:\n{digest}"
        )
        resp = await router.complete(
            [{"role": "user", "content": prompt}],
            profile=RouteProfile(complexity=7), max_tokens=2000, temperature=0.5,
        )
        return resp.text.strip()

    async def handle(
        self,
        session: AsyncSession,
        user_id: str,
        request: str,
        history: list[dict] | None = None,
        conversation_id: str | None = None,
        forced_agent: str | None = None,
    ) -> AsyncIterator[Event]:
        history = history or []
        memory_context = await memory_manager.context_block(session, user_id, request)

        # Always answer in the user's chosen response language (default English),
        # regardless of the language they typed/spoke in — so the reply and the
        # spoken voice are consistently in that language.
        user = await session.get(User, user_id)
        prefs = (user.preferences or {}) if user else {}
        lang = prefs.get("response_language") or "English"
        directive = (
            f"CRITICAL: Write your entire response to the user in {lang}, "
            "regardless of the language they use. Keep code and proper nouns as-is."
        )
        length = (prefs.get("response_length") or "").lower()
        if length in _LENGTH_DIRECTIVES:
            directive += "\n" + _LENGTH_DIRECTIVES[length]
        memory_context = directive + ("\n\n" + memory_context if memory_context else "")

        if forced_agent and forced_agent in AGENTS:
            plan = {"mode": "simple", "agent": forced_agent, "reason": "user-selected agent", "tasks": []}
        elif _looks_simple(request):
            # Skip the planning round-trip for everyday messages — answer directly.
            plan = {"mode": "simple", "agent": _fast_route(request),
                    "reason": "fast-routed (simple request)", "tasks": []}
        else:
            yield Event("status", {"message": "Thinking about how to approach this…"})
            plan = await self._plan(user_id, request, memory_context)

        yield Event("plan", plan)

        # ---- Simple mode: single agent answers directly ----------------
        if plan["mode"] == "simple" or not plan.get("tasks"):
            agent = get_agent(plan["agent"])
            yield Event("task_start", {"agent": agent.defn.key, "instruction": request})
            result = await agent.run(
                session, user_id, request, memory_context=memory_context,
                history=history, conversation_id=conversation_id,
            )
            yield Event("task_done", {"agent": agent.defn.key, "result": result.output})
            final = result.output
            yield Event("final", {"text": final, "agent": agent.defn.key,
                                  "cost_usd": result.cost_usd})
            await self._post_reflect(session, user_id, request, final)
            return

        # ---- Complex mode: execute the task graph ----------------------
        subtasks = [
            SubTask(
                id=int(t.get("id", i + 1)),
                agent=t["agent"] if t.get("agent") in AGENTS else "assistant",
                instruction=str(t.get("instruction", "")),
                depends_on=[int(d) for d in t.get("depends_on", [])],
            )
            for i, t in enumerate(plan["tasks"])
        ]
        by_id = {t.id: t for t in subtasks}
        done: set[int] = set()

        # Execute in dependency order; guard against cycles with a bounded loop.
        for _ in range(len(subtasks) + 1):
            progressed = False
            for task in subtasks:
                if task.status != "pending":
                    continue
                if not all(dep in done for dep in task.depends_on):
                    continue
                context = "\n\n".join(
                    f"Result from prior step ({by_id[d].agent}): {by_id[d].result}"
                    for d in task.depends_on if d in by_id
                )
                instruction = task.instruction
                if context:
                    instruction += f"\n\nUse these prior results:\n{context}"
                yield Event("task_start", {"id": task.id, "agent": task.agent,
                                          "instruction": task.instruction})
                agent = get_agent(task.agent)
                result = await agent.run(
                    session, user_id, instruction, memory_context=memory_context,
                    conversation_id=conversation_id,
                )
                task.result = result.output
                task.status = "done"
                done.add(task.id)
                progressed = True
                yield Event("task_done", {"id": task.id, "agent": task.agent,
                                         "result": result.output})
            if len(done) == len(subtasks):
                break
            if not progressed:
                # Unsatisfiable dependency (e.g. cycle) — run the rest anyway.
                for task in subtasks:
                    if task.status == "pending":
                        agent = get_agent(task.agent)
                        result = await agent.run(
                            session, user_id, task.instruction,
                            memory_context=memory_context, conversation_id=conversation_id,
                        )
                        task.result = result.output
                        task.status = "done"
                        done.add(task.id)
                        yield Event("task_done", {"id": task.id, "agent": task.agent,
                                                 "result": result.output})
                break

        yield Event("status", {"message": "Synthesizing the final answer…"})
        try:
            final = await self._synthesize(request, subtasks, memory_context)
        except LLMError as exc:
            final = "\n\n".join(f"**{t.agent}**: {t.result}" for t in subtasks)
            yield Event("error", {"message": f"synthesis fell back to concatenation: {exc}"})
        yield Event("final", {"text": final, "agent": "orchestrator"})
        await self._post_reflect(session, user_id, request, final)

    async def _post_reflect(self, session: AsyncSession, user_id: str, request: str, answer: str) -> None:
        """Extract durable memories from the exchange (best-effort)."""
        try:
            await memory_manager.extract_from_exchange(session, user_id, request, answer)
        except Exception as exc:  # never fail the response on memory extraction
            log.warning("memory extraction failed: %s", exc)


orchestrator = Orchestrator()
