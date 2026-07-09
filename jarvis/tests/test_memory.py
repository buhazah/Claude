"""Tests for embeddings and semantic memory recall/ranking."""
import numpy as np
import pytest

from server.memory.embeddings import LocalHashEmbedder


async def test_local_embedder_unit_norm():
    emb = LocalHashEmbedder()
    vecs = await emb.embed(["hello world", "the quick brown fox"])
    assert vecs.shape == (2, emb.dim)
    for v in vecs:
        assert abs(np.linalg.norm(v) - 1.0) < 1e-4


async def test_local_embedder_similarity_orders_correctly():
    emb = LocalHashEmbedder()
    vecs = await emb.embed([
        "I love building AI agents and automation",   # query-ish
        "artificial intelligence agents automation systems",  # related
        "my favorite dessert is chocolate cake",       # unrelated
    ])
    q = vecs[0]
    related = float(np.dot(q, vecs[1]))
    unrelated = float(np.dot(q, vecs[2]))
    assert related > unrelated


async def test_memory_recall_ranks_relevant_first():
    from server.db import SessionLocal, User
    from server.memory.manager import memory_manager
    from server.security import hash_password

    async with SessionLocal() as session:
        user = User(email="memtest@x.com", password_hash=hash_password("password123"))
        session.add(user)
        await session.commit()
        uid = user.id
        await memory_manager.remember(session, uid, "I run a Shopify store called Ember", kind="business")
        await memory_manager.remember(session, uid, "My favorite color is teal", kind="preference")
        await memory_manager.remember(session, uid, "I am building an AI operating system", kind="project")

        # The default fallback embedder is lexical, so query with shared
        # vocabulary; API embedders (OpenAI/Voyage) add true semantics.
        results = await memory_manager.recall(session, uid, "tell me about my Shopify store", limit=3)
        assert results
        top_content = results[0][0].content.lower()
        assert "shopify" in top_content or "ember" in top_content
