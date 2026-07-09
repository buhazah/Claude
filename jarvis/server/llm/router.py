"""Model catalog and intelligent routing.

The router scores every model from every *configured* provider against the
request profile (task complexity, needed context, latency sensitivity,
cost sensitivity) and picks the best fit. Fallback walks the ranked list
so a provider outage degrades gracefully instead of failing the request.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AsyncIterator

from ..config import settings
from .base import LLMError, LLMProvider, LLMResponse, ModelSpec
from .providers import AnthropicProvider, GoogleProvider, OpenAICompatibleProvider

log = logging.getLogger("jarvis.llm")

# Catalog of routable models. Costs are USD per million tokens.
CATALOG: list[ModelSpec] = [
    # Anthropic
    ModelSpec("anthropic", "claude-fable-5", 200_000, 15.0, 75.0, 4, 10),
    ModelSpec("anthropic", "claude-opus-4-8", 200_000, 15.0, 75.0, 5, 9),
    ModelSpec("anthropic", "claude-sonnet-5", 200_000, 3.0, 15.0, 7, 8),
    ModelSpec("anthropic", "claude-haiku-4-5-20251001", 200_000, 0.8, 4.0, 9, 6),
    # OpenAI
    ModelSpec("openai", "gpt-4o", 128_000, 2.5, 10.0, 7, 8),
    ModelSpec("openai", "gpt-4o-mini", 128_000, 0.15, 0.6, 9, 5),
    # Google
    ModelSpec("google", "gemini-2.0-flash", 1_000_000, 0.1, 0.4, 9, 6),
    ModelSpec("google", "gemini-1.5-pro", 2_000_000, 1.25, 5.0, 6, 8),
    # Groq (hosted open models, extremely fast)
    ModelSpec("groq", "llama-3.3-70b-versatile", 128_000, 0.59, 0.79, 10, 6),
    # DeepSeek
    ModelSpec("deepseek", "deepseek-chat", 64_000, 0.27, 1.1, 6, 7),
    ModelSpec("deepseek", "deepseek-reasoner", 64_000, 0.55, 2.19, 3, 8),
    # OpenRouter (meta-provider; useful as universal fallback)
    ModelSpec("openrouter", "anthropic/claude-sonnet-5", 200_000, 3.0, 15.0, 6, 8),
    ModelSpec("openrouter", "openai/gpt-4o-mini", 128_000, 0.15, 0.6, 8, 5),
    # Ollama local models — free, availability depends on what's pulled
    ModelSpec("ollama", "llama3.1", 128_000, 0.0, 0.0, 5, 4),
    ModelSpec("ollama", "qwen2.5", 128_000, 0.0, 0.0, 5, 4),
]


@dataclass
class RouteProfile:
    """What this request needs from a model."""

    complexity: int = 5          # 1 trivial .. 10 frontier reasoning
    min_context: int = 8_000     # tokens the conversation needs
    latency_sensitive: bool = False
    cost_sensitive: bool = True


class ModelRouter:
    def __init__(self):
        self.providers: dict[str, LLMProvider] = {}
        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
        if settings.openai_api_key:
            self.providers["openai"] = OpenAICompatibleProvider(settings.openai_api_key)
        if settings.google_api_key:
            self.providers["google"] = GoogleProvider(settings.google_api_key)
        if settings.groq_api_key:
            self.providers["groq"] = OpenAICompatibleProvider(
                settings.groq_api_key, "https://api.groq.com/openai/v1", name="groq"
            )
        if settings.deepseek_api_key:
            self.providers["deepseek"] = OpenAICompatibleProvider(
                settings.deepseek_api_key, "https://api.deepseek.com/v1", name="deepseek"
            )
        if settings.openrouter_api_key:
            self.providers["openrouter"] = OpenAICompatibleProvider(
                settings.openrouter_api_key, "https://openrouter.ai/api/v1", name="openrouter"
            )
        if settings.ollama_base_url:
            self.providers["ollama"] = OpenAICompatibleProvider(
                "", f"{settings.ollama_base_url.rstrip('/')}/v1", name="ollama"
            )

    @property
    def available(self) -> bool:
        return bool(self.providers)

    def candidates(self, profile: RouteProfile) -> list[ModelSpec]:
        """Rank configured models for this request profile, best first."""
        pool = [
            spec
            for spec in CATALOG
            if spec.provider in self.providers and spec.context_window >= profile.min_context
        ]

        def score(spec: ModelSpec) -> float:
            s = 0.0
            # Quality must clear the complexity bar; excess quality is mild waste.
            if spec.quality >= profile.complexity:
                s += 50 + (10 - (spec.quality - profile.complexity)) * 2
            else:
                s -= (profile.complexity - spec.quality) * 15
            if profile.latency_sensitive:
                s += spec.speed * 4
            if profile.cost_sensitive:
                blended = spec.cost_in_per_mtok * 0.7 + spec.cost_out_per_mtok * 0.3
                s += max(0.0, 20 - blended)
            return s

        return sorted(pool, key=score, reverse=True)

    def estimate_cost(self, spec: ModelSpec, tokens_in: int, tokens_out: int) -> float:
        return (
            tokens_in * spec.cost_in_per_mtok + tokens_out * spec.cost_out_per_mtok
        ) / 1_000_000

    async def complete(
        self,
        messages: list[dict],
        profile: RouteProfile | None = None,
        model_override: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse:
        profile = profile or RouteProfile()
        ranked = self._resolve(profile, model_override)
        errors: list[str] = []
        for spec in ranked:
            provider = self.providers[spec.provider]
            try:
                resp = await provider.complete(messages, spec.model, max_tokens, temperature)
                resp.cost_usd = self.estimate_cost(spec, resp.tokens_in, resp.tokens_out)
                return resp
            except LLMError as exc:
                log.warning("model %s/%s failed, trying next: %s", spec.provider, spec.model, exc)
                errors.append(f"{spec.provider}/{spec.model}: {exc}")
        raise LLMError(
            "All candidate models failed. Configure at least one provider API key. "
            f"Errors: {'; '.join(errors) or 'no providers configured'}"
        )

    async def stream(
        self,
        messages: list[dict],
        profile: RouteProfile | None = None,
        model_override: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        profile = profile or RouteProfile()
        ranked = self._resolve(profile, model_override)
        errors: list[str] = []
        for spec in ranked:
            provider = self.providers[spec.provider]
            try:
                async for chunk in provider.stream(messages, spec.model, max_tokens, temperature):
                    yield chunk
                return
            except LLMError as exc:
                log.warning("stream %s/%s failed, trying next: %s", spec.provider, spec.model, exc)
                errors.append(f"{spec.provider}/{spec.model}: {exc}")
        raise LLMError(
            f"All candidate models failed for streaming: {'; '.join(errors) or 'none configured'}"
        )

    def _resolve(self, profile: RouteProfile, model_override: str | None) -> list[ModelSpec]:
        if model_override:
            pinned = [s for s in CATALOG if s.model == model_override and s.provider in self.providers]
            if pinned:
                return pinned
        ranked = self.candidates(profile)
        if not ranked:
            raise LLMError(
                "No LLM provider is configured. Set ANTHROPIC_API_KEY (or another provider key) "
                "in the environment — see docs/ENVIRONMENT.md."
            )
        return ranked


router = ModelRouter()
