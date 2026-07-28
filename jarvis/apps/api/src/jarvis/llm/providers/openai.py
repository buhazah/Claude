"""OpenAI-compatible adapter.

The chat-completions wire format is spoken by OpenAI, DeepSeek, Qwen, Groq,
Together and Ollama, so one adapter with a configurable base URL and model
catalog covers all of them. ``OpenAIProvider`` is the hosted OpenAI instance;
``LocalProvider`` points the same code at an Ollama endpoint and marks its
models ``Privacy.LOCAL``.
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
    ToolCall,
    ToolSchema,
    Usage,
)

OPENAI_MODELS = [
    ModelSpec(
        id="gpt-5",
        provider="openai",
        context_window=400_000,
        max_output=32_000,
        input_cost_per_mtok=1.25,
        output_cost_per_mtok=10.0,
        quality=0.95,
        latency_score=0.6,
        modalities=(Modality.TEXT, Modality.VISION),
    ),
    ModelSpec(
        id="gpt-5-mini",
        provider="openai",
        context_window=400_000,
        max_output=16_000,
        input_cost_per_mtok=0.25,
        output_cost_per_mtok=2.0,
        quality=0.82,
        latency_score=0.88,
        modalities=(Modality.TEXT, Modality.VISION),
    ),
]

LOCAL_MODELS = [
    ModelSpec(
        id="qwen3:14b",
        provider="local",
        context_window=32_000,
        max_output=8_192,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        quality=0.68,
        latency_score=0.45,
        privacy=Privacy.LOCAL,
    ),
]


class OpenAICompatibleProvider:
    """Shared implementation for every chat-completions endpoint."""

    def __init__(
        self,
        name: str,
        *,
        api_key: str | None,
        base_url: str,
        models: list[ModelSpec],
        requires_key: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._models = models
        self._requires_key = requires_key
        self._client = client

    def models(self) -> list[ModelSpec]:
        return list(self._models)

    def is_available(self) -> bool:
        return bool(self._api_key) if self._requires_key else True

    def _payload(
        self, request: CompletionRequest, model: ModelSpec, tools: list[ToolSchema] | None
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            entry: dict[str, Any] = {"role": m.role.value, "content": m.content}
            if m.role is Role.TOOL and m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in m.tool_calls
                ]
            messages.append(entry)

        payload: dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "max_tokens": min(request.max_output_tokens, model.max_output),
            "temperature": request.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters or {"type": "object", "properties": {}},
                    },
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
        if self._requires_key and not self._api_key:
            raise ProviderUnavailableError(f"{self.name} api key is not set", provider=self.name)

        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"

        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        owns_client = self._client is None
        usage = Usage()
        # Tool calls stream as fragments keyed by index; assemble them and emit
        # only once the model signals it has finished asking.
        pending: dict[int, dict[str, str]] = {}
        try:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=self._payload(request, model, tools),
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")[:500]
                    raise ProviderError(
                        f"{self.name} {response.status_code}: {body}",
                        provider=self.name,
                        retryable=response.status_code in (408, 409, 429)
                        or response.status_code >= 500,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    if stats := event.get("usage"):
                        usage.input_tokens = stats.get("prompt_tokens", usage.input_tokens)
                        usage.output_tokens = stats.get("completion_tokens", usage.output_tokens)
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {})
                        if text := delta.get("content"):
                            yield Chunk(text=text)
                        for fragment in delta.get("tool_calls", []) or []:
                            slot = pending.setdefault(
                                fragment.get("index", 0), {"id": "", "name": "", "json": ""}
                            )
                            if identifier := fragment.get("id"):
                                slot["id"] = identifier
                            function = fragment.get("function", {})
                            if name := function.get("name"):
                                slot["name"] = name
                            slot["json"] += function.get("arguments", "") or ""
                        if choice.get("finish_reason") == "tool_calls":
                            for slot in pending.values():
                                yield Chunk(tool_call=_assemble(slot))
                            pending.clear()
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name} transport: {exc}", provider=self.name) from exc
        finally:
            if owns_client:
                await client.aclose()

        if not usage.input_tokens:
            usage.input_tokens = request.token_estimate()
        usage.cost_usd = model.cost_for(usage.input_tokens, usage.output_tokens)
        yield Chunk(done=True, usage=usage)


def _assemble(slot: dict[str, str]) -> ToolCall:
    """Turn accumulated fragments into a tool call.

    Unparseable arguments become an empty object rather than an exception: the
    runtime reports the tool failure back to the model, which can retry, and
    that is far better than killing the stream.
    """
    try:
        arguments = json.loads(slot["json"]) if slot["json"].strip() else {}
    except json.JSONDecodeError:
        arguments = {}
    return ToolCall(id=slot["id"], name=slot["name"], arguments=arguments)


def OpenAIProvider(
    api_key: str | None, *, client: httpx.AsyncClient | None = None
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "openai",
        api_key=api_key,
        base_url="https://api.openai.com/v1",
        models=OPENAI_MODELS,
        client=client,
    )


def LocalProvider(
    base_url: str = "http://localhost:11434/v1", *, client: httpx.AsyncClient | None = None
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "local",
        api_key=None,
        base_url=base_url,
        models=LOCAL_MODELS,
        requires_key=False,
        client=client,
    )
