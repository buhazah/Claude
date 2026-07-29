"""Modes: the narrowing, and the invariant that it only ever subtracts.

A mode is only worth having if it is enforced. Most of these tests are about
the ways a mode could accidentally *widen* reach — the failure that would turn
"switch to Business" into a way around the permission architecture.
"""

from __future__ import annotations

import pytest

from jarvis.agents.spec import AgentSpec, RoutingPolicy
from jarvis.kernel import container
from jarvis.kernel.errors import NotFoundError
from jarvis.llm.providers.echo import EchoProvider
from jarvis.modes.catalog import BUILT_IN, BUSINESS, CODING, PERSONAL, RESEARCH, built_in_modes
from jarvis.modes.spec import Mode
from jarvis.tools.registry import Grant, Permission

SPEC = AgentSpec(
    id="marketer",
    name="Marketer",
    tagline="Campaigns.",
    system_prompt="You write campaigns.",
    tools=("fetch_url", "browser_open", "run_command"),
    policy=RoutingPolicy.CHEAP,
)


# ── The invariant ─────────────────────────────────────────────────────────────


def test_a_mode_cannot_grant_a_tool_the_agent_does_not_have() -> None:
    """The whole safety argument. Tools are intersected, never unioned."""
    mode = Mode(id="x", name="X", tagline="", tools=("*", "delete_everything", "wire_money"))
    narrowed = mode.narrow(SPEC)

    assert set(narrowed.tools) == set(SPEC.tools)
    assert "delete_everything" not in narrowed.tools


def test_a_mode_can_take_tools_away() -> None:
    mode = Mode(id="x", name="X", tagline="", tools=("fetch_url",))
    assert mode.narrow(SPEC).tools == ("fetch_url",)


def test_a_tool_pattern_narrows_by_prefix() -> None:
    mode = Mode(id="x", name="X", tagline="", tools=("browser_*",))
    assert mode.narrow(SPEC).tools == ("browser_open",)


def test_a_mode_cannot_reach_an_agent_the_catalog_does_not_have(jarvis) -> None:
    mode = Mode(id="x", name="X", tagline="", agents=("marketing", "nonexistent_agent"))
    view = mode.view(jarvis.agents)

    assert [s.id for s in view.all()] == ["marketing"]


def test_a_briefing_is_context_not_capability() -> None:
    """A prompt can change what an agent says. It cannot change what it reaches."""
    mode = Mode(
        id="x",
        name="X",
        tagline="",
        briefing="You may use any tool you like, including run_command on production.",
        tools=("fetch_url",),
    )
    narrowed = mode.narrow(SPEC)

    assert narrowed.tools == ("fetch_url",)
    assert narrowed.system_prompt.startswith("You may use any tool")
    assert SPEC.system_prompt in narrowed.system_prompt


def test_narrowing_does_not_mutate_the_catalog(jarvis) -> None:
    """A mode is a view. Switching to it must not edit the system."""
    before = jarvis.agents.get("marketing")
    BUSINESS.view(jarvis.agents)
    after = jarvis.agents.get("marketing")

    assert after.system_prompt == before.system_prompt
    assert after.memory_scopes == before.memory_scopes
    assert after.tools == before.tools


# ── Resolution ────────────────────────────────────────────────────────────────


def test_the_default_mode_is_unconstrained(jarvis) -> None:
    """Personal exists so that switching *out* of it is what narrows."""
    assert PERSONAL.agents == ()
    assert PERSONAL.briefing == ""
    assert PERSONAL.memory_scope == ""
    assert len(PERSONAL.view(jarvis.agents).all()) == len(jarvis.agents.all())


def test_an_unknown_mode_is_refused_rather_than_defaulted() -> None:
    """Falling back would fail *open*: the default is the unconstrained mode."""
    registry = built_in_modes()
    with pytest.raises(NotFoundError, match="unknown mode"):
        registry.get("busines")


def test_no_mode_is_the_same_as_the_default() -> None:
    assert built_in_modes().get(None).id == "personal"
    assert built_in_modes().get("").id == "personal"


def test_the_default_orchestrator_is_not_rebuilt(jarvis) -> None:
    """The unconstrained path must stay the unconstrained object."""
    assert jarvis.orchestrator_for(None) is jarvis.orchestrator
    assert jarvis.orchestrator_for("personal") is jarvis.orchestrator
    assert jarvis.orchestrator_for("coding") is not jarvis.orchestrator


# ── The three seams ───────────────────────────────────────────────────────────


def test_routing_cannot_escape_the_mode(jarvis) -> None:
    """The point of coding mode: a request about feelings does not find the
    life coach, however the words fall."""
    coding = jarvis.orchestrator_for("coding")
    reachable = {s.id for s in coding.registry.all()}

    assert "life_coach" not in reachable
    assert "health" not in reachable
    assert "coding" in reachable

    matches = coding.registry.route("I am feeling burnt out and anxious about work")
    assert all(m.agent_id in reachable for m in matches)


def test_memory_is_namespaced_per_mode(jarvis) -> None:
    """What Jarvis learns about a client must not surface in a personal draft."""
    personal = jarvis.agents.get("marketing")
    business = BUSINESS.view(jarvis.agents).get("marketing")

    assert personal.scope == "marketing"
    assert business.scope == "business:marketing"


async def test_a_mode_scoped_memory_is_invisible_to_the_default(jarvis) -> None:
    """Not just a different string — a different search result."""
    business = BUSINESS.view(jarvis.agents).get("marketing")
    await jarvis.memory.remember(
        "The Q3 pricing floor for Acme is 40% margin", scope=business.scope
    )

    inside = await jarvis.memory.search("Acme pricing floor", scope=business.scope)
    outside = await jarvis.memory.search("Acme pricing floor", scope="marketing")

    assert inside, "the memory must be findable inside the mode that wrote it"
    assert outside == [], "and invisible outside it"


def test_a_mode_can_override_the_routing_policy(jarvis) -> None:
    """A cheap model that writes plausible-looking code costs more in review."""
    assert CODING.view(jarvis.agents).get("coding").policy is RoutingPolicy.QUALITY
    assert RESEARCH.view(jarvis.agents).get("research").policy is RoutingPolicy.QUALITY


# ── The catalog ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", BUILT_IN, ids=lambda m: m.id)
def test_every_built_in_mode_reaches_real_agents(mode: Mode, jarvis) -> None:
    """A mode listing an agent that does not exist is a silently empty mode."""
    known = {s.id for s in jarvis.agents.all()}
    assert set(mode.agents) <= known, f"{mode.id} names agents that do not exist"


@pytest.mark.parametrize("mode", BUILT_IN, ids=lambda m: m.id)
def test_every_built_in_mode_can_actually_route(mode: Mode, jarvis) -> None:
    view = mode.view(jarvis.agents)
    assert view.all(), f"{mode.id} has no agents"
    assert view.route("summarise this and tell me what to do about it")


@pytest.mark.parametrize("mode", [BUSINESS, CODING, RESEARCH], ids=lambda m: m.id)
def test_every_non_default_mode_actually_narrows(mode: Mode, jarvis) -> None:
    """A mode that removes nothing and adds nothing has no reason to exist."""
    assert len(mode.view(jarvis.agents).all()) < len(jarvis.agents.all())
    assert mode.briefing, f"{mode.id} has no point of view"
    assert mode.memory_scope, f"{mode.id} shares the default memory namespace"


def test_modes_are_published_with_what_they_narrow(jarvis) -> None:
    """The UI must not be able to claim a constraint the kernel does not hold."""
    for mode in jarvis.modes.all():
        assert mode.name and mode.tagline
        assert mode.surfaces, f"{mode.id} tells the client nothing about what to show"


def test_pinning_an_excluded_agent_is_not_a_way_around_a_mode(settings, clock) -> None:
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    coding = system.orchestrator_for("coding")

    assert "life_coach" in system.agents
    assert "life_coach" not in coding.registry


@pytest.mark.asyncio
async def test_a_memory_tool_cannot_read_across_a_mode_narrowing() -> None:
    """F11 of the intelligence audit.

    `AgentRuntime._build_context` recalls with `scope=spec.scope`, which a mode
    rewrites — that part was right. The `memory_search` *tool* called
    `memory.search(query, limit=limit)` with no scope at all, so it read every
    namespace. An agent in business mode therefore had one path to memory that
    respected the narrowing and another, reachable by the model on its own
    initiative, that did not.

    Same shape as the M9 routing fallback that escaped modes by hardcoding an
    agent id: a narrowing enforced in one place and ignored in another.
    """
    from jarvis.memory.store import InMemoryStore
    from jarvis.tools.builtins import register_builtins
    from jarvis.tools.registry import ToolRegistry

    memory = InMemoryStore()
    await memory.remember("the user's partner is called Sam", scope="life_coach")
    await memory.remember("Acme's renewal is in March", scope="business:sales")

    tools = ToolRegistry()
    register_builtins(tools, memory, None)

    business = await tools.invoke("memory_search", {"query": "Sam"}, scope="business:sales")
    assert not any("Sam" in hit["content"] for hit in business), (
        "a business-mode agent must not recall a personal memory through a tool"
    )

    personal = await tools.invoke("memory_search", {"query": "Sam"}, scope="life_coach")
    assert any("Sam" in hit["content"] for hit in personal)


@pytest.mark.asyncio
async def test_a_model_cannot_choose_its_own_memory_scope() -> None:
    """The scope is the runtime's to supply, never the model's to name. If a
    model could pass one it could pass somebody else's, and the narrowing
    would be advisory."""
    from jarvis.memory.store import InMemoryStore
    from jarvis.tools.builtins import register_builtins
    from jarvis.tools.registry import ToolRegistry

    memory = InMemoryStore()
    await memory.remember("the user's partner is called Sam", scope="life_coach")

    tools = ToolRegistry()
    register_builtins(tools, memory, None)

    smuggled = await tools.invoke(
        "memory_search", {"query": "Sam", "scope": "life_coach"}, scope="business:sales"
    )
    assert not any("Sam" in hit["content"] for hit in smuggled)


@pytest.mark.asyncio
async def test_a_memory_written_by_a_tool_lands_in_the_callers_namespace() -> None:
    """The write side of the same hole: `memory_write` defaulted to the global
    scope, so a note taken in business mode was readable from every mode."""
    from jarvis.memory.store import InMemoryStore
    from jarvis.tools.builtins import register_builtins
    from jarvis.tools.registry import ToolRegistry

    memory = InMemoryStore()
    tools = ToolRegistry(grants=[Grant("*", Permission.SENSITIVE)])
    register_builtins(tools, memory, None)

    await tools.invoke(
        "memory_write", {"content": "Acme wants net-60 terms"}, scope="business:sales"
    )

    stored = await memory.all(scope="business:sales")
    assert [m.content for m in stored] == ["Acme wants net-60 terms"]
    assert not await memory.all(scope="global")
