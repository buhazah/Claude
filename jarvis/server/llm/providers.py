"""Concrete LLM provider implementations over httpx.

AnthropicProvider and GoogleProvider speak their native APIs; everything
else (OpenAI, Groq, OpenRouter, DeepSeek, Ollama) shares the
OpenAI-compatible chat/completions wire format.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import httpx

from .base import LLMError, LLMProvider, LLMResponse

RETRY_STATUS = {429, 500, 502, 503, 529}
MAX_RETRIES = 3


async def _post_with_retries(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.post(url, **kwargs)
        except httpx.HTTPError as exc:
            # Transport-level failure (DNS, connect, read timeout) — retryable.
            last = exc
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
            continue
        if resp.status_code < 400:
            return resp
        if resp.status_code in RETRY_STATUS and attempt < MAX_RETRIES - 1:
            # Transient server-side/rate-limit status — back off and retry.
            await asyncio.sleep(2**attempt)
            continue
        # Non-retryable client error (e.g. 400/401/404): fail fast with detail.
        detail = resp.text[:400].replace("\n", " ")
        raise LLMError(f"request to {url} returned {resp.status_code}: {detail}")
    raise LLMError(f"request to {url} failed after {MAX_RETRIES} attempts: {last}")


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    API = "https://api.anthropic.com/v1/messages"

    # The Claude 5 generation (Fable/Mythos/Sonnet 5) and Opus 4.8 deprecate the
    # `temperature` sampling parameter; sending it returns a 400. Match by the
    # substrings that identify those model families.
    NO_TEMPERATURE = ("fable-5", "mythos-5", "sonnet-5", "opus-4-8")

    def _accepts_temperature(self, model: str) -> bool:
        return not any(tag in model for tag in self.NO_TEMPERATURE)

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def complete(self, messages, model, max_tokens=2048, temperature=0.7) -> LLMResponse:
        system, rest = self.split_system(messages)
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": rest,
        }
        if self._accepts_temperature(model):
            body["temperature"] = temperature
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await _post_with_retries(client, self.API, headers=self._headers(), json=body)
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model=model,
            provider=self.name,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            raw=data,
        )

    async def stream(self, messages, model, max_tokens=2048, temperature=0.7) -> AsyncIterator[str]:
        system, rest = self.split_system(messages)
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": rest,
            "stream": True,
        }
        if self._accepts_temperature(model):
            body["temperature"] = temperature
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", self.API, headers=self._headers(), json=body) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:500]
                    raise LLMError(f"anthropic stream failed ({resp.status_code}): {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI chat/completions wire format — used by OpenAI, Groq,
    OpenRouter, DeepSeek, and Ollama (/v1)."""

    name = "openai"
    default_base = "https://api.openai.com/v1"

    def __init__(self, api_key: str = "", base_url: str = "", name: str = ""):
        super().__init__(api_key, base_url or self.default_base)
        if name:
            self.name = name

    def _headers(self) -> dict:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(self, messages, model, max_tokens=2048, temperature=0.7) -> LLMResponse:
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await _post_with_retries(
                client, f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            )
        data = resp.json()
        usage = data.get("usage", {})
        return LLMResponse(
            text=data["choices"][0]["message"].get("content") or "",
            model=model,
            provider=self.name,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            raw=data,
        )

    async def stream(self, messages, model, max_tokens=2048, temperature=0.7) -> AsyncIterator[str]:
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:500]
                    raise LLMError(f"{self.name} stream failed ({resp.status_code}): {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    delta = event.get("choices", [{}])[0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]


class GoogleProvider(LLMProvider):
    name = "google"
    API = "https://generativelanguage.googleapis.com/v1beta/models"

    @staticmethod
    def _to_gemini(messages: list[dict]) -> tuple[dict | None, list[dict]]:
        system, rest = LLMProvider.split_system(messages)
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in rest
        ]
        sys_block = {"parts": [{"text": system}]} if system else None
        return sys_block, contents

    async def complete(self, messages, model, max_tokens=2048, temperature=0.7) -> LLMResponse:
        sys_block, contents = self._to_gemini(messages)
        body: dict = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if sys_block:
            body["systemInstruction"] = sys_block
        url = f"{self.API}/{model}:generateContent?key={self.api_key}"
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await _post_with_retries(client, url, json=body)
        data = resp.json()
        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            text = "".join(
                p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])
            )
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            model=model,
            provider=self.name,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
            raw=data,
        )

    async def stream(self, messages, model, max_tokens=2048, temperature=0.7) -> AsyncIterator[str]:
        # Gemini streaming uses a different endpoint; a single-shot completion
        # yielded whole keeps behaviour identical for callers.
        resp = await self.complete(messages, model, max_tokens, temperature)
        if resp.text:
            yield resp.text
