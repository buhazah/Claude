"""Recall ranking — one implementation, shared by every store.

This module exists to prevent a specific failure: if the in-memory store ranked
in Python and the SQL store ranked in SQL, the two would drift, and "why did
Jarvis recall that?" would have two different answers depending on deployment.

So stores differ only in how they *fetch candidates* (a scan, or a pgvector ANN
index). Scoring is always this code. Retrieval strategy is an implementation
detail; ranking semantics are part of the product.
"""

from __future__ import annotations

import math
import re
from datetime import datetime

from jarvis.memory.embeddings import cosine
from jarvis.memory.models import Memory, Recall

_WORD_RE = re.compile(r"[a-z0-9'-]+")

HALF_LIFE_DAYS = 45.0  # a memory's recency weight halves over this span

# Relevance weights. Lexical leads because proper nouns and identifiers are what
# people actually search for, and embeddings blur exactly those.
W_LEXICAL = 0.45
W_SEMANTIC = 0.40
W_RECENCY = 0.15


def tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def lexical_score(query_tokens: set[str], memory: Memory) -> float:
    """Share of the query's terms present in the memory."""
    if not query_tokens:
        return 0.0
    haystack = tokenize(memory.content) | {tag.lower() for tag in memory.tags}
    overlap = query_tokens & haystack
    if not overlap:
        return 0.0
    # Normalised by query length, so matching 3 of 4 terms beats 3 of 10
    # regardless of how long the memory itself is.
    return len(overlap) / len(query_tokens)


def recency_score(memory: Memory, now: datetime) -> float:
    if not memory.created_at:
        return 0.5
    created = memory.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=now.tzinfo)
    age_days = (now - created).total_seconds() / 86_400
    return math.exp(-math.log(2) * max(age_days, 0.0) / HALF_LIFE_DAYS)


def score(
    memory: Memory,
    *,
    query_tokens: set[str],
    query_vector: list[float],
    now: datetime,
) -> Recall:
    """Blend the three signals, then weight the result by the memory's salience."""
    lexical = lexical_score(query_tokens, memory)
    semantic = max(0.0, cosine(query_vector, memory.embedding or []))
    recency = recency_score(memory, now)

    relevance = W_LEXICAL * lexical + W_SEMANTIC * semantic + W_RECENCY * recency
    # Salience scales rather than adds: a recorded decision outranks small talk
    # that happens to match, but cannot manufacture relevance on its own.
    weighted = relevance * (0.6 + 0.4 * memory.salience)

    return Recall(
        memory=memory,
        score=round(weighted, 6),
        lexical=round(lexical, 4),
        semantic=round(semantic, 4),
        recency=round(recency, 4),
    )


def rank(
    memories: list[Memory],
    *,
    query: str,
    query_vector: list[float],
    now: datetime,
    limit: int,
    min_score: float = 0.05,
) -> list[Recall]:
    """Score a candidate set and return the best, deterministically ordered."""
    query_tokens = tokenize(query)
    results = [
        recall
        for memory in memories
        if (
            recall := score(memory, query_tokens=query_tokens, query_vector=query_vector, now=now)
        ).score
        >= min_score
    ]
    results.sort(key=lambda r: (-r.score, r.memory.id))
    return results[:limit]
