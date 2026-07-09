"""Long-term memory: storage, semantic retrieval, ranking, decay,
consolidation, reflection, and summarization.

Retrieval score = semantic similarity × importance × recency decay,
mirroring generative-agent style memory ranking. Consolidation merges
old low-importance memories of one kind into an LLM-written summary
memory; reflection distills recent activity into higher-level insights.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import Memory, utcnow
from ..llm.base import LLMError
from ..llm.router import RouteProfile, router
from .embeddings import embedder

log = logging.getLogger("jarvis.memory")

MEMORY_KINDS = {
    "profile", "preference", "goal", "project", "relationship", "fact",
    "decision", "mistake", "lesson", "skill", "style", "business", "life",
    "conversation", "reflection", "summary",
}

# Baseline importance per kind; the extractor can override per item.
KIND_IMPORTANCE = {
    "profile": 0.9, "goal": 0.85, "business": 0.8, "preference": 0.75,
    "decision": 0.7, "lesson": 0.7, "mistake": 0.65, "relationship": 0.65,
    "project": 0.6, "skill": 0.6, "style": 0.6, "life": 0.55, "fact": 0.5,
    "reflection": 0.7, "summary": 0.6, "conversation": 0.35,
}


def _to_bytes(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def _from_bytes(raw: bytes) -> np.ndarray | None:
    if not raw:
        return None
    return np.frombuffer(raw, dtype=np.float32)


class MemoryManager:
    # ------------------------------------------------------------- storage

    async def remember(
        self,
        session: AsyncSession,
        user_id: str,
        content: str,
        kind: str = "fact",
        source: str = "chat",
        importance: float | None = None,
        meta: dict | None = None,
    ) -> Memory:
        if kind not in MEMORY_KINDS:
            kind = "fact"
        content = content.strip()[:8000]
        vec = (await embedder.embed([content]))[0]
        memory = Memory(
            user_id=user_id,
            kind=kind,
            content=content,
            source=source,
            importance=importance if importance is not None else KIND_IMPORTANCE[kind],
            embedding=_to_bytes(vec),
            meta=meta or {},
        )
        session.add(memory)
        await session.commit()
        return memory

    # ----------------------------------------------------------- retrieval

    def _recency_weight(self, last_accessed: datetime) -> float:
        age_days = max(0.0, (utcnow() - last_accessed).total_seconds() / 86400)
        return math.exp(-math.log(2) * age_days / settings.memory_decay_half_life_days)

    async def recall(
        self,
        session: AsyncSession,
        user_id: str,
        query: str,
        limit: int | None = None,
        kinds: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        limit = limit or settings.memory_max_retrieval
        stmt = select(Memory).where(
            Memory.user_id == user_id, Memory.consolidated_into.is_(None)
        )
        if kinds:
            stmt = stmt.where(Memory.kind.in_(kinds))
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            return []

        qvec = (await embedder.embed([query]))[0]
        scored: list[tuple[Memory, float]] = []
        for mem in rows:
            vec = _from_bytes(mem.embedding)
            if vec is None or vec.shape != qvec.shape:
                # Embedder changed since this memory was written — re-embed lazily.
                vec = (await embedder.embed([mem.content]))[0]
                mem.embedding = _to_bytes(vec)
            similarity = float(np.dot(qvec, vec))
            score = (
                0.6 * max(similarity, 0.0)
                + 0.25 * mem.importance
                + 0.15 * self._recency_weight(mem.last_accessed)
            )
            scored.append((mem, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        top = scored[:limit]
        now = utcnow()
        for mem, _ in top:
            mem.access_count += 1
            mem.last_accessed = now
        await session.commit()
        return top

    async def context_block(self, session: AsyncSession, user_id: str, query: str) -> str:
        """Format recalled memories for inclusion in an agent's system prompt."""
        top = await self.recall(session, user_id, query)
        if not top:
            return ""
        lines = [f"- [{mem.kind}] {mem.content}" for mem, _ in top]
        return "Relevant long-term memories about the user:\n" + "\n".join(lines)

    # ---------------------------------------------------------- extraction

    async def extract_from_exchange(
        self, session: AsyncSession, user_id: str, user_text: str, assistant_text: str
    ) -> list[Memory]:
        """Ask a cheap model to pull durable facts out of a chat exchange."""
        prompt = (
            "Extract durable long-term memories about the user from this exchange. "
            "Return STRICT JSON: a list of objects with keys kind, content, importance "
            "(0.0-1.0). kind must be one of: profile, preference, goal, project, "
            "relationship, fact, decision, business, life, style. Only include things "
            "worth remembering for months (identity, preferences, goals, businesses, "
            "relationships, decisions). Return [] if nothing qualifies.\n\n"
            f"USER: {user_text[:3000]}\n\nASSISTANT: {assistant_text[:2000]}"
        )
        try:
            resp = await router.complete(
                [{"role": "user", "content": prompt}],
                profile=RouteProfile(complexity=3, latency_sensitive=True),
                max_tokens=800,
                temperature=0.0,
            )
            items = _parse_json_list(resp.text)
        except LLMError:
            return []
        saved: list[Memory] = []
        for item in items[:10]:
            content = str(item.get("content", "")).strip()
            if len(content) < 8:
                continue
            saved.append(
                await self.remember(
                    session,
                    user_id,
                    content,
                    kind=str(item.get("kind", "fact")),
                    source="extraction",
                    importance=float(item.get("importance", 0.5)),
                )
            )
        return saved

    # ------------------------------------------------------- consolidation

    async def consolidate(self, session: AsyncSession, user_id: str) -> int:
        """Merge bloated kinds into summary memories. Returns merged count."""
        merged_total = 0
        counts = (
            await session.execute(
                select(Memory.kind, func.count())
                .where(Memory.user_id == user_id, Memory.consolidated_into.is_(None))
                .group_by(Memory.kind)
            )
        ).all()
        for kind, count in counts:
            if kind in {"summary", "reflection"} or count < settings.memory_consolidation_threshold:
                continue
            # Consolidate the oldest, least-important half.
            rows = (
                (
                    await session.execute(
                        select(Memory)
                        .where(
                            Memory.user_id == user_id,
                            Memory.kind == kind,
                            Memory.consolidated_into.is_(None),
                        )
                        .order_by(Memory.importance.asc(), Memory.created_at.asc())
                        .limit(count // 2)
                    )
                )
                .scalars()
                .all()
            )
            if len(rows) < 5:
                continue
            corpus = "\n".join(f"- {m.content}" for m in rows)
            try:
                resp = await router.complete(
                    [
                        {
                            "role": "user",
                            "content": (
                                f"Condense these '{kind}' memories about a user into at most 8 "
                                "bullet points, preserving every distinct durable fact:\n"
                                f"{corpus[:12000]}"
                            ),
                        }
                    ],
                    profile=RouteProfile(complexity=4),
                    max_tokens=600,
                    temperature=0.2,
                )
            except LLMError as exc:
                log.warning("consolidation skipped for kind=%s: %s", kind, exc)
                continue
            summary = await self.remember(
                session, user_id, resp.text, kind="summary", source="consolidation",
                importance=max(m.importance for m in rows),
                meta={"consolidated_kind": kind, "merged": len(rows)},
            )
            for m in rows:
                m.consolidated_into = summary.id
            merged_total += len(rows)
        await session.commit()
        return merged_total

    # ---------------------------------------------------------- reflection

    async def reflect(self, session: AsyncSession, user_id: str) -> Memory | None:
        """Distill the most recent memories into a higher-level insight."""
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .where(Memory.user_id == user_id, Memory.consolidated_into.is_(None))
                    .order_by(Memory.created_at.desc())
                    .limit(30)
                )
            )
            .scalars()
            .all()
        )
        if len(rows) < 5:
            return None
        corpus = "\n".join(f"- [{m.kind}] {m.content}" for m in rows)
        try:
            resp = await router.complete(
                [
                    {
                        "role": "user",
                        "content": (
                            "From these recent memories about a user, write ONE non-obvious, "
                            "actionable insight about their goals, patterns, or needs "
                            "(2-3 sentences):\n" + corpus[:10000]
                        ),
                    }
                ],
                profile=RouteProfile(complexity=6),
                max_tokens=300,
                temperature=0.4,
            )
        except LLMError:
            return None
        return await self.remember(
            session, user_id, resp.text, kind="reflection", source="reflection", importance=0.75
        )


def _parse_json_list(text: str) -> list[dict]:
    """Tolerantly parse a JSON list out of model output (handles fences)."""
    import json
    import re

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return [d for d in data if isinstance(d, dict)]
    except json.JSONDecodeError:
        return []


memory_manager = MemoryManager()
