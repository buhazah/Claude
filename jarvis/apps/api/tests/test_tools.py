from __future__ import annotations

import pytest

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import FrozenClock
from jarvis.kernel.errors import ApprovalRequiredError, NotFoundError, PermissionDeniedError
from jarvis.memory.store import InMemoryStore
from jarvis.tools.builtins import register_builtins
from jarvis.tools.registry import Grant, Permission, ToolRegistry


def _registry(grants: list[Grant] | None = None, bus: EventBus | None = None) -> ToolRegistry:
    registry = ToolRegistry(bus=bus, grants=grants)
    registry.register("read_note", "Read a note", lambda note_id: f"note:{note_id}")
    registry.register(
        "send_email",
        "Send an email",
        lambda to: f"sent:{to}",
        permission=Permission.SENSITIVE,
        namespace="comms",
    )
    registry.register(
        "delete_repo",
        "Delete a repository",
        lambda name: f"deleted:{name}",
        permission=Permission.DANGEROUS,
        namespace="github",
    )
    return registry


async def test_safe_tool_runs_under_the_default_grant() -> None:
    registry = _registry()
    assert await registry.invoke("read_note", {"note_id": "7"}) == "note:7"


async def test_sensitive_tool_is_denied_without_a_sufficient_grant() -> None:
    registry = _registry([Grant("*", Permission.SAFE)])
    with pytest.raises(PermissionDeniedError, match="requires SENSITIVE"):
        await registry.invoke("send_email", {"to": "a@b.com"})


async def test_sensitive_tool_runs_when_granted() -> None:
    registry = _registry([Grant("*", Permission.SENSITIVE)])
    assert await registry.invoke("send_email", {"to": "a@b.com"}) == "sent:a@b.com"


async def test_dangerous_tool_requires_explicit_approval_even_when_granted() -> None:
    registry = _registry([Grant("*", Permission.DANGEROUS)])
    with pytest.raises(ApprovalRequiredError) as exc:
        await registry.invoke("delete_repo", {"name": "prod"})
    assert exc.value.tool == "delete_repo"


async def test_dangerous_tool_runs_with_an_auto_approve_grant() -> None:
    registry = _registry([Grant("delete_repo", Permission.DANGEROUS, auto_approve=True)])
    assert await registry.invoke("delete_repo", {"name": "scratch"}) == "deleted:scratch"


async def test_namespace_grant_covers_only_its_namespace() -> None:
    registry = _registry([Grant("comms.*", Permission.SENSITIVE)])
    assert await registry.invoke("send_email", {"to": "x@y.com"}) == "sent:x@y.com"
    with pytest.raises(PermissionDeniedError):
        await registry.invoke("delete_repo", {"name": "prod"})


async def test_no_covering_grant_is_a_denial() -> None:
    registry = _registry([Grant("comms.*", Permission.SENSITIVE)])
    with pytest.raises(PermissionDeniedError, match="no grant covers"):
        await registry.invoke("read_note", {"note_id": "1"})


async def test_unknown_tool_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _registry().invoke("nope", {})


def test_schemas_skip_tools_that_are_not_installed() -> None:
    registry = _registry()
    schemas = registry.schemas_for(["read_note", "not_installed_connector"])
    assert [s.name for s in schemas] == ["read_note"]


async def test_invocation_publishes_lifecycle_events() -> None:
    bus = EventBus(clock=FrozenClock())
    registry = _registry(bus=bus)
    sub = bus.subscribe("tool.**")

    await registry.invoke("read_note", {"note_id": "1"})

    topics = [sub.queue.get_nowait().topic for _ in range(sub.queue.qsize())]
    assert topics == ["tool.called", "tool.succeeded"]


async def test_tool_failure_is_published_and_re_raised() -> None:
    bus = EventBus(clock=FrozenClock())
    registry = ToolRegistry(bus=bus)

    def explode() -> None:
        raise RuntimeError("kaboom")

    registry.register("explode", "Always fails", explode)
    sub = bus.subscribe("tool.failed")

    with pytest.raises(RuntimeError, match="kaboom"):
        await registry.invoke("explode", {})
    assert sub.queue.qsize() == 1


async def test_builtin_memory_tools_round_trip(clock: FrozenClock) -> None:
    memory = InMemoryStore(clock=clock)
    registry = ToolRegistry(grants=[Grant("*", Permission.SENSITIVE)])
    register_builtins(registry, memory)

    written = await registry.invoke("memory_write", {"content": "The launch date is March 14"})
    assert written["id"].startswith("mem_")

    found = await registry.invoke("memory_search", {"query": "when is the launch"})
    assert found and "March 14" in found[0]["content"]


def test_builtin_write_is_sensitive_and_search_is_safe(clock: FrozenClock) -> None:
    registry = ToolRegistry()
    register_builtins(registry, InMemoryStore(clock=clock))
    assert registry.get("memory_search").permission is Permission.SAFE
    assert registry.get("memory_write").permission is Permission.SENSITIVE
