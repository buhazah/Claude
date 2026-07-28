"""Composition root.

Every dependency is wired exactly once, here. Nothing else in the codebase
constructs a provider, store or registry, which is what makes the whole system
substitutable in tests: build a ``Jarvis`` with a frozen clock and an echo
provider and you have the real system, deterministically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

from jarvis.agents.orchestrator import Orchestrator
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.runtime import AgentRuntime
from jarvis.config import Settings, get_settings
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.redis_bus import RedisEventBus
from jarvis.knowledge.ingest import Ingestor
from jarvis.knowledge.store import InMemoryKnowledgeStore, KnowledgeStore, SqlKnowledgeStore
from jarvis.llm.base import LLMProvider
from jarvis.llm.providers.anthropic import AnthropicProvider
from jarvis.llm.providers.echo import EchoProvider
from jarvis.llm.providers.openai import LocalProvider, OpenAIProvider
from jarvis.llm.router import ModelRouter
from jarvis.memory.embeddings import Embedder, HashingEmbedder, HostedEmbedder
from jarvis.memory.sql_store import SqlMemoryStore
from jarvis.memory.store import InMemoryStore, MemoryStore
from jarvis.observability.audit import AuditLog, NullAuditLog, SqlAuditLog
from jarvis.persistence.db import Database
from jarvis.runs.models import RunStore
from jarvis.runs.sql_store import SqlRunStore
from jarvis.tools.approvals import ApprovalBroker
from jarvis.tools.builtins import register_builtins
from jarvis.tools.mcp import MCPManager, MCPServerConfig
from jarvis.tools.registry import Grant, Permission, ToolRegistry
from jarvis.tools.system import Workspace, register_system_tools
from jarvis.voice.ports import SilentSpeaker, Speaker
from jarvis.voice.providers.hosted import HostedSpeaker, HostedTranscriber
from jarvis.voice.session import VoiceSession
from jarvis.voice.wake import WakeWordDetector
from jarvis.workflows.catalog import starter_workflows
from jarvis.workflows.engine import WorkflowEngine
from jarvis.workflows.store import InMemoryWorkflowStore, SqlWorkflowStore, WorkflowStore
from jarvis.workflows.triggers import Scheduler

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


def parse_mcp_servers(raw: str) -> list[MCPServerConfig]:
    """Parse the MCP server list. Malformed config disables connectors, not Jarvis."""
    if not raw.strip():
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("mcp_config_invalid", error=str(exc))
        return []

    servers: list[MCPServerConfig] = []
    for entry in entries if isinstance(entries, list) else []:
        try:
            servers.append(
                MCPServerConfig(
                    name=entry["name"],
                    command=list(entry["command"]),
                    env=dict(entry.get("env", {})),
                    permission=Permission[entry.get("permission", "SENSITIVE").upper()],
                    enabled=bool(entry.get("enabled", True)),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("mcp_server_skipped", entry=entry, error=str(exc))
    return servers


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
    knowledge: KnowledgeStore
    ingestor: Ingestor
    workflows: WorkflowStore
    engine: WorkflowEngine
    scheduler: Scheduler
    speaker: Speaker
    transcriber: HostedTranscriber
    approvals: ApprovalBroker
    audit: AuditLog
    workspace: Workspace
    mcp: MCPManager
    database: Database | None = None

    @property
    def provider_names(self) -> list[str]:
        return sorted(self.router.providers)

    def voice_session(self, *, require_wake_word: bool | None = None) -> VoiceSession:
        """A fresh voice conversation. One per connected client."""
        return VoiceSession(
            orchestrator=self.orchestrator,
            runtime=self.runtime,
            agents=self.agents,
            speaker=self.speaker,
            bus=self.bus,
            require_wake_word=(
                self.settings.require_wake_word if require_wake_word is None else require_wake_word
            ),
            wake=WakeWordDetector((self.settings.wake_word, f"hey {self.settings.wake_word}")),
        )

    @property
    def storage(self) -> str:
        return self.database.dialect if self.database else "memory"

    async def start(self) -> None:
        """Open connections, prepare storage, mount connectors. Idempotent."""
        # SQLite is created in place; Postgres schema is owned by Alembic, so a
        # server deployment must be migrated before it is started.
        if self.database is not None and not self.database.is_postgres:
            await self.database.create_all()
        if isinstance(self.bus, RedisEventBus):
            await self.bus.start()
        for config in parse_mcp_servers(self.settings.mcp_servers):
            await self.mcp.add(config)

        # Seed the starter workflows once, so the builder opens onto something
        # real. They are ordinary rows afterwards — editable and deletable.
        if not await self.workflows.all():
            for workflow in starter_workflows():
                await self.workflows.save(workflow)
        if self.settings.enable_scheduler:
            await self.scheduler.start()

    async def stop(self) -> None:
        await self.scheduler.stop()
        await self.mcp.stop_all()
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
    knowledge: KnowledgeStore
    if settings.database_url:
        database = Database(settings.database_url, echo=settings.database_echo)
        memory = SqlMemoryStore(database, embedder=embedder, bus=bus, clock=clock)
        runs = SqlRunStore(database, clock=clock)
        knowledge = SqlKnowledgeStore(database, embedder=embedder, bus=bus, clock=clock)
    else:
        memory = InMemoryStore(embedder=embedder, bus=bus, clock=clock)
        runs = RunStore(clock=clock)
        knowledge = InMemoryKnowledgeStore(embedder=embedder, bus=bus, clock=clock)
    ingestor = Ingestor(knowledge)
    workflows: WorkflowStore = (
        SqlWorkflowStore(database, clock=clock) if database else InMemoryWorkflowStore(clock=clock)
    )
    audit: AuditLog = SqlAuditLog(database, clock=clock) if database else NullAuditLog()
    approvals = ApprovalBroker(bus=bus, clock=clock, timeout_s=settings.approval_timeout_s)
    tools = ToolRegistry(
        bus=bus,
        # Default posture: safe tools run freely, sensitive ones are permitted
        # and audited, dangerous ones suspend for an explicit human decision.
        #
        # The ceiling must be DANGEROUS, not SENSITIVE: max_permission is what
        # may be *requested*, and auto_approve is what may happen *without
        # asking*. Capping at SENSITIVE would flatly deny dangerous tools and
        # make the approval gate unreachable.
        grants=[Grant("*", Permission.DANGEROUS, auto_approve=False)],
        approvals=approvals,
        audit=audit,
    )
    workspace = Workspace(settings.workspace_dir)
    register_builtins(tools, memory, knowledge)
    register_system_tools(tools, workspace)
    mcp = MCPManager(tools)

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

    engine = WorkflowEngine(
        store=workflows,
        orchestrator=orchestrator,
        runtime=runtime,
        agents=agents,
        tools=tools,
        approvals=approvals,
        bus=bus,
        clock=clock,
    )
    scheduler = Scheduler(store=workflows, engine=engine, bus=bus, clock=clock)

    # Hosted speech when a key is configured; otherwise recognition happens in
    # the browser and synthesis is silent. The session is identical either way.
    speaker: Speaker = (
        HostedSpeaker(
            settings.speech_api_key,
            model=settings.tts_model,
            voice=settings.tts_voice,
            base_url=settings.speech_base_url,
        )
        if settings.speech_api_key
        else SilentSpeaker(realtime=settings.realtime_speech)
    )
    transcriber = HostedTranscriber(
        settings.speech_api_key, model=settings.stt_model, base_url=settings.speech_base_url
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
        knowledge=knowledge,
        ingestor=ingestor,
        workflows=workflows,
        engine=engine,
        scheduler=scheduler,
        speaker=speaker,
        transcriber=transcriber,
        approvals=approvals,
        audit=audit,
        workspace=workspace,
        mcp=mcp,
        database=database,
    )
