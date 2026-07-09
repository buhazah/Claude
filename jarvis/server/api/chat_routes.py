"""Chat routes: streaming orchestrated responses over Server-Sent Events,
plus conversation and message history."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.definitions import AGENTS
from ..agents.orchestrator import orchestrator
from ..db import Conversation, Message, User, get_session, SessionLocal
from ..schemas import ChatIn, ConversationOut, MessageOut
from ..security import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _get_or_create_conversation(
    session: AsyncSession, user: User, conversation_id: str | None, first_message: str, agent: str
) -> Conversation:
    if conversation_id:
        convo = await session.get(Conversation, conversation_id)
        if convo is None or convo.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return convo
    convo = Conversation(
        user_id=user.id, agent=agent,
        title=(first_message[:60] + "…") if len(first_message) > 60 else first_message,
    )
    session.add(convo)
    await session.commit()
    return convo


async def _load_history(session: AsyncSession, conversation_id: str) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in rows if m.role in {"user", "assistant"}]


@router.post("/stream")
async def chat_stream(
    body: ChatIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.agent and body.agent not in AGENTS and body.agent != "orchestrator":
        raise HTTPException(status_code=400, detail=f"Unknown agent '{body.agent}'")
    forced = body.agent if body.agent and body.agent != "orchestrator" else None

    convo = await _get_or_create_conversation(
        session, user, body.conversation_id, body.message, body.agent or "orchestrator"
    )
    history = await _load_history(session, convo.id)
    session.add(Message(conversation_id=convo.id, role="user", content=body.message))
    await session.commit()
    convo_id = convo.id
    user_id = user.id
    message = body.message

    async def event_stream():
        # Use a dedicated session for the generator's lifetime.
        final_text = ""
        final_agent = "orchestrator"
        async with SessionLocal() as gen_session:
            yield _sse("open", {"conversation_id": convo_id})
            try:
                async for event in orchestrator.handle(
                    gen_session, user_id, message, history=history,
                    conversation_id=convo_id, forced_agent=forced,
                ):
                    if event.type == "final":
                        final_text = event.data.get("text", "")
                        final_agent = event.data.get("agent", "orchestrator")
                    yield _sse(event.type, event.data)
            except Exception as exc:  # surface, don't crash the stream
                yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
            # Persist the assistant message.
            if final_text:
                gen_session.add(
                    Message(
                        conversation_id=convo_id, role="assistant",
                        content=final_text, agent=final_agent,
                    )
                )
                convo = await gen_session.get(Conversation, convo_id)
                if convo:
                    convo.agent = final_agent
                await gen_session.commit()
            yield _sse("done", {"agent": final_agent})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = (
        (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user.id)
                .order_by(Conversation.updated_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [ConversationOut.model_validate(c, from_attributes=True) for c in rows]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def conversation_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.get(Conversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [MessageOut.model_validate(m, from_attributes=True) for m in rows]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convo = await session.get(Conversation, conversation_id)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.delete(convo)
    await session.commit()
    return {"deleted": conversation_id}
