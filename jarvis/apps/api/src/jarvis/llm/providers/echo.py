"""Deterministic offline provider.

This is not a mock bolted onto tests — it is a first-class adapter that lets
the whole system boot, stream and be exercised with no API keys and no
network. CI runs against it, demos run against it, and it is the reason the
fallback chain always has a floor.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator

from jarvis.llm.base import (
    Chunk,
    CompletionRequest,
    ModelSpec,
    Privacy,
    ToolSchema,
    Usage,
)

ECHO_MODEL = ModelSpec(
    id="echo-1",
    provider="echo",
    context_window=32_000,
    max_output=4096,
    input_cost_per_mtok=0.0,
    output_cost_per_mtok=0.0,
    quality=0.25,
    latency_score=1.0,
    privacy=Privacy.LOCAL,
    supports_tools=True,
)


class EchoProvider:
    """Produces a stable, readable response derived from the request."""

    name = "echo"

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def models(self) -> list[ModelSpec]:
        return [ECHO_MODEL]

    def is_available(self) -> bool:
        return not self._fail

    async def stream(
        self,
        request: CompletionRequest,
        model: ModelSpec,
        tools: list[ToolSchema] | None = None,
    ) -> AsyncIterator[Chunk]:
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role.value == "user"), ""
        )
        digest = hashlib.sha256(last_user.encode()).hexdigest()[:8]
        words = f"[echo:{digest}] {last_user.strip()}".split()

        input_tokens = request.token_estimate()
        output_tokens = 0
        for word in words:
            output_tokens += 1
            yield Chunk(text=word + " ")

        yield Chunk(
            done=True,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=model.cost_for(input_tokens, output_tokens),
            ),
        )
