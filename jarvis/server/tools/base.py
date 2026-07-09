"""Tool framework: typed tool definitions, a registry, and safe execution.

Agents receive tool schemas in their prompt, emit JSON tool calls, and
the executor validates arguments against the schema before running.
Every execution is bounded by a timeout and captured as a ToolResult.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger("jarvis.tools")

TOOL_TIMEOUT_DEFAULT = 60


@dataclass
class ToolParam:
    name: str
    type: str  # "string" | "integer" | "number" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    enum: list[str] | None = None


@dataclass
class Tool:
    name: str
    description: str
    params: list[ToolParam]
    handler: Callable[..., Awaitable[Any]]
    timeout: int = TOOL_TIMEOUT_DEFAULT
    dangerous: bool = False  # dangerous tools can be disabled per-deployment

    def schema(self) -> dict:
        properties = {}
        for p in self.params:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [p.name for p in self.params if p.required],
            },
        }


@dataclass
class ToolResult:
    tool: str
    ok: bool
    output: str
    error: str = ""
    meta: dict = field(default_factory=dict)


_PY_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def subset(self, names: list[str]) -> list[Tool]:
        return [self._tools[n] for n in names if n in self._tools]

    def schemas(self, names: list[str] | None = None) -> list[dict]:
        tools = self.subset(names) if names is not None else list(self._tools.values())
        return [t.schema() for t in tools]

    def validate_args(self, tool: Tool, args: dict) -> str | None:
        """Return an error message, or None when args are valid."""
        if not isinstance(args, dict):
            return "arguments must be a JSON object"
        for p in tool.params:
            if p.name not in args:
                if p.required:
                    return f"missing required parameter '{p.name}'"
                continue
            expected = _PY_TYPES[p.type]
            value = args[p.name]
            if p.type == "number" and isinstance(value, bool):
                return f"parameter '{p.name}' must be a number"
            if not isinstance(value, expected):
                return f"parameter '{p.name}' must be of type {p.type}"
            if p.enum and value not in p.enum:
                return f"parameter '{p.name}' must be one of {p.enum}"
        unknown = set(args) - {p.name for p in tool.params}
        if unknown:
            return f"unknown parameters: {sorted(unknown)}"
        return None

    async def execute(self, name: str, args: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(tool=name, ok=False, output="", error=f"unknown tool '{name}'")
        error = self.validate_args(tool, args)
        if error:
            return ToolResult(tool=name, ok=False, output="", error=error)
        try:
            result = await asyncio.wait_for(tool.handler(**args), timeout=tool.timeout)
            output = result if isinstance(result, str) else repr(result)
            return ToolResult(tool=name, ok=True, output=output[:20000])
        except asyncio.TimeoutError:
            return ToolResult(
                tool=name, ok=False, output="", error=f"tool timed out after {tool.timeout}s"
            )
        except Exception as exc:
            log.exception("tool %s raised", name)
            return ToolResult(tool=name, ok=False, output="", error=f"{type(exc).__name__}: {exc}")


registry = ToolRegistry()


def tool(
    name: str,
    description: str,
    params: list[ToolParam] | None = None,
    timeout: int = TOOL_TIMEOUT_DEFAULT,
    dangerous: bool = False,
):
    """Decorator registering an async function as a tool."""

    def wrap(fn: Callable[..., Awaitable[Any]]):
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(f"tool handler {fn.__name__} must be async")
        registry.register(
            Tool(
                name=name,
                description=description,
                params=params or [],
                handler=fn,
                timeout=timeout,
                dangerous=dangerous,
            )
        )
        return fn

    return wrap
