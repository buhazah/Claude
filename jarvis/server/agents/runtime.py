"""Agent runtime: a ReAct-style reason/act/observe loop.

An agent receives a goal plus long-term memory context, then iterates:
think -> optionally emit a tool call (as JSON) -> observe the result ->
continue, until it emits a final answer or hits the step budget. Every
run is persisted as an AgentRun with its plan, steps, tokens, and cost.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db import AgentRun, utcnow
from ..integrations.context import reset_current_user, set_current_user
from ..llm.base import LLMError
from ..llm.router import RouteProfile, router
from ..tools.base import registry
from .definitions import AGENTS, AgentDef

log = logging.getLogger("jarvis.agents")

MAX_STEPS = 8

_TOOL_CALL_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class StepRecord:
    thought: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    observation: str = ""


def _tool_instructions(tool_names: list[str]) -> str:
    schemas = registry.schemas(tool_names)
    if not schemas:
        return "You have no tools available; answer from your own knowledge."
    listing = json.dumps(schemas, indent=2)
    return (
        "You have access to these tools:\n"
        f"{listing}\n\n"
        "To call a tool, respond with ONLY a fenced json block:\n"
        '```json\n{\"tool\": \"<name>\", \"args\": { ... }}\n```\n'
        "After you see the tool result you may call another tool or give your "
        "final answer. When you are done, respond with a fenced json block:\n"
        '```json\n{\"final\": \"<your complete answer to the user>\"}\n```\n'
        "Always think briefly in plain text before the json block."
    )


def _extract_action(text: str) -> dict | None:
    for match in _TOOL_CALL_RE.finditer(text):
        try:
            obj = json.loads(match.group(1))
            if isinstance(obj, dict) and ("tool" in obj or "final" in obj):
                return obj
        except json.JSONDecodeError:
            continue
    return None


@dataclass
class AgentResult:
    agent: str
    output: str
    steps: list[StepRecord]
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    error: str = ""


class Agent:
    def __init__(self, defn: AgentDef):
        self.defn = defn

    def _profile(self) -> RouteProfile:
        return RouteProfile(
            complexity=self.defn.complexity,
            min_context=self.defn.min_context,
            cost_sensitive=True,
        )

    def _build_messages(self, goal: str, memory_context: str, history: list[dict]) -> list[dict]:
        system = self.defn.system_prompt()
        if memory_context:
            system += "\n\n" + memory_context
        system += "\n\n" + _tool_instructions(self.defn.tools)
        messages = [{"role": "system", "content": system}]
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": goal})
        return messages

    async def run(
        self,
        session: AsyncSession,
        user_id: str,
        goal: str,
        memory_context: str = "",
        history: list[dict] | None = None,
        conversation_id: str | None = None,
        on_step: Callable[[StepRecord], None] | None = None,
    ) -> AgentResult:
        history = history or []
        messages = self._build_messages(goal, memory_context, history)
        run = AgentRun(
            user_id=user_id, conversation_id=conversation_id,
            agent=self.defn.key, goal=goal[:4000], status="running",
        )
        session.add(run)
        await session.commit()

        steps: list[StepRecord] = []
        tokens_in = tokens_out = 0
        cost = 0.0
        final = ""
        error = ""

        # Bind the user so account-connected tools (calendar/spotify/gmail)
        # act on this user's linked accounts.
        ctx_token = set_current_user(user_id)
        try:
            for _ in range(MAX_STEPS):
                resp = await router.complete(
                    messages, profile=self._profile(), max_tokens=2048,
                    temperature=self.defn.temperature,
                )
                tokens_in += resp.tokens_in
                tokens_out += resp.tokens_out
                cost += resp.cost_usd
                action = _extract_action(resp.text)
                thought = _TOOL_CALL_RE.sub("", resp.text).strip()

                if action is None:
                    # No structured action: treat the whole reply as the answer.
                    final = resp.text.strip()
                    steps.append(StepRecord(thought=thought or final))
                    break
                if "final" in action:
                    final = str(action["final"]).strip()
                    steps.append(StepRecord(thought=thought))
                    break

                tool_name = str(action.get("tool", ""))
                args = action.get("args", {}) or {}
                result = await registry.execute(tool_name, args)
                observation = result.output if result.ok else f"ERROR: {result.error}"
                step = StepRecord(thought=thought, tool=tool_name, args=args, observation=observation)
                steps.append(step)
                if on_step:
                    on_step(step)

                messages.append({"role": "assistant", "content": resp.text})
                messages.append(
                    {"role": "user", "content": f"Tool `{tool_name}` result:\n{observation[:6000]}"}
                )
            else:
                # Step budget exhausted — ask for a wrap-up answer.
                messages.append(
                    {"role": "user", "content": "Provide your best final answer now based on what you have."}
                )
                resp = await router.complete(
                    messages, profile=self._profile(), max_tokens=1500,
                    temperature=self.defn.temperature,
                )
                tokens_in += resp.tokens_in
                tokens_out += resp.tokens_out
                cost += resp.cost_usd
                final = _TOOL_CALL_RE.sub("", resp.text).strip()
        except LLMError as exc:
            error = str(exc)
            final = f"The {self.defn.name} could not complete the task: {exc}"
        finally:
            reset_current_user(ctx_token)

        run.status = "failed" if error else "success"
        run.plan = [s.thought for s in steps if s.thought]
        run.steps = [
            {"thought": s.thought, "tool": s.tool, "args": s.args, "observation": s.observation[:2000]}
            for s in steps
        ]
        run.output = final[:20000]
        run.error = error
        run.tokens_in = tokens_in
        run.tokens_out = tokens_out
        run.cost_usd = cost
        run.finished_at = utcnow()
        await session.commit()

        return AgentResult(
            agent=self.defn.key, output=final, steps=steps,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost, error=error,
        )


def get_agent(key: str) -> Agent:
    defn = AGENTS.get(key)
    if defn is None:
        raise KeyError(f"unknown agent '{key}'")
    return Agent(defn)
