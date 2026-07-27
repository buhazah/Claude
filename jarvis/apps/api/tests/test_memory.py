from __future__ import annotations

import pytest

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import FrozenClock
from jarvis.memory.embeddings import HashingEmbedder, cosine
from jarvis.memory.models import MemoryKind, MemoryTier, categorize, salience_for
from jarvis.memory.store import InMemoryStore


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I prefer short emails with no greeting", MemoryKind.PREFERENCE),
        ("We decided to use Postgres over Mongo", MemoryKind.DECISION),
        ("The migration failed because the index was not unique", MemoryKind.MISTAKE),
        ("My goal is to reach 10k MRR by Q3", MemoryKind.GOAL),
        ("Ember is a dating app project I am building", MemoryKind.PROJECT),
        ("The capital of France is Paris", MemoryKind.FACT),
    ],
)
def test_categorisation_infers_kind_from_text(text: str, expected: MemoryKind) -> None:
    assert categorize(text) is expected


def test_decision_outranks_preference_when_both_patterns_appear() -> None:
    # Rule order matters: the more specific signal must win.
    assert categorize("I decided I prefer Postgres") is MemoryKind.DECISION


def test_salience_prefers_durable_kinds_over_chatter() -> None:
    assert salience_for(MemoryKind.DECISION, "x" * 50) > salience_for(
        MemoryKind.CONVERSATION, "x" * 50
    )


def test_embeddings_are_unit_length_and_deterministic() -> None:
    embedder = HashingEmbedder()
    a = embedder.embed_one("quarterly revenue forecast")
    b = embedder.embed_one("quarterly revenue forecast")
    assert a == b
    assert cosine(a, b) == pytest.approx(1.0, abs=1e-6)


def test_related_text_scores_higher_than_unrelated() -> None:
    embedder = HashingEmbedder()
    query = embedder.embed_one("revenue forecast for next quarter")
    related = embedder.embed_one("quarterly revenue projection")
    unrelated = embedder.embed_one("the dog slept on the porch")
    assert cosine(query, related) > cosine(query, unrelated)


async def test_remember_assigns_kind_tier_and_salience(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    memory = await store.remember("We decided to ship on Friday")
    assert memory.kind is MemoryKind.DECISION
    assert memory.tier is MemoryTier.PROCEDURAL
    assert memory.salience > 0.5
    assert memory.created_at == clock.now()
    assert memory.embedding is not None


async def test_remember_rejects_empty_content(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    with pytest.raises(ValueError, match="empty"):
        await store.remember("   ")


async def test_search_ranks_the_relevant_memory_first(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    await store.remember("The Ember app uses Supabase for auth and storage")
    await store.remember("I like oat milk in coffee")
    await store.remember("Weather in Lisbon is mild in October")

    results = await store.search("what database does Ember use")
    assert results
    assert "Supabase" in results[0].memory.content


async def test_lexical_signal_finds_identifiers_embeddings_would_blur(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    await store.remember("Deploy key for project zephyr-7 lives in the vault")
    await store.remember("General notes about deployment and infrastructure")

    results = await store.search("zephyr-7")
    assert "zephyr-7" in results[0].memory.content
    assert results[0].lexical > 0


async def test_recency_decays_older_memories(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    old = await store.remember("Pricing is 29 dollars per month")
    clock.advance(90 * 86_400)  # two half-lives
    new = await store.remember("Pricing is 49 dollars per month")

    results = await store.search("what is the pricing")
    ordering = [r.memory.id for r in results]
    assert ordering.index(new.id) < ordering.index(old.id)


async def test_scope_limits_recall_to_the_agent_plus_global(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    await store.remember("Sales pipeline notes about acme", scope="sales")
    await store.remember("Coding notes about acme repo", scope="coding")
    await store.remember("Acme is a customer", scope="global")

    results = await store.search("acme", scope="sales")
    scopes = {r.memory.scope for r in results}
    assert scopes == {"sales", "global"}


async def test_kind_filter_narrows_results(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    await store.remember("I prefer dark mode everywhere")
    await store.remember("Dark matter makes up most of the universe")

    results = await store.search("dark", kinds=[MemoryKind.PREFERENCE])
    assert len(results) == 1
    assert results[0].memory.kind is MemoryKind.PREFERENCE


async def test_search_marks_recall_access(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    memory = await store.remember("Anna is the designer on the Ember project")
    await store.search("who is Anna")
    assert memory.access_count == 1
    assert memory.last_accessed_at == clock.now()


async def test_forget_removes_a_memory(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    memory = await store.remember("Temporary note about the offsite")
    assert await store.forget(memory.id) is True
    assert await store.get(memory.id) is None
    assert await store.forget(memory.id) is False


async def test_superseded_memories_stop_surfacing(clock: FrozenClock) -> None:
    store = InMemoryStore(clock=clock)
    old = await store.remember("The API base url is api.old.example")
    await store.supersede(old.id, "The API base url is api.new.example")

    results = await store.search("api base url")
    contents = [r.memory.content for r in results]
    assert any("api.new.example" in c for c in contents)
    assert not any("api.old.example" in c for c in contents)


async def test_writes_and_recalls_are_published_on_the_bus(clock: FrozenClock) -> None:
    bus = EventBus(clock=clock)
    store = InMemoryStore(bus=bus, clock=clock)
    sub = bus.subscribe("memory.**")

    await store.remember("Something worth keeping about the roadmap")
    await store.search("roadmap")

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics == ["memory.written", "memory.recalled"]


async def test_search_on_empty_store_returns_nothing(clock: FrozenClock) -> None:
    assert await InMemoryStore(clock=clock).search("anything") == []
