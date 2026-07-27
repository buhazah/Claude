"""Built-in tools available before any connector is configured.

Deliberately small. Real connectors (browser, GitHub, Gmail, terminal) land in
M4 behind the same registry and the same permission wall — these exist so the
tool path is exercised end to end from day one.
"""

from __future__ import annotations

from typing import Any

from jarvis.memory.models import MemoryKind
from jarvis.memory.store import InMemoryStore
from jarvis.tools.registry import Permission, ToolRegistry


def register_builtins(registry: ToolRegistry, memory: InMemoryStore) -> None:
    async def memory_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
        recalls = await memory.search(query, limit=limit)
        return [
            {"content": r.memory.content, "kind": r.memory.kind.value, "score": r.score}
            for r in recalls
        ]

    async def memory_write(content: str, kind: str | None = None) -> dict[str, str]:
        stored = await memory.remember(
            content, kind=MemoryKind(kind) if kind else None, source="tool"
        )
        return {"id": stored.id, "kind": stored.kind.value}

    registry.register(
        "memory_search",
        "Search the user's long-term memory in natural language.",
        memory_search,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        permission=Permission.SAFE,
        namespace="memory",
    )

    registry.register(
        "memory_write",
        "Store a durable fact, preference, decision or outcome.",
        memory_write,
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": [k.value for k in MemoryKind],
                    "description": "Omit to auto-categorise",
                },
            },
            "required": ["content"],
        },
        permission=Permission.SENSITIVE,
        namespace="memory",
    )
