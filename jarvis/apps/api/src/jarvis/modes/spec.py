"""Modes.

A mode is not a theme and not a preset prompt. If switching to "Business"
only changed the accent colour and prepended a sentence, it would be a lie the
UI tells — the same agents, the same tools, the same memory, dressed up.

A mode is a **narrowing**, applied at three seams:

* **Routing.** Only the mode's agents are candidates. Coding mode cannot route
  a request to the therapist, however the words fall.
* **Reach.** An agent's tools are *intersected* with the mode's allowlist.
* **Memory.** Reads and writes are scoped to the mode, so what Jarvis learns
  about a client does not surface while drafting a personal message.

The invariant that makes this safe to build on: **a mode can only ever
subtract.** It cannot hand an agent a tool its spec does not list, cannot
raise a permission the registry would refuse, and cannot reach an agent the
catalog does not have. Any other rule and "mode" becomes a way to widen
authority by picking a different one — the exact thing the permission
architecture exists to prevent.

The mechanism is deliberately dull: a mode produces a *narrowed registry* of
narrowed specs, and everything downstream — orchestrator, runtime, tools,
memory — runs unchanged against it. No conditional threading a mode id through
five call sites and forgetting the sixth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jarvis.agents.registry import AgentRegistry
from jarvis.agents.spec import AgentSpec
from jarvis.kernel.errors import NotFoundError
from jarvis.llm.base import RoutingPolicy


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    """Exact name, ``namespace.*``, or ``*``. Same shape as a tool grant."""
    for pattern in patterns:
        if pattern == "*" or pattern == name:
            return True
        if pattern.endswith("*") and name.startswith(pattern[:-1]):
            return True
    return False


@dataclass(frozen=True, slots=True)
class Mode:
    """One way of working, expressed as constraints."""

    id: str
    name: str
    tagline: str
    # Empty means "every agent in the catalog" — the default, personal mode.
    agents: tuple[str, ...] = ()
    # Patterns intersected with each agent's own allowlist. "*" keeps whatever
    # the agent already had; it does not grant anything new.
    tools: tuple[str, ...] = ("*",)
    # Prepended to every agent's system prompt in this mode. Context, never
    # capability — a briefing cannot make a tool appear.
    briefing: str = ""
    # Overrides the agent's default routing policy when set. Research wants
    # quality; triaging an inbox does not.
    policy: RoutingPolicy | None = None
    # Memory namespace. Empty means the agent's own scope, unchanged.
    memory_scope: str = ""
    # What the client should surface. Presentation only, and stated as data so
    # the UI has one source of truth rather than a switch statement.
    surfaces: tuple[str, ...] = ()
    accent: str = ""

    def admits(self, agent_id: str) -> bool:
        return not self.agents or agent_id in self.agents

    def narrow(self, spec: AgentSpec) -> AgentSpec:
        """Return this agent as it exists inside the mode.

        Subtractive by construction: tools are intersected, never unioned.
        """
        tools = tuple(t for t in spec.tools if _matches(t, self.tools))
        prompt = spec.system_prompt
        if self.briefing:
            prompt = f"{self.briefing.strip()}\n\n{prompt}"
        return spec.model_copy(
            update={
                "system_prompt": prompt,
                "tools": tools,
                "policy": self.policy or spec.policy,
                "memory_scopes": (
                    (f"{self.memory_scope}:{spec.id}",) if self.memory_scope else spec.memory_scopes
                ),
            }
        )

    def view(self, registry: AgentRegistry) -> AgentRegistry:
        """The catalog as it exists inside the mode.

        A registry rather than a filter callback, so routing, tool resolution
        and metrics all see the same narrowed world without knowing modes
        exist.

        Declared order is preserved, because the registry falls back to its
        first agent when nothing matches — so the agent a mode names first is
        the one that owns whatever the mode cannot classify. That should be a
        decision, not whatever the catalog happened to list first.
        """
        specs = {s.id: s for s in registry.all()}
        chosen = (
            [specs[a] for a in self.agents if a in specs] if self.agents else list(specs.values())
        )
        return AgentRegistry([self.narrow(s) for s in chosen])


@dataclass(slots=True)
class ModeRegistry:
    modes: dict[str, Mode] = field(default_factory=dict)
    default_id: str = "personal"

    def __post_init__(self) -> None:
        if self.default_id not in self.modes and self.modes:
            self.default_id = next(iter(self.modes))

    def get(self, mode_id: str | None) -> Mode:
        """Resolve a mode. Absent means the default; unknown is an error.

        Falling back on an unknown id would fail *open*: the default mode is
        the unconstrained one, so a typo — `?mode=busines` — would silently
        hand back the whole catalog and the personal memory namespace when the
        caller asked to be narrowed. Refusing is the only answer that cannot
        quietly widen reach.
        """
        if not mode_id:
            return self.modes[self.default_id]
        try:
            return self.modes[mode_id]
        except KeyError:
            raise NotFoundError(f"unknown mode: {mode_id}") from None

    def all(self) -> list[Mode]:
        return list(self.modes.values())

    def __contains__(self, mode_id: str) -> bool:
        return mode_id in self.modes
