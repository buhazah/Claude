"""Pluggable embedding backends.

Priority (when JARVIS_EMBEDDING_PROVIDER=auto):
  1. OpenAI text-embedding-3-small (if OPENAI_API_KEY set)
  2. Voyage voyage-3-lite (if VOYAGE_API_KEY set)
  3. LocalHashEmbedder — deterministic, dependency-free n-gram hashing.

The local embedder is a real, working semantic-lite fallback (character
n-gram feature hashing with TF weighting and L2 norm). It gives useful
lexical-similarity retrieval offline; API embedders give true semantic
similarity. Both produce unit-norm float32 vectors so cosine similarity
is a dot product either way.
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx
import numpy as np

from ..config import settings

DIM_LOCAL = 512


class Embedder(ABC):
    name: str = "base"
    dim: int = DIM_LOCAL

    @abstractmethod
    async def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of unit-norm vectors."""


class LocalHashEmbedder(Embedder):
    name = "local-hash"
    dim = DIM_LOCAL

    _token_re = re.compile(r"[a-z0-9]+")

    def _features(self, text: str) -> dict[int, float]:
        text = text.lower()
        counts: dict[int, float] = {}
        tokens = self._token_re.findall(text)
        # Word unigrams + bigrams and character trigrams give the fallback
        # some robustness to inflection and typos.
        grams: list[str] = list(tokens)
        grams += [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        joined = " ".join(tokens)
        grams += [joined[i : i + 3] for i in range(len(joined) - 2)]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode(), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            counts[idx] = counts.get(idx, 0.0) + sign
        return counts

    async def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for idx, weight in self._features(text).items():
                # Sub-linear TF damping
                out[row, idx] += math.copysign(math.log1p(abs(weight)), weight)
            norm = np.linalg.norm(out[row])
            if norm > 0:
                out[row] /= norm
        return out


class OpenAIEmbedder(Embedder):
    name = "openai"
    dim = 1536
    MODEL = "text-embedding-3-small"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def embed(self, texts: list[str]) -> np.ndarray:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"authorization": f"Bearer {self.api_key}"},
                json={"model": self.MODEL, "input": texts},
            )
            resp.raise_for_status()
        vectors = [item["embedding"] for item in resp.json()["data"]]
        arr = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms


class VoyageEmbedder(Embedder):
    name = "voyage"
    dim = 512
    MODEL = "voyage-3-lite"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def embed(self, texts: list[str]) -> np.ndarray:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"authorization": f"Bearer {self.api_key}"},
                json={"model": self.MODEL, "input": texts},
            )
            resp.raise_for_status()
        vectors = [item["embedding"] for item in resp.json()["data"]]
        arr = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms


def build_embedder() -> Embedder:
    choice = settings.embedding_provider
    if choice == "openai" or (choice == "auto" and settings.openai_api_key):
        return OpenAIEmbedder(settings.openai_api_key)
    if choice == "voyage" or (choice == "auto" and settings.voyage_api_key):
        return VoyageEmbedder(settings.voyage_api_key)
    return LocalHashEmbedder()


embedder = build_embedder()
