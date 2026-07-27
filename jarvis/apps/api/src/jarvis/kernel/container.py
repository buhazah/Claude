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
from jarvis.llm.base import LLMProvider
from jarvis.llm.providers.anthropic import AnthropicProvider
from jarvis.llm.providers.echo import EchoProvider
from jarvis.llm.providers.openai import LocalProvider, OpenAIProvider
from jarvis.llm.router import ModelRouter
from jarvis.memory.store import InMemoryStore
from jarvis.runs.models import RunStore
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


@dataclass(slots=True)
class Jarvis:
    """The assembled system. One object the API layer depends on."""

    settings: Settings
    bus: EventBus
    router: ModelRouter
    agents: AgentRegistry
    memory: InMemoryStore
    runs: RunStore
    tools: ToolRegistry
    runtime: AgentRuntime
    orchestrator: Orchestrator

    @property
    def provider_names(self) -> list[str]:
        return sorted(self.router.providers)


def build(
    settings: Settings | None = None,
    *,
    providers: list[LLMProvider] | None = None,
    clock: Clock = SYSTEM_CLOCK,
) -> Jarvis:
    settings = settings or get_settings()
    bus = EventBus(clock=clock)
    router = ModelRouter(providers or build_providers(settings), bus=bus, clock=clock)
    agents = AgentRegistry()
    memory = InMemoryStore(bus=bus, clock=clock)
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
    )
