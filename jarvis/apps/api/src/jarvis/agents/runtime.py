"""The agent runtime: one execution path for every agent in the catalog.

Executing an agent means: recall relevant memory, assemble a context window,
stream from the routed model, record what happened, and learn from it. All of
that is spec-driven, so a new agent inherits streaming, metrics, memory,
cost accounting and observability for free.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from jarvis.agents.spec import AgentSpec
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.errors import ApprovalRequiredError, PermissionDeniedError
from jarvis.llm.base import CompletionRequest, Message, Role, ToolCall
from jarvis.llm.router import ModelRouter
from jarvis.memory.models import MemoryKind
from jarvis.memory.store import MemoryStore
from jarvis.runs.models import Run, RunState, RunStore, StepKind
from jarvis.tools.registry import ToolRegistry

if TYPE_CHECKING:  # imported for typing only; runtime import would be a cycle
    from jarvis.agents.registry import AgentRegistry

log = structlog.get_logger(__name__)

MEMORY_RECALL_LIMIT = 6
# How many model→tool→model rounds one request may take before Jarvis stops.
MAX_TOOL_ITERATIONS = 6


@dataclass(slots=True)
class AgentDelta:
    """One increment of agent output, as streamed to the client."""

    type: str  # "routing" | "context" | "token" | "tool" | "done" | "error"
    text: str = ""
    data: dict[str, object] | None = None


class AgentRuntime:
    """Executes any :class:`AgentSpec`."""

    def __init__(
        self,
        *,
        router: ModelRouter,
        registry: AgentRegistry,
        memory: MemoryStore,
        runs: RunStore,
        tools: ToolRegistry,
        bus: EventBus,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._router = router
        self._registry = registry
        self._memory = memory
        self._runs = runs
        self._tools = tools
        self._bus = bus
        self._clock = clock

    async def _build_context(self, spec: AgentSpec, request: str, run: Run) -> str | None:
        """Recall memory relevant to this request, scoped to the agent."""
        step = self._runs.start_step(run, StepKind.MEMORY, "recall")
        recalls = await self._memory.search(request, limit=MEMORY_RECALL_LIMIT, scope=spec.id)
        self._runs.end_step(step, hits=len(recalls))
        if not recalls:
            return None
        lines = [f"- [{r.memory.kind.value}] {r.memory.content}" for r in recalls]
        return "What you already know about the user and their work:\n" + "\n".join(lines)

    async def _invoke_tool(self, spec: AgentSpec, call: ToolCall, run: Run) -> tuple[str, bool]:
        """Run one tool call, returning ``(text_for_the_model, succeeded)``.

        Failures are *returned*, not raised. A denied permission or a broken
        tool is information the model can act on — it can apologise, try a
        different approach, or ask the user — whereas an exception here would
        discard a half-finished answer the user is already reading.
        """
        step = self._runs.start_step(run, StepKind.TOOL, call.name, arguments=call.arguments)
        try:
            result = await self._tools.invoke(
                call.name, call.arguments, run_id=run.id, agent_id=spec.id
            )
        except (PermissionDeniedError, ApprovalRequiredError) as exc:
            self._runs.end_step(step, state=RunState.FAILED, error=str(exc))
            return f"Refused: {exc}", False
        except Exception as exc:
            self._runs.end_step(step, state=RunState.FAILED, error=str(exc))
            log.warning("tool_failed", tool=call.name, error=str(exc))
            return f"Tool '{call.name}' failed: {exc}", False

        text = result if isinstance(result, str) else json.dumps(result, default=str)
        self._runs.end_step(step, result_preview=text[:200])
        return text, True

    async def stream(
        self,
        spec: AgentSpec,
        request: str,
        *,
        history: list[Message] | None = None,
        run: Run | None = None,
        remember: bool = True,
    ) -> AsyncIterator[AgentDelta]:
        """Run an agent, streaming deltas and recording the run."""
        run = run or self._runs.create(request=request, agent_id=spec.id)
        run.state = RunState.RUNNING
        started = self._clock.monotonic()
        self._bus.publish(
            "agent.started", {"agent": spec.id, "request": request[:200]}, run_id=run.id
        )

        context = await self._build_context(spec, request, run)
        if context:
            yield AgentDelta("context", data={"memories": context.count("\n- ") + 1})

        messages = list(history or [])
        messages.append(Message(role=Role.USER, content=request))
        system = spec.system_prompt if not context else f"{spec.system_prompt}\n\n{context}"

        tool_schemas = self._tools.schemas_for(spec.tools)
        parts: list[str] = []
        cost, tokens = 0.0, 0
        step = None

        # The agentic loop. A model that asks for a tool gets the result back
        # and another turn, until it stops asking or hits the ceiling. The
        # ceiling is not a safety feature — the permission wall is — it stops a
        # confused model from looping forever on the user's budget.
        try:
            for iteration in range(MAX_TOOL_ITERATIONS):
                completion = CompletionRequest(
                    messages=messages,
                    system=system,
                    policy=spec.policy,
                    min_privacy=spec.min_privacy,
                    max_output_tokens=spec.max_output_tokens,
                    temperature=spec.temperature,
                    needs_tools=bool(spec.tools),
                )
                label = f"{spec.id} completion" + (f" ({iteration + 1})" if iteration else "")
                step = self._runs.start_step(run, StepKind.MODEL, label)

                turn_text: list[str] = []
                requested: list[ToolCall] = []
                # Per-turn, because a step's cost is its own; the run totals
                # them. Writing cumulative figures onto every step would count
                # the first turn once per later turn.
                turn_cost, turn_tokens = 0.0, 0
                async for chunk in self._router.stream(
                    completion, tools=tool_schemas or None, run_id=run.id
                ):
                    if chunk.text:
                        turn_text.append(chunk.text)
                        parts.append(chunk.text)
                        self._bus.publish(
                            "agent.delta", {"agent": spec.id, "text": chunk.text}, run_id=run.id
                        )
                        yield AgentDelta("token", text=chunk.text)
                    if chunk.tool_call:
                        requested.append(chunk.tool_call)
                    if chunk.usage:
                        turn_cost = chunk.usage.cost_usd
                        turn_tokens = chunk.usage.input_tokens + chunk.usage.output_tokens
                    if chunk.done and chunk.model_id:
                        step.detail["model"] = chunk.model_id

                cost += turn_cost
                tokens += turn_tokens
                self._runs.end_step(step, cost_usd=turn_cost, tokens=turn_tokens)
                if not requested:
                    break

                # Record what the model asked for, so the next request replays
                # the exchange in the shape the provider expects.
                messages.append(
                    Message(
                        role=Role.ASSISTANT,
                        content="".join(turn_text),
                        tool_calls=requested,
                    )
                )

                for call in requested:
                    yield AgentDelta("tool", data={"name": call.name, "arguments": call.arguments})
                    result, ok = await self._invoke_tool(spec, call, run)
                    yield AgentDelta(
                        "tool_result",
                        data={"name": call.name, "ok": ok, "result": result[:400]},
                    )
                    messages.append(Message(role=Role.TOOL, content=result, tool_call_id=call.id))
            else:
                # Loop exhausted rather than broke: the model never stopped
                # asking. Say so instead of returning a silently truncated answer.
                parts.append(
                    f"\n\n[stopped after {MAX_TOOL_ITERATIONS} tool rounds without "
                    "reaching an answer]"
                )
        except Exception as exc:
            if step is not None:
                self._runs.end_step(step, state=RunState.FAILED, error=str(exc))
            self._runs.finish(run, state=RunState.FAILED, error=str(exc))
            await self._runs.persist(run)
            latency_ms = (self._clock.monotonic() - started) * 1000
            self._registry.metrics(spec.id).record(
                ok=False, latency_ms=latency_ms, cost_usd=cost, tokens=tokens
            )
            self._bus.publish("agent.failed", {"agent": spec.id, "error": str(exc)}, run_id=run.id)
            yield AgentDelta("error", text=str(exc))
            return

        output = "".join(parts).strip()
        self._runs.finish(run, state=RunState.SUCCEEDED, output=output)
        await self._runs.persist(run)

        latency_ms = (self._clock.monotonic() - started) * 1000
        self._registry.metrics(spec.id).record(
            ok=True, latency_ms=latency_ms, cost_usd=cost, tokens=tokens
        )

        if remember and output:
            await self._memory.remember(
                f"Asked: {request}\nAnswered ({spec.name}): {output[:600]}",
                kind=MemoryKind.CONVERSATION,
                scope=spec.id,
                source=f"run:{run.id}",
            )

        self._bus.publish(
            "agent.completed",
            {
                "agent": spec.id,
                "run_id": run.id,
                "cost_usd": round(cost, 6),
                "tokens": tokens,
                "latency_ms": round(latency_ms, 1),
            },
            run_id=run.id,
        )
        yield AgentDelta(
            "done",
            data={
                "run_id": run.id,
                "agent": spec.id,
                "cost_usd": round(cost, 6),
                "tokens": tokens,
                "latency_ms": round(latency_ms, 1),
            },
        )

    async def run(
        self, spec: AgentSpec, request: str, *, history: list[Message] | None = None
    ) -> Run:
        """Execute to completion and return the run record."""
        run = self._runs.create(request=request, agent_id=spec.id)
        async for _ in self.stream(spec, request, history=history, run=run):
            pass
        return run
