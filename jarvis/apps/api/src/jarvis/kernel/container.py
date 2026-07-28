"""Composition root.

Every dependency is wired exactly once, here. Nothing else in the codebase
constructs a provider, store or registry, which is what makes the whole system
substitutable in tests: build a ``Jarvis`` with a frozen clock and an echo
provider and you have the real system, deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from jarvis.agents.orchestrator import Orchestrator
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.runtime import AgentRuntime
from jarvis.config import Settings, get_settings
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.redis_bus import RedisEventBus
from jarvis.llm.base import LLMProvider
from jarvis.llm.providers.anthropic import AnthropicProvider
from jarvis.llm.providers.echo import EchoProvider
from jarvis.llm.providers.openai import LocalProvider, OpenAIProvider
from jarvis.llm.router import ModelRouter
from jarvis.memory.embeddings import Embedder, HashingEmbedder, HostedEmbedder
from jarvis.memory.sql_store import SqlMemoryStore
from jarvis.memory.store import InMemoryStore, MemoryStore
from jarvis.persistence.db import Database
from jarvis.runs.models import RunStore
from jarvis.runs.sql_store import SqlRunStore
from jarvis.tools.builtins import register_builtins
from jarvis.tools.registry import Grant, Permission, ToolRegistry

log = structlog.get_logger(__name__)


def build_providers(settings: Settings) -> list[LLMProvider]:
    """Register every configured provider. Echo is always last and always present."""
    providers: list[LLMProvider] = []
    if settings.anthropic_api_key:
        providers.append(AnthropicProvider(settings.anthropic_api_key))
    if settings.openai_api_key:
        providers.append(OpenAIProvider(settings.openai_api_key))
    if settings.enable_local_llm:
        providers.append(LocalProvider(settings.local_llm_base_url))
    providers.append(EchoProvider())
    return providers


def build_embedder(settings: Settings) -> Embedder:
    """Hosted embeddings when a key is configured, deterministic local ones otherwise."""
    if settings.embedding_api_key:
        return HostedEmbedder(
            settings.embedding_api_key,
            model=settings.embedding_model,
            base_url=settings.embedding_base_url,
        )
    return HashingEmbedder()


@dataclass(slots=True)
class Jarvis:
    """The assembled system. One object the API layer depends on."""

    settings: Settings
    bus: EventBus
    router: ModelRouter
    agents: AgentRegistry
    memory: MemoryStore
    runs: RunStore
    tools: ToolRegistry
    runtime: AgentRuntime
    orchestrator: Orchestrator
    database: Database | None = None

    @property
    def provider_names(self) -> list[str]:
        return sorted(self.router.providers)

    @property
    def storage(self) -> str:
        return self.database.dialect if self.database else "memory"

    async def start(self) -> None:
        """Open connections and prepare storage. Idempotent."""
        # SQLite is created in place; Postgres schema is owned by Alembic, so a
        # server deployment must be migrated before it is started.
        if self.database is not None and not self.database.is_postgres:
            await self.database.create_all()
        if isinstance(self.bus, RedisEventBus):
            await self.bus.start()

    async def stop(self) -> None:
        if isinstance(self.bus, RedisEventBus):
            await self.bus.stop()
        if self.database is not None:
            await self.database.dispose()


def build(
    settings: Settings | None = None,
    *,
    providers: list[LLMProvider] | None = None,
    clock: Clock = SYSTEM_CLOCK,
) -> Jarvis:
    settings = settings or get_settings()

    bus: EventBus = (
        RedisEventBus(settings.redis_url, clock=clock)
        if settings.redis_url
        else EventBus(clock=clock)
    )
    router = ModelRouter(providers or build_providers(settings), bus=bus, clock=clock)
    agents = AgentRegistry()
    embedder = build_embedder(settings)

    # One switch decides durability. Everything downstream is written against
    # the ports, so nothing else in the system knows which branch was taken.
    database: Database | None = None
    memory: MemoryStore
    runs: RunStore
    if settings.database_url:
        database = Database(settings.database_url, echo=settings.database_echo)
        memory = SqlMemoryStore(database, embedder=embedder, bus=bus, clock=clock)
        runs = SqlRunStore(database, clock=clock)
    else:
        memory = InMemoryStore(embedder=embedder, bus=bus, clock=clock)
        runs = RunStore(clock=clock)
    tools = ToolRegistry(
        bus=bus,
        # Default posture: safe tools run freely, sensitive ones are permitted
        # and audited, dangerous ones need an explicit per-tool grant.
        grants=[Grant("*", Permission.SENSITIVE)],
    )
    register_builtins(tools, memory)

    runtime = AgentRuntime(
        router=router,
        registry=agents,
        memory=memory,
        runs=runs,
        tools=tools,
        bus=bus,
        clock=clock,
    )
    orchestrator = Orchestrator(
        registry=agents,
        runtime=runtime,
        router=router,
        runs=runs,
        bus=bus,
        use_arbiter=settings.use_llm_arbiter,
    )

    log.info(
        "jarvis_built",
        providers=sorted(router.providers),
        models=len(router.catalog()),
        agents=len(agents),
        tools=len(tools.all()),
        storage=database.dialect if database else "memory",
        bus="redis" if settings.redis_url else "in-process",
        embedder=type(embedder).__name__,
    )
    return Jarvis(
        settings=settings,
        bus=bus,
        router=router,
        agents=agents,
        memory=memory,
        runs=runs,
        tools=tools,
        runtime=runtime,
        orchestrator=orchestrator,
        database=database,
    )
