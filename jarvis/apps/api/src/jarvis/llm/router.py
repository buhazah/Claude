"""Model router: chooses *which* model runs a request, and what happens when it fails.

Two responsibilities:

1. **Selection.** Score every registered model against the request's policy on
   normalised quality / cost / latency, after eliminating models that cannot
   satisfy hard constraints (context window, privacy floor, modality, tools).
2. **Resilience.** Selection returns an ordered chain, not a single model. A
   failure walks down the chain, and repeated failures trip a per-provider
   circuit breaker so a dead provider stops costing latency on every request.

Cost and latency are normalised across the *candidate set*, not against
absolute constants, so the scoring stays meaningful as the catalog changes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import structlog

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.errors import (
    AllProvidersFailedError,
    ConfigurationError,
)
from jarvis.llm.base import (
    POLICY_WEIGHTS,
    Chunk,
    Completion,
    CompletionRequest,
    LLMProvider,
    ModelSpec,
    ToolCall,
    ToolSchema,
    Usage,
)
from jarvis.security.budget import BudgetExceededError, CostGovernor, Verdict
from jarvis.tools.approvals import ApprovalBroker, ApprovalState

log = structlog.get_logger(__name__)

CIRCUIT_THRESHOLD = 3  # consecutive failures before a provider is skipped
CIRCUIT_COOLDOWN_S = 60.0


@dataclass(slots=True)
class Candidate:
    model: ModelSpec
    score: float
    reasons: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class _Circuit:
    failures: int = 0
    opened_at: float | None = None

    def is_open(self, now: float) -> bool:
        if self.opened_at is None:
            return False
        if now - self.opened_at >= CIRCUIT_COOLDOWN_S:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def record_failure(self, now: float) -> None:
        self.failures += 1
        if self.failures >= CIRCUIT_THRESHOLD:
            self.opened_at = now

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None


def _normalise(value: float, low: float, high: float) -> float:
    """Map ``value`` into 0..1 across the observed range; 0.5 when degenerate."""
    if high <= low:
        return 0.5
    return (value - low) / (high - low)


class ModelRouter:
    """Selects models, streams completions, and survives provider failures."""

    def __init__(
        self,
        providers: list[LLMProvider],
        *,
        bus: EventBus | None = None,
        clock: Clock = SYSTEM_CLOCK,
        governor: CostGovernor | None = None,
        approvals: ApprovalBroker | None = None,
    ) -> None:
        if not providers:
            raise ConfigurationError("ModelRouter requires at least one provider")
        # Models are dispatched back to their provider by name, so a mismatch
        # here would surface as a KeyError mid-request. Fail at boot instead.
        for provider in providers:
            for model in provider.models():
                if model.provider != provider.name:
                    raise ConfigurationError(
                        f"provider '{provider.name}' offers model '{model.id}' "
                        f"declaring provider '{model.provider}'"
                    )
        self._providers = {p.name: p for p in providers}
        self._bus = bus
        self._clock = clock
        self._circuits: dict[str, _Circuit] = {p.name: _Circuit() for p in providers}
        # Cost is governed here rather than in the runtime because this is the
        # only place every call passes through — agents, workflows, documents,
        # voice and the routing arbiter all end up in `stream` or `complete`.
        self._governor = governor
        self._approvals = approvals

    @property
    def providers(self) -> dict[str, LLMProvider]:
        return dict(self._providers)

    def catalog(self) -> list[ModelSpec]:
        return [m for p in self._providers.values() for m in p.models()]

    def _available_models(self) -> list[ModelSpec]:
        now = self._clock.monotonic()
        out: list[ModelSpec] = []
        for name, provider in self._providers.items():
            if not provider.is_available() or self._circuits[name].is_open(now):
                continue
            out.extend(provider.models())
        return out

    def rank(self, request: CompletionRequest) -> list[Candidate]:
        """Return every eligible model, best first."""
        if request.model_id:
            pinned = [m for m in self._available_models() if m.id == request.model_id]
            if pinned:
                return [Candidate(pinned[0], 1.0, {"pinned": 1.0})]

        needed_context = request.token_estimate() + request.max_output_tokens
        eligible = [
            m
            for m in self._available_models()
            if m.context_window >= needed_context
            and m.privacy >= request.min_privacy
            and all(mod in m.modalities for mod in request.required_modalities)
            and (m.supports_tools or not request.needs_tools)
        ]
        if not eligible:
            return []

        costs = [m.input_cost_per_mtok + m.output_cost_per_mtok for m in eligible]
        low_cost, high_cost = min(costs), max(costs)
        w_quality, w_cost, w_latency = POLICY_WEIGHTS[request.policy]

        candidates: list[Candidate] = []
        for model in eligible:
            cost = model.input_cost_per_mtok + model.output_cost_per_mtok
            cheapness = 1.0 - _normalise(cost, low_cost, high_cost)
            score = w_quality * model.quality + w_cost * cheapness + w_latency * model.latency_score
            candidates.append(
                Candidate(
                    model,
                    round(score, 6),
                    {
                        "quality": round(w_quality * model.quality, 4),
                        "cost": round(w_cost * cheapness, 4),
                        "latency": round(w_latency * model.latency_score, 4),
                    },
                )
            )

        # Deterministic ties: score, then quality, then id.
        candidates.sort(key=lambda c: (-c.score, -c.model.quality, c.model.id))
        return candidates

    def select(self, request: CompletionRequest) -> ModelSpec:
        candidates = self.rank(request)
        if not candidates:
            raise AllProvidersFailedError("no model satisfies the request constraints", failures={})
        return candidates[0].model

    async def stream(
        self,
        request: CompletionRequest,
        *,
        tools: list[ToolSchema] | None = None,
        run_id: str | None = None,
        max_fallbacks: int = 2,
    ) -> AsyncIterator[Chunk]:
        """Stream a completion, walking the fallback chain on failure.

        Fallback only happens before the first token: once output has been
        emitted, silently restarting on another model would corrupt the stream,
        so the error propagates instead.
        """
        chain = self.rank(request)
        if not chain:
            raise AllProvidersFailedError("no model satisfies the request constraints", failures={})

        await self._authorise_spend(chain[0], request, run_id=run_id)

        failures: dict[str, str] = {}
        for attempt, candidate in enumerate(chain[: max_fallbacks + 1]):
            model = candidate.model
            provider = self._providers[model.provider]
            emitted = False
            if self._bus:
                self._bus.publish(
                    "llm.selected",
                    {
                        "model": model.id,
                        "provider": model.provider,
                        "policy": request.policy.value,
                        "score": candidate.score,
                        "attempt": attempt,
                    },
                    run_id=run_id,
                )
            try:
                async for chunk in provider.stream(request, model, tools):
                    chunk.model_id = model.id
                    emitted = emitted or bool(chunk.text)
                    if chunk.done and chunk.usage and self._governor:
                        # Actual spend, not the estimate the ceiling was
                        # checked against — the estimate is deliberately high.
                        self._governor.record(chunk.usage.cost_usd)
                    if chunk.done and chunk.usage and self._bus:
                        self._bus.publish(
                            "llm.completed",
                            {
                                "model": model.id,
                                "input_tokens": chunk.usage.input_tokens,
                                "output_tokens": chunk.usage.output_tokens,
                                "cost_usd": round(chunk.usage.cost_usd, 6),
                            },
                            run_id=run_id,
                        )
                    yield chunk
                self._circuits[model.provider].record_success()
                return
            except BudgetExceededError:
                # A refusal to spend is a decision, not a provider fault. Never
                # fall back on it — the next model costs money too.
                raise
            except Exception as exc:
                # Deliberately broad. `ProviderError` is what a well-behaved
                # adapter raises, but the whole point of a fallback chain is
                # that a provider failing for *any* reason degrades quality
                # instead of failing the request — and in production the
                # failure is as likely to be a connection reset or a JSON
                # decode error that some adapter forgot to wrap.
                # `CancelledError` derives from BaseException, so a client
                # hanging up still propagates rather than triggering a retry.
                self._circuits[model.provider].record_failure(self._clock.monotonic())
                failures[model.id] = str(exc)
                log.warning(
                    "provider_failed", provider=model.provider, model=model.id, error=str(exc)
                )
                if self._bus:
                    self._bus.publish(
                        "llm.failed",
                        {"model": model.id, "provider": model.provider, "error": str(exc)},
                        run_id=run_id,
                    )
                # Falling back mid-stream would splice two different voices
                # into one answer, so only pre-first-token failures fall back.
                if emitted:
                    raise
                continue

        # Carry the causes into the message: this string is what lands on the
        # run record and in front of the user.
        detail = "; ".join(f"{model}: {error}" for model, error in failures.items())
        raise AllProvidersFailedError(
            f"all {len(failures)} candidate models failed — {detail}", failures=failures
        )

    async def _authorise_spend(
        self, candidate: Candidate, request: CompletionRequest, *, run_id: str | None
    ) -> None:
        """Grade this call against the ceilings, before it is made.

        The estimate assumes the model emits its full output allowance. That
        over-states most calls, deliberately: a budget that under-estimates is
        a budget that gets exceeded, and the failure mode of being slightly too
        careful with someone's money is much better than the alternative.
        """
        if self._governor is None or not self._governor.enforced:
            return

        model = candidate.model
        estimate = model.cost_for(request.token_estimate(), request.max_output_tokens)
        assessment = self._governor.assess(estimate)
        if assessment.verdict is Verdict.ALLOW:
            return

        if self._bus:
            self._bus.publish("budget.exceeded", assessment.to_dict(), run_id=run_id)

        if assessment.verdict is Verdict.REFUSE:
            raise BudgetExceededError(
                assessment.reason, spent=assessment.spent, limit=assessment.limit
            )

        # Soft ceiling: the same gate that guards a dangerous tool. Without an
        # approver there is nobody to ask, and spending money unasked is not
        # the safe default.
        if self._approvals is None:
            raise BudgetExceededError(
                f"{assessment.reason}; no approver is configured",
                spent=assessment.spent,
                limit=assessment.limit,
            )
        approval = await self._approvals.request(
            tool="spend",
            arguments={"description": assessment.reason, **assessment.to_dict()},
            run_id=run_id,
        )
        if approval.state is not ApprovalState.APPROVED:
            raise BudgetExceededError(
                f"spending was {approval.state.value}: {assessment.reason}",
                spent=assessment.spent,
                limit=assessment.limit,
            )

    async def complete(
        self,
        request: CompletionRequest,
        *,
        tools: list[ToolSchema] | None = None,
        run_id: str | None = None,
    ) -> Completion:
        """Collect a full completion. Convenience over :meth:`stream`."""
        parts: list[str] = []
        tool_calls: list[ToolCall] = []
        usage = Usage()
        used_model = self.select(request).id
        async for chunk in self.stream(request, tools=tools, run_id=run_id):
            if chunk.model_id:
                used_model = chunk.model_id
            if chunk.text:
                parts.append(chunk.text)
            if chunk.tool_call:
                tool_calls.append(chunk.tool_call)
            if chunk.usage:
                usage = chunk.usage
        spec = next((m for m in self.catalog() if m.id == used_model), None)
        return Completion(
            text="".join(parts),
            model_id=used_model,
            provider=spec.provider if spec else "unknown",
            usage=usage,
            tool_calls=tool_calls,
        )
