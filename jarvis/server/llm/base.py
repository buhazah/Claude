"""Provider-agnostic LLM interface.

All providers speak a common message format:
    {"role": "system"|"user"|"assistant", "content": str}
and return an LLMResponse. Implementations are plain httpx calls so the
same code path works for every OpenAI-compatible host (Groq, OpenRouter,
DeepSeek, Ollama) plus Anthropic and Google native APIs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ModelSpec:
    """Catalog entry used by the router to score candidate models."""

    provider: str
    model: str
    context_window: int
    cost_in_per_mtok: float   # USD per million input tokens
    cost_out_per_mtok: float  # USD per million output tokens
    speed: int                # 1 (slow) .. 10 (fastest)
    quality: int              # 1 (basic) .. 10 (frontier reasoning)
    supports_tools: bool = True


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    raw: dict = field(default_factory=dict)


class LLMError(RuntimeError):
    """Raised when a provider call fails after retries."""


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def available(self) -> bool:
        return bool(self.api_key or self.base_url)

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        ...

    @staticmethod
    def split_system(messages: list[dict]) -> tuple[str, list[dict]]:
        """Extract the system prompt for APIs that take it separately."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [m for m in messages if m["role"] != "system"]
        return system, rest
