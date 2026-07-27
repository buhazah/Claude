"""Anthropic adapter (Messages API, streaming).

Talks HTTP directly rather than pulling the vendor SDK: the surface we use is
small, and owning it keeps the adapter's failure modes explicit — which is
what the router's circuit breaker reasons about.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from jarvis.kernel.errors import ProviderError, ProviderUnavailableError
from jarvis.llm.base import (
    Chunk,
    CompletionRequest,
    Modality,
    ModelSpec,
    Privacy,
    Role,
    ToolSchema,
    Usage,
)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

MODELS = [
    ModelSpec(
        id="claude-opus-5",
        provider="anthropic",
        context_window=200_000,
        max_output=32_000,
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=25.0,
        quality=0.98,
        latency_score=0.55,
        privacy=Privacy.TRUSTED_CLOUD,
        modalities=(Modality.TEXT, Modality.VISION),
    ),
    ModelSpec(
        id="claude-sonnet-5",
        provider="anthropic",
        context_window=200_000,
        max_output=16_000,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=15.0,
        quality=0.92,
        latency_score=0.75,
        privacy=Privacy.TRUSTED_CLOUD,
        modalities=(Modality.TEXT, Modality.VISION),
    ),
    ModelSpec(
        id="claude-haiku-4-5-20251001",
        provider="anthropic",
        context_window=200_000,
        max_output=8_192,
        input_cost_per_mtok=0.8,
        output_cost_per_mtok=4.0,
        quality=0.80,
        latency_score=0.95,
        privacy=Privacy.TRUSTED_CLOUD,
        modalities=(Modality.TEXT, Modality.VISION),
    ),
]


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None, *, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client

    def models(self) -> list[ModelSpec]:
        return list(MODELS)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _payload(
        self, request: CompletionRequest, model: ModelSpec, tools: list[ToolSchema] | None
    ) -> dict[str, Any]:
        messages = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role is not Role.SYSTEM
        ]
        payload: dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "max_tokens": min(request.max_output_tokens, model.max_output),
            "temperature": request.temperature,
            "stream": True,
        }
        if request.system:
            payload["system"] = request.system
        if tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters or {"type": "object", "properties": {}},
                }
                for t in tools
            ]
        return payload

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        if not self._api_key:
            raise ProviderUnavailableError("ANTHROPIC_API_KEY is not set", provider=self.name)

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        owns_client = self._client is None
        usage = Usage()
        try:
            async with client.stream(
                "POST", API_URL, headers=headers, json=self._payload(request, model, tools)
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")[:500]
                    raise ProviderError(
                        f"anthropic {response.status_code}: {body}",
                        provider=self.name,
                        # 4xx other than rate limiting will fail identically on retry.
                        retryable=response.status_code in (408, 409, 429)
                        or response.status_code >= 500,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[5:].strip())
                    kind = event.get("type")
                    if kind == "content_block_delta":
                        delta = event.get("delta", {})
                        if text := delta.get("text"):
                            yield Chunk(text=text)
                    elif kind == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            yield Chunk(
                                tool_call={"id": block.get("id"), "name": block.get("name")}
                            )
                    elif kind == "message_start":
                        stats = event.get("message", {}).get("usage", {})
                        usage.input_tokens = stats.get("input_tokens", 0)
                    elif kind == "message_delta":
                        usage.output_tokens = event.get("usage", {}).get("output_tokens", 0)
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic transport: {exc}", provider=self.name) from exc
        finally:
            if owns_client:
                await client.aclose()

        usage.cost_usd = model.cost_for(usage.input_tokens, usage.output_tokens)
        yield Chunk(done=True, usage=usage)
