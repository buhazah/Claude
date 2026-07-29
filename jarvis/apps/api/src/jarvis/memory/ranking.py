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


# Words that carry no retrieval signal. Without this list, "what are the
# margins like" scored a memory about consulting work exactly as highly as the
# one stating the margin, because both contain "the" and the score was share of
# query terms matched. A stopword hit is not a hit.
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "so",
        "as",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "from",
        "by",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "out",
        "up",
        "down",
        "off",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "them",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "too",
        "very",
        "can",
        "will",
        "just",
        "should",
        "now",
        "like",
        "get",
        "got",
        "make",
        "made",
        "want",
        "need",
        "would",
        "could",
        "please",
        "tell",
        "say",
        "said",
        "thing",
        "things",
        "stuff",
    ]
)

# Below this a prefix match is noise: "op" would match "operations", "opening"
# and "opposite" equally.
MIN_PREFIX = 4


def tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def content_tokens(text: str) -> set[str]:
    """Tokens worth retrieving on. Falls back to everything for a query that is
    entirely stopwords, so "how are you" still scores something rather than
    dividing by zero and silently matching nothing."""
    tokens = tokenize(text)
    meaningful = tokens - STOPWORDS
    return meaningful or tokens


def _matches(term: str, haystack: set[str]) -> bool:
    """Whether a query term is present, allowing for the endings English adds.

    Exact set overlap missed "margins" against "margin" and "meetings" against
    "meeting" — which is how a memory stating the gross margin failed to be
    recalled by a question about margins. The router has matched by prefix
    since M1; recall matching by equality meant the same system held two
    different opinions about what a word is, and the weaker one governed what
    the user could remember.
    """
    if term in haystack:
        return True
    if len(term) < MIN_PREFIX:
        return False
    return any(
        word.startswith(term) or (len(word) >= MIN_PREFIX and term.startswith(word))
        for word in haystack
    )


def lexical_score(query_tokens: set[str], memory: Memory) -> float:
    """Share of the query's *content* terms present in the memory."""
    if not query_tokens:
        return 0.0
    haystack = tokenize(memory.content) | {tag.lower() for tag in memory.tags}
    hits = sum(1 for term in query_tokens if _matches(term, haystack))
    if not hits:
        return 0.0
    # Normalised by query length, so matching 3 of 4 terms beats 3 of 10
    # regardless of how long the memory itself is.
    return hits / len(query_tokens)


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
    query_tokens = content_tokens(query)
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
