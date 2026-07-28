"""HTTP routes.

The whole surface is one router so the mounting order and the OpenAPI shape are
obvious. Handlers stay thin: they translate HTTP to kernel calls and back, and
contain no business logic.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from jarvis.api.schemas import (
    AgentSummary,
    ChatRequest,
    ModelSummary,
    RememberRequest,
    RouteRequest,
)
from jarvis.api.sse import HEADERS, frame
from jarvis.kernel.container import Jarvis
from jarvis.kernel.errors import JarvisError, NotFoundError
from jarvis.memory.models import MemoryKind

router = APIRouter()


def _jarvis(request: Request) -> Jarvis:
    return request.app.state.jarvis


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    jarvis = _jarvis(request)
    return {
        "status": "ok",
        "environment": jarvis.settings.environment,
        "providers": jarvis.provider_names,
        "models": len(jarvis.router.catalog()),
        "agents": len(jarvis.agents),
        "tools": len(jarvis.tools.all()),
        "memories": await jarvis.memory.count(),
        "events_published": jarvis.bus.published_count,
        "storage": jarvis.storage,
        "database_healthy": await jarvis.database.healthy() if jarvis.database else None,
    }


@router.get("/v1/models")
async def list_models(request: Request) -> list[ModelSummary]:
    return [
        ModelSummary(
            id=m.id,
            provider=m.provider,
            context_window=m.context_window,
            quality=m.quality,
            latency_score=m.latency_score,
            input_cost_per_mtok=m.input_cost_per_mtok,
            output_cost_per_mtok=m.output_cost_per_mtok,
            privacy=m.privacy.name.lower(),
        )
        for m in _jarvis(request).router.catalog()
    ]


@router.get("/v1/agents")
async def list_agents(request: Request) -> list[AgentSummary]:
    jarvis = _jarvis(request)
    return [
        AgentSummary.build(spec, jarvis.agents.metrics(spec.id)) for spec in jarvis.agents.all()
    ]


@router.get("/v1/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request) -> AgentSummary:
    jarvis = _jarvis(request)
    try:
        spec = jarvis.agents.get(agent_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AgentSummary.build(spec, jarvis.agents.metrics(agent_id))


@router.post("/v1/route")
async def route_request(body: RouteRequest, request: Request) -> dict[str, Any]:
    """Preview the routing decision without executing it — powers the palette."""
    matches = await _jarvis(request).orchestrator.plan(body.message)
    return {"candidates": [m.model_dump() for m in matches]}


@router.post("/v1/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    jarvis = _jarvis(request)
    if body.agent_id and body.agent_id not in jarvis.agents:
        raise HTTPException(status_code=404, detail=f"unknown agent: {body.agent_id}")

    history = body.history[-jarvis.settings.max_history_messages :]

    async def stream() -> AsyncIterator[str]:
        try:
            async for delta in jarvis.orchestrator.handle(
                body.message, agent_id=body.agent_id, history=history
            ):
                yield frame(delta.type, {"text": delta.text, **(delta.data or {})})
        except JarvisError as exc:
            yield frame("error", {"message": str(exc), "type": type(exc).__name__})
        except asyncio.CancelledError:  # client hung up mid-stream
            raise
        except Exception as exc:
            yield frame("error", {"message": str(exc), "type": "InternalError"})

    return StreamingResponse(stream(), media_type="text/event-stream", headers=HEADERS)


@router.get("/v1/events")
async def events(
    request: Request, topics: str = "**", limit: int | None = None
) -> StreamingResponse:
    """Firehose for the live-activity rail.

    ``topics`` is comma-separated patterns. ``limit`` closes the stream after
    N events, which turns the same endpoint into a bounded snapshot fetch for
    clients that cannot hold an open connection.
    """
    jarvis = _jarvis(request)
    patterns = tuple(t.strip() for t in topics.split(",") if t.strip())

    async def stream() -> AsyncIterator[str]:
        subscription = jarvis.bus.subscribe(*patterns)
        try:
            yield frame("ready", {"patterns": list(patterns)})
            sent = 0
            async for event in subscription.events():
                if await request.is_disconnected():
                    break
                yield frame(event.topic, event.to_dict())
                sent += 1
                if limit is not None and sent >= limit:
                    break
        finally:
            subscription.close()

    return StreamingResponse(stream(), media_type="text/event-stream", headers=HEADERS)


@router.get("/v1/runs")
async def list_runs(
    request: Request, limit: int = 25, agent_id: str | None = None
) -> list[dict[str, Any]]:
    runs = await _jarvis(request).runs.list(limit=limit, agent_id=agent_id)
    return [
        {
            "id": r.id,
            "request": r.request,
            "agent_id": r.agent_id,
            "state": r.state.value,
            "steps": len(r.steps),
            "cost_usd": r.cost_usd,
            "tokens": r.tokens,
            "duration_ms": round(r.duration_ms, 1),
            "created_at": r.created_at,
        }
        for r in runs
    ]


@router.get("/v1/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    run = await _jarvis(request).runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
    return {
        **run.model_dump(),
        "cost_usd": run.cost_usd,
        "tokens": run.tokens,
        "duration_ms": round(run.duration_ms, 1),
    }


@router.get("/v1/memory")
async def search_memory(request: Request, q: str = "", limit: int = 20) -> list[dict[str, Any]]:
    jarvis = _jarvis(request)
    if not q:
        return [m.model_dump() for m in await jarvis.memory.all()][:limit]
    recalls = await jarvis.memory.search(q, limit=limit)
    return [
        {
            **r.memory.model_dump(),
            "score": r.score,
            "signals": {"lexical": r.lexical, "semantic": r.semantic, "recency": r.recency},
        }
        for r in recalls
    ]


@router.post("/v1/memory", status_code=201)
async def remember(body: RememberRequest, request: Request) -> dict[str, Any]:
    try:
        kind = MemoryKind(body.kind) if body.kind else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown memory kind: {body.kind}") from exc
    memory = await _jarvis(request).memory.remember(
        body.content, kind=kind, scope=body.scope, tags=body.tags, source="api"
    )
    return memory.model_dump()


@router.delete("/v1/memory/{memory_id}", status_code=204)
async def forget(memory_id: str, request: Request) -> None:
    if not await _jarvis(request).memory.forget(memory_id):
        raise HTTPException(status_code=404, detail=f"unknown memory: {memory_id}")


@router.get("/v1/tools")
async def list_tools(request: Request) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "namespace": t.namespace,
            "description": t.description,
            "permission": t.permission.name.lower(),
            "parameters": t.parameters,
        }
        for t in _jarvis(request).tools.all()
    ]
