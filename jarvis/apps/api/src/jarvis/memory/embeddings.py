"""Embedding port with a deterministic offline implementation.

``HashingEmbedder`` is a real, if modest, embedding model: a hashed
bag-of-character-ngrams projected onto a fixed-dimension unit vector. It gives
genuine (if coarse) semantic-ish similarity with no network, which keeps recall
ranking testable and keeps Jarvis useful in fully local mode. A hosted
embedder implements the same protocol and swaps in by config.
"""

from __future__ import annotations

import hashlib
import math
import re
from itertools import pairwise
from typing import Protocol

_WORD_RE = re.compile(r"[a-z0-9']+")
DIMENSIONS = 256


class Embedder(Protocol):
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _features(text: str) -> list[str]:
    words = _WORD_RE.findall(text.lower())
    features = list(words)
    features += [f"{a}_{b}" for a, b in pairwise(words)]
    for word in words:
        if len(word) > 4:
            features += [word[i : i + 4] for i in range(len(word) - 3)]
    return features


class HashingEmbedder:
    """Deterministic, dependency-free, and identical across processes."""

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self.dimensions = dimensions

    def embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        features = _features(text)
        if not features:
            return vector
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))  # inputs are unit vectors
