"""Memory records and automatic categorisation."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from jarvis.kernel.ids import new_id


class MemoryKind(StrEnum):
    """What sort of thing is being remembered. Drives retention and recall."""

    FACT = "fact"  # durable truths about the world or the user's context
    PREFERENCE = "preference"  # how the user likes things done
    PERSON = "person"  # people, relationships, context about them
    PROJECT = "project"  # projects, businesses, their state
    GOAL = "goal"  # intentions with a horizon
    IDEA = "idea"  # unformed thoughts worth keeping
    EVENT = "event"  # meetings, milestones, things that happened
    DECISION = "decision"  # choices made and their reasoning
    MISTAKE = "mistake"  # what went wrong, so it stops recurring
    SUCCESS = "success"  # what worked, so it repeats
    STYLE = "style"  # the user's voice and writing habits
    DOCUMENT = "document"  # ingested source material
    CODE = "code"  # code and repository knowledge
    CONVERSATION = "conversation"  # episodic dialogue summaries


class MemoryTier(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


TIER_BY_KIND: dict[MemoryKind, MemoryTier] = {
    MemoryKind.CONVERSATION: MemoryTier.EPISODIC,
    MemoryKind.EVENT: MemoryTier.EPISODIC,
    MemoryKind.MISTAKE: MemoryTier.PROCEDURAL,
    MemoryKind.SUCCESS: MemoryTier.PROCEDURAL,
    MemoryKind.DECISION: MemoryTier.PROCEDURAL,
}


class Memory(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    content: str
    kind: MemoryKind = MemoryKind.FACT
    tier: MemoryTier = MemoryTier.SEMANTIC
    scope: str = "global"
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    salience: float = 0.5  # 0..1, how much this should influence recall
    created_at: datetime | None = None
    last_accessed_at: datetime | None = None
    access_count: int = 0
    embedding: list[float] | None = Field(default=None, exclude=True)
    superseded_by: str | None = None

    def touch(self, when: datetime) -> None:
        self.last_accessed_at = when
        self.access_count += 1


class Recall(BaseModel):
    """A memory returned from a search, with why it surfaced."""

    memory: Memory
    score: float
    lexical: float = 0.0
    semantic: float = 0.0
    recency: float = 0.0


# Ordered most-specific first: the first pattern to match wins, so
# "I decided to..." is a DECISION rather than a generic FACT.
_RULES: list[tuple[MemoryKind, re.Pattern[str]]] = [
    (
        MemoryKind.MISTAKE,
        re.compile(r"\b(went wrong|failed|mistake|broke|regret|shouldn't have|bug)\b"),
    ),
    (
        MemoryKind.SUCCESS,
        re.compile(r"\b(worked well|succeeded|great result|win|landed|shipped)\b"),
    ),
    (MemoryKind.DECISION, re.compile(r"\b(decided|chose|we'll go with|settled on|picked)\b")),
    (
        MemoryKind.PREFERENCE,
        re.compile(r"\b(prefer|likes?|dislikes?|hates?|always|never|favourite|favorite)\b"),
    ),
    (MemoryKind.STYLE, re.compile(r"\b(tone|voice|writing style|phrasing|wording)\b")),
    (
        MemoryKind.GOAL,
        re.compile(r"\b(goal|aim|want to|target|by (q[1-4]|next|end of)|objective)\b"),
    ),
    (MemoryKind.PROJECT, re.compile(r"\b(project|launch|building|startup|company|repo|product)\b")),
    (
        MemoryKind.PERSON,
        re.compile(r"\b(met|colleague|client|friend|manager|investor|partner|his|her|their) \b"),
    ),
    (
        MemoryKind.EVENT,
        re.compile(
            r"\b(meeting|call|standup|conference|dinner|deadline|on (mon|tue|wed|thu|fri|sat|sun))"
        ),
    ),
    (MemoryKind.IDEA, re.compile(r"\b(idea|what if|could try|concept|thought about)\b")),
    (
        MemoryKind.CODE,
        re.compile(r"\b(function|class|module|api|endpoint|migration|typescript|python)\b"),
    ),
]


def categorize(content: str) -> MemoryKind:
    """Infer a memory's kind from its text."""
    text = content.lower()
    for kind, pattern in _RULES:
        if pattern.search(text):
            return kind
    return MemoryKind.FACT


def tier_for(kind: MemoryKind) -> MemoryTier:
    return TIER_BY_KIND.get(kind, MemoryTier.SEMANTIC)


def salience_for(kind: MemoryKind, content: str) -> float:
    """Heuristic importance. Explicit, durable statements outrank chatter."""
    base = {
        MemoryKind.DECISION: 0.85,
        MemoryKind.GOAL: 0.85,
        MemoryKind.PREFERENCE: 0.8,
        MemoryKind.MISTAKE: 0.8,
        MemoryKind.STYLE: 0.75,
        MemoryKind.PERSON: 0.7,
        MemoryKind.PROJECT: 0.7,
        MemoryKind.SUCCESS: 0.7,
        MemoryKind.FACT: 0.5,
        MemoryKind.EVENT: 0.5,
        MemoryKind.IDEA: 0.45,
        MemoryKind.CONVERSATION: 0.35,
    }.get(kind, 0.5)
    if len(content) < 25:  # one-liners are usually incidental
        base -= 0.1
    return round(min(max(base, 0.05), 1.0), 3)
