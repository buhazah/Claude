"""Store contract tests.

Every store implementation runs the *same* suite. That is the point: memory,
SQLite and Postgres must be behaviourally indistinguishable to the runtime, and
the only way to know that is to assert it against all three.

Postgres is included whenever ``JARVIS_TEST_POSTGRES_URL`` points at a live
server with pgvector, and skipped otherwise, so the suite still runs offline.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from jarvis.config import get_settings
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import FrozenClock
from jarvis.memory.models import MemoryKind
from jarvis.memory.sql_store import SqlMemoryStore
from jarvis.memory.store import InMemoryStore
from jarvis.persistence.db import Database, normalise_url
from jarvis.runs.models import RunState, RunStore, StepKind
from jarvis.runs.sql_store import SqlRunStore

POSTGRES_URL = os.getenv("JARVIS_TEST_POSTGRES_URL", "")
needs_postgres = pytest.mark.skipif(not POSTGRES_URL, reason="JARVIS_TEST_POSTGRES_URL not set")

BACKENDS = ["memory", "sqlite"] + (["postgres"] if POSTGRES_URL else [])


@pytest.fixture
async def database(request: pytest.FixtureRequest, tmp_path) -> AsyncIterator[Database]:
    """A clean database per test, for whichever dialect is being exercised."""
    backend = getattr(request, "param", "sqlite")
    url = POSTGRES_URL if backend == "postgres" else f"sqlite+aiosqlite:///{tmp_path}/test.db"
    db = Database(url)
    if backend == "postgres":
        # Postgres is a shared server: drop and rebuild so tests never inherit
        # rows from each other.
        from jarvis.persistence.models import Base

        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    await db.create_all()
    try:
        yield db
    finally:
        await db.dispose()


@pytest.fixture(params=BACKENDS)
async def memory_store(request: pytest.FixtureRequest, tmp_path, clock: FrozenClock):
    """The same memory-store contract, once per backend."""
    backend = request.param
    if backend == "memory":
        yield InMemoryStore(clock=clock)
        return

    url = POSTGRES_URL if backend == "postgres" else f"sqlite+aiosqlite:///{tmp_path}/mem.db"
    db = Database(url)
    if backend == "postgres":
        from jarvis.persistence.models import Base

        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    await db.create_all()
    try:
        yield SqlMemoryStore(db, clock=clock)
    finally:
        await db.dispose()


# ── URL handling ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("sqlite:///jarvis.db", "sqlite+aiosqlite:///jarvis.db"),
        ("sqlite+aiosqlite:///jarvis.db", "sqlite+aiosqlite:///jarvis.db"),
    ],
)
def test_urls_are_normalised_to_async_drivers(given: str, expected: str) -> None:
    assert normalise_url(given) == expected


# ── Memory store contract ─────────────────────────────────────────────────────


async def test_remember_round_trips(memory_store) -> None:
    stored = await memory_store.remember("We decided to ship on Friday")
    fetched = await memory_store.get(stored.id)

    assert fetched is not None
    assert fetched.content == stored.content
    assert fetched.kind is MemoryKind.DECISION
    assert fetched.embedding is not None
    assert len(fetched.embedding) == 256


async def test_remember_rejects_empty_content(memory_store) -> None:
    with pytest.raises(ValueError, match="empty"):
        await memory_store.remember("   ")


async def test_search_ranks_the_relevant_memory_first(memory_store) -> None:
    await memory_store.remember("The Ember app uses Supabase for auth and storage")
    await memory_store.remember("I like oat milk in coffee")
    await memory_store.remember("Weather in Lisbon is mild in October")

    results = await memory_store.search("what database does Ember use")
    assert results
    assert "Supabase" in results[0].memory.content
    assert results[0].score > 0


async def test_search_exposes_the_signals_behind_a_recall(memory_store) -> None:
    await memory_store.remember("Deploy key for project zephyr-7 lives in the vault")
    results = await memory_store.search("zephyr-7")

    assert results[0].lexical > 0
    assert 0.0 <= results[0].semantic <= 1.0
    assert 0.0 < results[0].recency <= 1.0


async def test_scope_limits_recall_to_the_agent_plus_global(memory_store) -> None:
    await memory_store.remember("Sales pipeline notes about acme", scope="sales")
    await memory_store.remember("Coding notes about the acme repo", scope="coding")
    await memory_store.remember("Acme is a customer", scope="global")

    results = await memory_store.search("acme", scope="sales")
    assert {r.memory.scope for r in results} == {"sales", "global"}


async def test_kind_filter_narrows_results(memory_store) -> None:
    await memory_store.remember("I prefer dark mode everywhere")
    await memory_store.remember("Dark matter makes up most of the universe")

    results = await memory_store.search("dark", kinds=[MemoryKind.PREFERENCE])
    assert len(results) == 1
    assert results[0].memory.kind is MemoryKind.PREFERENCE


async def test_search_records_access(memory_store) -> None:
    stored = await memory_store.remember("Anna is the designer on the Ember project")
    await memory_store.search("who is Anna")

    fetched = await memory_store.get(stored.id)
    assert fetched is not None
    assert fetched.access_count == 1
    assert fetched.last_accessed_at is not None


async def test_forget_removes_a_memory(memory_store) -> None:
    stored = await memory_store.remember("Temporary note about the offsite")
    assert await memory_store.forget(stored.id) is True
    assert await memory_store.get(stored.id) is None
    assert await memory_store.forget(stored.id) is False


async def test_superseded_memories_stop_surfacing(memory_store) -> None:
    old = await memory_store.remember("The API base url is api.old.example")
    await memory_store.supersede(old.id, "The API base url is api.new.example")

    contents = [r.memory.content for r in await memory_store.search("api base url")]
    assert any("api.new.example" in c for c in contents)
    assert not any("api.old.example" in c for c in contents)


async def test_all_returns_newest_first_and_excludes_superseded(memory_store) -> None:
    first = await memory_store.remember("First durable note about pricing")
    await memory_store.remember("Second durable note about hiring")
    await memory_store.supersede(first.id, "Revised note about pricing")

    everything = await memory_store.all()
    assert len(everything) == 2
    assert not any("First durable" in m.content for m in everything)


async def test_count_reflects_writes(memory_store) -> None:
    assert await memory_store.count() == 0
    await memory_store.remember("something worth keeping about the roadmap")
    assert await memory_store.count() == 1


async def test_search_on_an_empty_store_returns_nothing(memory_store) -> None:
    assert await memory_store.search("anything at all") == []


async def test_writes_and_recalls_publish_events(tmp_path, clock: FrozenClock) -> None:
    bus = EventBus(clock=clock)
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/events.db")
    await db.create_all()
    store = SqlMemoryStore(db, bus=bus, clock=clock)
    sub = bus.subscribe("memory.**")

    await store.remember("Something worth keeping about the roadmap")
    await store.search("roadmap")
    await db.dispose()

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics == ["memory.written", "memory.recalled"]


async def test_memories_survive_a_reconnect(tmp_path, clock: FrozenClock) -> None:
    """The actual point of persistence: a restart must not lose anything."""
    url = f"sqlite+aiosqlite:///{tmp_path}/durable.db"

    first = Database(url)
    await first.create_all()
    stored = await SqlMemoryStore(first, clock=clock).remember("The launch date is September 12")
    await first.dispose()

    second = Database(url)
    reopened = SqlMemoryStore(second, clock=clock)
    found = await reopened.search("when is the launch")
    fetched = await reopened.get(stored.id)
    await second.dispose()

    assert fetched is not None and fetched.id == stored.id
    assert found and "September 12" in found[0].memory.content


# ── Run store contract ────────────────────────────────────────────────────────


async def test_run_persists_with_its_steps(database: Database, clock: FrozenClock) -> None:
    store = SqlRunStore(database, clock=clock)
    run = store.create(request="research competitors", agent_id="research")

    step = store.start_step(run, StepKind.MEMORY, "recall")
    store.end_step(step, hits=3)
    model_step = store.start_step(run, StepKind.MODEL, "completion")
    store.end_step(model_step, cost_usd=0.0021, tokens=350, model="claude-sonnet-5")
    store.finish(run, state=RunState.SUCCEEDED, output="done")
    await store.persist(run)

    fetched = await SqlRunStore(database, clock=clock).get(run.id)
    assert fetched is not None
    assert fetched.state is RunState.SUCCEEDED
    assert fetched.output == "done"
    assert [s.kind for s in fetched.steps] == [StepKind.MEMORY, StepKind.MODEL]
    assert fetched.steps[1].detail["model"] == "claude-sonnet-5"
    assert fetched.cost_usd == pytest.approx(0.0021)
    assert fetched.tokens == 350


async def test_persist_is_idempotent(database: Database, clock: FrozenClock) -> None:
    store = SqlRunStore(database, clock=clock)
    run = store.create(request="a task", agent_id="planner")
    store.start_step(run, StepKind.MODEL, "completion")

    await store.persist(run)
    store.finish(run, state=RunState.SUCCEEDED, output="finished")
    await store.persist(run)

    fetched = await store.get(run.id)
    assert fetched is not None
    assert fetched.state is RunState.SUCCEEDED
    assert len(fetched.steps) == 1  # steps replaced, not duplicated


async def test_failed_runs_keep_their_error(database: Database, clock: FrozenClock) -> None:
    store = SqlRunStore(database, clock=clock)
    run = store.create(request="doomed", agent_id="research")
    store.finish(run, state=RunState.FAILED, error="provider is down")
    await store.persist(run)

    fetched = await SqlRunStore(database, clock=clock).get(run.id)
    assert fetched is not None
    assert fetched.state is RunState.FAILED
    assert fetched.error == "provider is down"


async def test_listing_merges_live_and_persisted_runs(
    database: Database, clock: FrozenClock
) -> None:
    store = SqlRunStore(database, clock=clock)
    done = store.create(request="finished work", agent_id="research")
    store.finish(done, state=RunState.SUCCEEDED)
    await store.persist(done)

    # Still streaming, never checkpointed — the UI must still see it.
    in_flight = store.create(request="still running", agent_id="coding")
    in_flight.state = RunState.RUNNING

    listed = await store.list()
    assert [r.request for r in listed] == ["still running", "finished work"]


async def test_runs_can_be_filtered_by_agent(database: Database, clock: FrozenClock) -> None:
    store = SqlRunStore(database, clock=clock)
    for agent in ("research", "coding", "research"):
        run = store.create(request=f"{agent} task", agent_id=agent)
        store.finish(run, state=RunState.SUCCEEDED)
        await store.persist(run)

    assert len(await store.list(agent_id="research")) == 2
    assert len(await store.list(agent_id="coding")) == 1


async def test_unknown_run_is_none(database: Database, clock: FrozenClock) -> None:
    assert await SqlRunStore(database, clock=clock).get("run_missing") is None


async def test_in_memory_run_store_satisfies_the_same_contract(clock: FrozenClock) -> None:
    store = RunStore(clock=clock)
    run = store.create(request="a task", agent_id="planner")
    store.finish(run, state=RunState.SUCCEEDED, output="ok")
    await store.persist(run)  # no-op, but must exist and be awaitable

    assert (await store.get(run.id)) is run
    assert [r.id for r in await store.list()] == [run.id]


# ── Postgres-specific behaviour ───────────────────────────────────────────────


@needs_postgres
async def test_postgres_uses_a_real_vector_column() -> None:
    db = Database(POSTGRES_URL)
    from jarvis.persistence.models import Base

    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await db.create_all()

    from sqlalchemy import text

    async with db.session() as session:
        result = await session.execute(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'memories' AND column_name = 'embedding'"
            )
        )
        assert result.scalar_one() == "vector"
    await db.dispose()


@needs_postgres
async def test_postgres_ann_and_lexical_candidates_are_unioned(clock: FrozenClock) -> None:
    """An exact identifier must reach the ranker even if it is far away in vector space."""
    db = Database(POSTGRES_URL)
    from jarvis.persistence.models import Base

    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await db.create_all()
    store = SqlMemoryStore(db, clock=clock)

    for i in range(60):
        await store.remember(f"Routine note number {i} about daily standup logistics")
    await store.remember("Deploy key for project zephyr-7 lives in the vault")

    results = await store.search("zephyr-7", limit=3)
    await db.dispose()

    assert results
    assert "zephyr-7" in results[0].memory.content


# ── Migrations ────────────────────────────────────────────────────────────────


def _alembic_config(url: str):
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "src/jarvis/persistence/migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_migrations_build_the_same_schema_as_the_models(tmp_path) -> None:
    """A migration that has drifted from the models is worse than none at all.

    Running Alembic and ``create_all`` against two fresh databases must produce
    the same tables and columns — otherwise a server deployment quietly differs
    from every local one.
    """
    from alembic import command
    from sqlalchemy import create_engine, inspect

    from jarvis.persistence.models import Base

    migrated_path = tmp_path / "migrated.db"
    os.environ["JARVIS_DATABASE_URL"] = f"sqlite:///{migrated_path}"
    get_settings.cache_clear()
    try:
        command.upgrade(_alembic_config(f"sqlite:///{migrated_path}"), "head")
    finally:
        os.environ.pop("JARVIS_DATABASE_URL", None)
        get_settings.cache_clear()

    declared_path = tmp_path / "declared.db"
    declared_engine = create_engine(f"sqlite:///{declared_path}")
    Base.metadata.create_all(declared_engine)

    migrated = inspect(create_engine(f"sqlite:///{migrated_path}"))
    declared = inspect(declared_engine)

    migrated_tables = set(migrated.get_table_names()) - {"alembic_version"}
    assert migrated_tables == set(declared.get_table_names())

    for table in sorted(migrated_tables):
        assert {c["name"] for c in migrated.get_columns(table)} == {
            c["name"] for c in declared.get_columns(table)
        }, f"column drift in {table}"


@needs_postgres
def test_migrations_apply_cleanly_to_postgres() -> None:
    from alembic import command
    from sqlalchemy import create_engine, inspect, text

    sync_url = POSTGRES_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))

    os.environ["JARVIS_DATABASE_URL"] = sync_url
    get_settings.cache_clear()
    try:
        command.upgrade(_alembic_config(sync_url), "head")
    finally:
        os.environ.pop("JARVIS_DATABASE_URL", None)
        get_settings.cache_clear()

    tables = set(inspect(engine).get_table_names())
    assert {"memories", "runs", "run_steps", "agent_metrics", "audit_log"} <= tables

    with engine.connect() as connection:
        index = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_memories_embedding_hnsw'")
        ).scalar_one()
    assert "hnsw" in index and "vector_cosine_ops" in index
