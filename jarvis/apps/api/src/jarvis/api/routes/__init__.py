"""HTTP routes.

The whole surface is one router so the mounting order and the OpenAPI shape are
obvious. Handlers stay thin: they translate HTTP to kernel calls and back, and
contain no business logic.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse

from jarvis.api.schemas import (
    AgentSummary,
    ApprovalDecision,
    ChatRequest,
    DocumentRequest,
    IngestRequest,
    ModelSummary,
    RememberRequest,
    RouteRequest,
    ToolInvocation,
    WorkflowRunRequest,
)
from jarvis.api.sse import HEADERS, frame
from jarvis.documents.models import DocumentKind
from jarvis.documents.render import MEDIA_TYPES, RENDERERS
from jarvis.kernel.container import Jarvis
from jarvis.kernel.errors import (
    ApprovalRequiredError,
    JarvisError,
    NotFoundError,
    PermissionDeniedError,
)
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
        # Two different things, deliberately named apart: `knowledge` is what
        # was ingested, `documents` is what Jarvis wrote.
        "knowledge": await jarvis.knowledge.count(),
        "documents": len(await jarvis.documents.list(limit=1000)),
        "workflows": len(await jarvis.workflows.all()),
        "scheduler": jarvis.scheduler.running,
        "computer": {
            "driver": jarvis.computer.computer.name,
            "available": jarvis.computer.computer.is_available(),
            "allowed_hosts": list(jarvis.computer.policy.allowed_hosts),
            "blocked_hosts": list(jarvis.computer.policy.blocked_hosts),
        },
        "voice": {
            "speaker": jarvis.speaker.name,
            "transcription": jarvis.transcriber.is_available(),
            "wake_word": jarvis.settings.wake_word,
        },
        "events_published": jarvis.bus.published_count,
        "storage": jarvis.storage,
        "pending_approvals": len(jarvis.approvals.pending()),
        "mcp_servers": sorted(jarvis.mcp.servers),
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


@router.get("/v1/modes")
async def list_modes(request: Request) -> dict[str, Any]:
    """The ways of working, and exactly what each one narrows.

    Published rather than hardcoded in the client, so the UI cannot claim a
    constraint the kernel does not enforce.
    """
    jarvis = _jarvis(request)
    return {
        "default": jarvis.modes.default_id,
        "modes": [
            {
                "id": mode.id,
                "name": mode.name,
                "tagline": mode.tagline,
                "agents": [s.id for s in mode.view(jarvis.agents).all()],
                "agent_count": len(mode.view(jarvis.agents).all()),
                "memory_scope": mode.memory_scope,
                "policy": mode.policy.value if mode.policy else None,
                "surfaces": list(mode.surfaces),
                "accent": mode.accent,
                "briefing": mode.briefing,
            }
            for mode in jarvis.modes.all()
        ],
    }


@router.post("/v1/route")
async def route_request(
    body: RouteRequest, request: Request, mode: str | None = None
) -> dict[str, Any]:
    """Preview the routing decision without executing it — powers the palette."""
    jarvis = _jarvis(request)
    try:
        orchestrator = jarvis.orchestrator_for(mode)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    matches = await orchestrator.plan(body.message)
    return {"candidates": [m.model_dump() for m in matches], "mode": jarvis.mode(mode).id}


@router.post("/v1/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    jarvis = _jarvis(request)
    try:
        orchestrator = jarvis.orchestrator_for(body.mode)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Checked against the *mode's* catalog, not the whole one: pinning an agent
    # the mode excludes must fail rather than quietly escape the narrowing.
    if body.agent_id and body.agent_id not in orchestrator.registry:
        raise HTTPException(
            status_code=404,
            detail=f"agent '{body.agent_id}' is not available in {jarvis.mode(body.mode).id} mode",
        )

    history = body.history[-jarvis.settings.max_history_messages :]

    async def stream() -> AsyncIterator[str]:
        try:
            async for delta in orchestrator.handle(
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


@router.websocket("/v1/voice")
async def voice(websocket: WebSocket) -> None:
    """Duplex voice.

    A WebSocket rather than SSE, because voice is the one interaction where the
    user talks *while* Jarvis does — barge-in needs a channel that carries
    speech up at the same moment audio is going down.

    The client sends recognised text (browser recognition is the default) or an
    explicit interrupt; the server streams state, tokens and speech back.
    """
    await websocket.accept()
    jarvis: Jarvis = websocket.app.state.jarvis
    session = jarvis.voice_session()

    async def pump() -> None:
        """Forward session events to the client until the session ends.

        A client that walks away mid-sentence is ordinary, not exceptional —
        the send simply fails and the pump stops.
        """
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            async for event in session.events():
                await websocket.send_json(event.to_dict())

    pumping = asyncio.create_task(pump())
    try:
        while True:
            message = await websocket.receive_json()
            kind = message.get("type")

            if kind == "transcript":
                await session.hear(
                    str(message.get("text", "")), final=bool(message.get("final", True))
                )
            elif kind == "interrupt":
                await session.interrupt()
            elif kind == "end":
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "text": str(exc)})
    finally:
        await session.close()
        pumping.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pumping
        with contextlib.suppress(Exception):
            await websocket.close()


@router.get("/v1/documents")
async def list_documents(
    request: Request, limit: int = 50, mode: str | None = None
) -> list[dict[str, Any]]:
    documents = await _jarvis(request).documents.list(limit=limit, mode=mode)
    return [d.summarise() for d in documents]


@router.post("/v1/documents")
async def compose_document(body: DocumentRequest, request: Request) -> StreamingResponse:
    """Compose a document, streaming the outline and then each section.

    Streaming rather than returning: a document takes long enough that a
    spinner would be a lie about what is happening, and the outline landing
    first is the point at which the user can tell it is going wrong.
    """
    jarvis = _jarvis(request)
    try:
        kind = DocumentKind(body.kind)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"unknown document kind: {body.kind}") from None
    try:
        mode = jarvis.mode(body.mode)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def stream() -> AsyncIterator[str]:
        try:
            async for event, document, text in jarvis.composer.compose(
                body.request,
                kind=kind,
                mode=mode.id,
                scope=body.scope,
                agent_id=body.agent_id,
            ):
                if event == "token":
                    yield frame("token", {"text": text})
                elif event == "outline":
                    yield frame(
                        "outline",
                        {
                            "id": document.id,
                            "title": document.title,
                            "sections": [
                                {"heading": s.heading, "intent": s.intent}
                                for s in document.sections
                            ],
                        },
                    )
                elif event == "section":
                    yield frame("section", {"heading": text})
                elif event in ("done", "error"):
                    # Saved before the terminal frame, so a client that acts on
                    # `done` can immediately fetch what it was told about.
                    await jarvis.documents.save(document)
                    yield frame(event, {**document.summarise(), "message": text})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield frame("error", {"message": str(exc), "type": "InternalError"})

    return StreamingResponse(stream(), media_type="text/event-stream", headers=HEADERS)


@router.get("/v1/documents/{document_id}")
async def get_document(document_id: str, request: Request) -> dict[str, Any]:
    document = await _jarvis(request).documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"unknown document: {document_id}")
    return {
        **document.summarise(),
        "request": document.request,
        "sections": [s.model_dump() for s in document.sections],
        "references": [c.model_dump() for c in document.citations],
    }


@router.get("/v1/documents/{document_id}/export")
async def export_document(document_id: str, request: Request, format: str = "md") -> Response:
    """The document as something you can send to a person."""
    if format not in RENDERERS:
        raise HTTPException(
            status_code=400, detail=f"unknown format: {format} (try {', '.join(RENDERERS)})"
        )
    document = await _jarvis(request).documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"unknown document: {document_id}")

    slug = "".join(c if c.isalnum() else "-" for c in document.title.lower()).strip("-")[:60]
    return Response(
        content=RENDERERS[format](document),
        media_type=MEDIA_TYPES[format],
        headers={"content-disposition": f'inline; filename="{slug or document.id}.{format}"'},
    )


@router.delete("/v1/documents/{document_id}")
async def delete_document(document_id: str, request: Request) -> dict[str, bool]:
    return {"deleted": await _jarvis(request).documents.delete(document_id)}


@router.get("/v1/computer")
async def computer_status(request: Request) -> dict[str, Any]:
    """What the browser is looking at, and everything it has done."""
    session = _jarvis(request).computer
    return {
        "driver": session.computer.name,
        "available": session.computer.is_available(),
        "policy": {
            "allowed_hosts": list(session.policy.allowed_hosts),
            "blocked_hosts": list(session.policy.blocked_hosts),
        },
        "budget": {
            "steps": len(session.steps),
            "max_steps": session.max_steps,
            "max_seconds": session.max_seconds,
        },
        "page": session.snapshot.to_dict(),
        "steps": [s.to_dict() for s in session.steps[-50:]],
    }


@router.get("/v1/computer/screen")
async def computer_screen(request: Request) -> Response:
    """The current screenshot.

    Served as an image rather than base64 in JSON: the evidence for a decision
    should be as cheap to look at as possible.
    """
    session = _jarvis(request).computer
    if session.snapshot.screenshot is None:
        raise HTTPException(status_code=404, detail="nothing has been observed yet")
    return Response(content=session.snapshot.screenshot, media_type="image/png")


@router.post("/v1/voice/transcribe")
async def transcribe(request: Request) -> dict[str, Any]:
    """Transcribe an uploaded utterance, when the browser cannot recognise."""
    jarvis = _jarvis(request)
    if not jarvis.transcriber.is_available():
        raise HTTPException(
            status_code=503,
            detail="no speech key configured — recognise in the browser instead",
        )
    audio = await request.body()
    segment = await jarvis.transcriber.transcribe(audio)
    return {"text": segment.text, "confidence": segment.confidence}


@router.get("/v1/workflows")
async def list_workflows(request: Request) -> list[dict[str, Any]]:
    return [w.model_dump(mode="json") for w in await _jarvis(request).workflows.all()]


@router.post("/v1/workflows", status_code=201)
async def save_workflow(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Create or update a workflow. Rejects a graph that cannot execute."""
    from jarvis.workflows.models import Workflow

    try:
        workflow = Workflow.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if problems := workflow.validate_graph():
        # Every problem at once: fixing one typo per save is a miserable loop.
        raise HTTPException(status_code=422, detail={"problems": problems})

    saved = await _jarvis(request).workflows.save(workflow)
    return saved.model_dump(mode="json")


@router.delete("/v1/workflows/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, request: Request) -> None:
    if not await _jarvis(request).workflows.remove(workflow_id):
        raise HTTPException(status_code=404, detail=f"unknown workflow: {workflow_id}")


@router.post("/v1/workflows/{workflow_id}/run")
async def run_workflow(
    workflow_id: str, body: WorkflowRunRequest, request: Request
) -> dict[str, Any]:
    """Start a run. Returns as soon as it finishes *or* suspends."""
    jarvis = _jarvis(request)
    workflow = await jarvis.workflows.get(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"unknown workflow: {workflow_id}")
    try:
        run = await jarvis.engine.start(workflow, inputs=body.inputs, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return run.model_dump(mode="json")


@router.get("/v1/workflow-runs")
async def list_workflow_runs(
    request: Request, workflow_id: str | None = None, limit: int = 25
) -> list[dict[str, Any]]:
    runs = await _jarvis(request).workflows.runs(workflow_id=workflow_id, limit=limit)
    return [
        {
            "id": r.id,
            "workflow_id": r.workflow_id,
            "workflow_name": r.workflow_name,
            "state": r.state.value,
            "trigger": r.trigger,
            "steps": len(r.records),
            "cost_usd": r.cost_usd,
            "created_at": r.created_at,
            "error": r.error,
        }
        for r in runs
    ]


@router.get("/v1/workflow-runs/{run_id}")
async def get_workflow_run(run_id: str, request: Request) -> dict[str, Any]:
    run = await _jarvis(request).workflows.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown workflow run: {run_id}")
    return {**run.model_dump(mode="json"), "cost_usd": run.cost_usd}


@router.get("/v1/triggers")
async def list_triggers(request: Request) -> list[dict[str, Any]]:
    return [t.model_dump(mode="json") for t in await _jarvis(request).workflows.triggers()]


@router.post("/v1/triggers", status_code=201)
async def save_trigger(body: dict[str, Any], request: Request) -> dict[str, Any]:
    from jarvis.workflows.models import Trigger

    try:
        trigger = Trigger.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    jarvis = _jarvis(request)
    if await jarvis.workflows.get(trigger.workflow_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown workflow: {trigger.workflow_id}")
    return (await jarvis.workflows.save_trigger(trigger)).model_dump(mode="json")


@router.delete("/v1/triggers/{trigger_id}", status_code=204)
async def delete_trigger(trigger_id: str, request: Request) -> None:
    if not await _jarvis(request).workflows.remove_trigger(trigger_id):
        raise HTTPException(status_code=404, detail=f"unknown trigger: {trigger_id}")


@router.get("/v1/knowledge")
async def list_knowledge(request: Request, limit: int = 100) -> list[dict[str, Any]]:
    documents = await _jarvis(request).knowledge.documents(limit=limit)
    return [d.model_dump() for d in documents]


@router.get("/v1/knowledge/search")
async def search_knowledge(request: Request, q: str, limit: int = 6) -> list[dict[str, Any]]:
    """Retrieve passages with the citation attached to each."""
    citations = await _jarvis(request).knowledge.search(q, limit=limit)
    return [{**c.model_dump(), "reference": c.reference()} for c in citations]


@router.post("/v1/knowledge", status_code=201)
async def ingest(body: IngestRequest, request: Request) -> dict[str, Any]:
    """Ingest a URL, a path on disk, or pasted text."""
    jarvis = _jarvis(request)
    if body.url:
        result = await jarvis.ingestor.ingest_url(body.url, scope=body.scope)
    elif body.path:
        # Paths are resolved inside the workspace: ingestion must not become a
        # way to read arbitrary files off the host.
        try:
            target = jarvis.workspace.resolve(body.path)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        result = (
            await jarvis.ingestor.ingest_directory(target, scope=body.scope)
            if target.is_dir()
            else await jarvis.ingestor.ingest_file(target, scope=body.scope)
        )
    elif body.text:
        result = await jarvis.ingestor.ingest_text(
            body.text, title=body.title or "Pasted note", scope=body.scope
        )
    else:
        raise HTTPException(status_code=422, detail="provide one of url, path or text")
    return result.to_dict()


@router.delete("/v1/knowledge/{document_id}", status_code=204)
async def forget_document(document_id: str, request: Request) -> None:
    if not await _jarvis(request).knowledge.remove(document_id):
        raise HTTPException(status_code=404, detail=f"unknown document: {document_id}")


@router.post("/v1/tools/{name}/invoke")
async def invoke_tool(name: str, body: ToolInvocation, request: Request) -> dict[str, Any]:
    """Run a tool directly.

    Goes through exactly the same permission wall as an agent's call — a
    dangerous tool parks here too, waiting for the approval gate. That is the
    point: there is no path to a tool that bypasses the wall.
    """
    jarvis = _jarvis(request)
    try:
        result = await jarvis.tools.invoke(name, body.arguments, agent_id="user")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PermissionDeniedError, ApprovalRequiredError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"tool": name, "result": result}


@router.get("/v1/approvals")
async def list_approvals(request: Request, pending_only: bool = False) -> list[dict[str, Any]]:
    """Approvals waiting on a human, plus recent decisions."""
    broker = _jarvis(request).approvals
    approvals = broker.pending() if pending_only else broker.all()
    return [a.to_dict() for a in approvals]


@router.post("/v1/approvals/{approval_id}")
async def decide_approval(
    approval_id: str, body: ApprovalDecision, request: Request
) -> dict[str, Any]:
    """Approve or deny a suspended tool call, releasing the waiting run."""
    try:
        approval = _jarvis(request).approvals.resolve(
            approval_id, approved=body.approved, reason=body.reason
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return approval.to_dict()


@router.get("/v1/audit")
async def list_audit(request: Request, limit: int = 50) -> dict[str, Any]:
    """The audit trail, with the integrity of its hash chain."""
    jarvis = _jarvis(request)
    intact, broken_at = await jarvis.audit.verify()
    return {
        "intact": intact,
        "broken_at": broken_at,
        "entries": await jarvis.audit.entries(limit=limit),
    }


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
