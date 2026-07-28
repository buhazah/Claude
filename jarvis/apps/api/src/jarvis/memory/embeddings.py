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
from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)

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


class HostedEmbedder:
    """Embeddings from an OpenAI-compatible ``/embeddings`` endpoint.

    Vectors are truncated and re-normalised to ``DIMENSIONS`` so hosted and
    local embeddings share one column width — you can switch backends without
    a migration, though existing vectors must be re-embedded to be comparable.

    Falls back to the hashing embedder on any failure: degraded recall quality
    beats a memory subsystem that stops accepting writes because a vendor is
    having an outage.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        dimensions: int = DIMENSIONS,
        client: Any = None,
    ) -> None:
        self.dimensions = dimensions
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._fallback = HashingEmbedder(dimensions)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import httpx

        client = self._client or httpx.AsyncClient(timeout=30.0)
        owns_client = self._client is None
        try:
            response = await client.post(
                f"{self._base_url}/embeddings",
                headers={"authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "input": texts, "dimensions": self.dimensions},
            )
            response.raise_for_status()
            data = response.json()["data"]
            return [_unit(item["embedding"][: self.dimensions]) for item in data]
        except Exception as exc:
            log.warning("hosted_embedding_failed", error=str(exc), model=self._model)
            return await self._fallback.embed(texts)
        finally:
            if owns_client:
                await client.aclose()


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else list(vector)
