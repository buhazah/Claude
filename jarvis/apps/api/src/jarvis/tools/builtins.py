"""Built-in tools available before any connector is configured.

Deliberately small. Real connectors (browser, GitHub, Gmail, terminal) land in
M4 behind the same registry and the same permission wall — these exist so the
tool path is exercised end to end from day one.
"""

from __future__ import annotations

from typing import Any

from jarvis.knowledge.store import KnowledgeStore
from jarvis.memory.models import MemoryKind
from jarvis.memory.store import MemoryStore
from jarvis.tools.registry import Permission, ToolRegistry


def register_builtins(
    registry: ToolRegistry, memory: MemoryStore, knowledge: KnowledgeStore | None = None
) -> None:
    # `scope` on both of these is supplied by the runtime from the calling
    # agent's spec, never by the model — see `Tool.scoped`. Without it these
    # read and write the global namespace, which is a hole straight through
    # a mode's narrowing (ADR 0010): an agent in business mode could recall
    # personal memories through the tool that `_build_context` scopes
    # correctly, and write business notes where every mode reads them.
    async def memory_search(
        query: str, limit: int = 5, scope: str | None = None
    ) -> list[dict[str, Any]]:
        recalls = await memory.search(query, limit=limit, scope=scope)
        return [
            {"content": r.memory.content, "kind": r.memory.kind.value, "score": r.score}
            for r in recalls
        ]

    async def memory_write(
        content: str, kind: str | None = None, scope: str | None = None
    ) -> dict[str, str]:
        stored = await memory.remember(
            content,
            kind=MemoryKind(kind) if kind else None,
            source="tool",
            scope=scope or "global",
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
        scoped=True,
    )

    if knowledge is not None:

        async def search_documents(query: str, limit: int = 5) -> list[dict[str, Any]]:
            citations = await knowledge.search(query, limit=limit)
            # The reference travels with the text, so an agent that uses a
            # passage has no excuse for citing it vaguely or not at all.
            return [
                {
                    "reference": c.reference(),
                    "source": c.source,
                    "untrusted_content": c.snippet,
                    "score": c.score,
                }
                for c in citations
            ]

        registry.register(
            "search_documents",
            "Search ingested documents. Results carry a reference you must cite.",
            search_documents,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            permission=Permission.SAFE,
            namespace="knowledge",
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
        scoped=True,
    )
