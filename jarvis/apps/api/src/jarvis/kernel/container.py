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
from jarvis.computer.policy import ComputerPolicy
from jarvis.computer.ports import Computer, UnavailableComputer
from jarvis.computer.session import ComputerSession
from jarvis.computer.tools import register_computer_tools
from jarvis.config import Settings, get_settings
from jarvis.documents.compose import DocumentComposer
from jarvis.documents.store import DocumentStore, InMemoryDocumentStore
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
from jarvis.modes.catalog import built_in_modes
from jarvis.modes.spec import Mode, ModeRegistry
from jarvis.observability.audit import AuditLog, NullAuditLog, SqlAuditLog
from jarvis.persistence.db import Database
from jarvis.runs.models import RunStore
from jarvis.runs.sql_store import SqlRunStore
from jarvis.security.budget import CostGovernor, Ledger, budgets_from_settings
from jarvis.security.sql_store import (
    SqlAgentMetricsStore,
    SqlApprovalJournal,
    SqlDocumentStore,
    SqlSecretStore,
)
from jarvis.security.vault import InMemorySecretStore, Vault, derive_key
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


def build_computer(settings: Settings) -> Computer:
    """The browser driver, or one that refuses loudly.

    Refusing beats degrading: an agent told "no browser is available" reports
    that, where one handed a silently blank page describes what it imagines.
    """
    if not settings.enable_computer:
        return UnavailableComputer()
    from jarvis.computer.browser import PlaywrightComputer

    driver = PlaywrightComputer(
        headless=settings.browser_headless,
        executable_path=settings.browser_executable or None,
    )
    if not driver.is_available():
        log.warning("computer_driver_missing", reason="playwright is not installed")
        return UnavailableComputer()
    return driver


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
    computer: ComputerSession
    modes: ModeRegistry
    documents: DocumentStore
    composer: DocumentComposer
    vault: Vault
    governor: CostGovernor
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

    def mode(self, mode_id: str | None = None) -> Mode:
        return self.modes.get(mode_id)

    def orchestrator_for(self, mode_id: str | None) -> Orchestrator:
        """An orchestrator that can only see what the mode allows.

        Built per request rather than cached: it is a handful of references,
        and a cached one would go stale the moment an agent's metrics moved.
        The narrowing happens once, here, so nothing downstream needs to know
        modes exist (ADR 0010).
        """
        mode = self.modes.get(mode_id)
        if mode.id == self.modes.default_id and not mode.agents and not mode.briefing:
            return self.orchestrator  # the unconstrained default, unwrapped
        return Orchestrator(
            registry=mode.view(self.agents),
            runtime=self.runtime,
            router=self.router,
            runs=self.runs,
            bus=self.bus,
            use_arbiter=self.settings.use_llm_arbiter,
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
        # Everything durable comes back before anything is served. The vault
        # is loaded eagerly rather than lazily because a secret nobody has read
        # yet cannot be redacted — which is exactly when it ends up in a log.
        await self.vault.load()
        await self.approvals.restore()
        await self.agents.restore()

        if self.settings.enable_scheduler:
            await self.scheduler.start()

    async def stop(self) -> None:
        await self.scheduler.stop()
        await self.mcp.stop_all()
        await self.computer.stop()
        if isinstance(self.bus, RedisEventBus):
            await self.bus.stop()
        if self.database is not None:
            await self.database.dispose()


def build(
    settings: Settings | None = None,
    *,
    providers: list[LLMProvider] | None = None,
    clock: Clock = SYSTEM_CLOCK,
    computer_driver: Computer | None = None,
) -> Jarvis:
    settings = settings or get_settings()

    bus: EventBus = (
        RedisEventBus(settings.redis_url, clock=clock)
        if settings.redis_url
        else EventBus(clock=clock)
    )
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

    vault = Vault(
        store=SqlSecretStore(database) if database else InMemorySecretStore(),
        key=derive_key(settings.vault_key) if settings.vault_key else None,
    )
    governor = CostGovernor(
        ledger=Ledger(clock=clock),
        budgets=budgets_from_settings(
            daily_soft=settings.daily_budget_soft_usd,
            daily_hard=settings.daily_budget_hard_usd,
            monthly_soft=settings.monthly_budget_soft_usd,
            monthly_hard=settings.monthly_budget_hard_usd,
        ),
    )
    approvals = ApprovalBroker(
        bus=bus,
        clock=clock,
        timeout_s=settings.approval_timeout_s,
        journal=SqlApprovalJournal(database) if database else None,
    )
    # The router is the one place every model call passes through — agents,
    # workflows, documents, voice and the routing arbiter all end up there — so
    # the ceilings are enforced there rather than in each caller.
    router = ModelRouter(
        providers or build_providers(settings),
        bus=bus,
        clock=clock,
        governor=governor,
        approvals=approvals,
    )
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
        vault=vault,
    )
    workspace = Workspace(settings.workspace_dir)
    register_builtins(tools, memory, knowledge)
    register_system_tools(tools, workspace)
    mcp = MCPManager(tools)

    # Computer control is opt-in, and the wall is built here rather than in the
    # session so the same policy object is what the UI reports and what the
    # session enforces — a wall described in one place and enforced in another
    # is a wall nobody can check.
    computer = ComputerSession(
        computer=computer_driver or build_computer(settings),
        policy=ComputerPolicy(
            allowed_hosts=tuple(settings.browser_allowed_hosts),
            blocked_hosts=tuple(settings.browser_blocked_hosts),
        ),
        bus=bus,
        approvals=approvals,
        audit=audit,
        max_steps=settings.browser_max_steps,
        max_seconds=settings.browser_max_seconds,
    )
    if settings.enable_computer:
        register_computer_tools(tools, computer)

    # Every tool an agent declares but nothing implements. Not fatal — computer
    # control is opt-in and MCP servers mount later, so a gap here is often
    # correct — but it is never *silently* correct, which is how twelve agents
    # ended up advertising capabilities they did not have.
    unresolved = {
        spec.id: missing for spec in agents.all() if (missing := tools.missing(spec.tools))
    }
    if unresolved:
        log.warning("agent_tools_unresolved", agents=unresolved)

    documents: DocumentStore = (
        SqlDocumentStore(database, clock=clock) if database else InMemoryDocumentStore()
    )
    if database is not None:
        agents.store = SqlAgentMetricsStore(database)

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

    composer = DocumentComposer(
        router=router,
        runtime=runtime,
        agents=agents,
        knowledge=knowledge,
        bus=bus,
        clock=clock,
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
        computer=computer,
        modes=built_in_modes(),
        documents=documents,
        composer=composer,
        vault=vault,
        governor=governor,
        database=database,
    )
