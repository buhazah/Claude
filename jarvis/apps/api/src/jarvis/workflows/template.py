"""Context resolution and interpolation.

Workflow steps refer to earlier results: ``"Summarise this: {{ trigger.body }}"``
or ``{"to": "{{ steps.classify.output }}"}``. That needs a resolver, and the
obvious implementations are both wrong for this system:

* ``eval`` / f-strings — a workflow definition is user input, and this process
  also owns a shell tool and a filesystem.
* A full template engine — a large dependency, and its power (loops,
  arbitrary attribute access, filters) is exactly what should not be reachable
  from a stored definition.

So: dotted-path lookup into a plain dict, and nothing else. A missing path
resolves to empty and is *reported*, because a prompt that silently loses half
its content produces a confidently wrong answer.
"""

from __future__ import annotations

import re
from typing import Any

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.\[\]-]+)\s*\}\}")
MAX_RENDERED_CHARS = 20_000


def resolve(path: str, context: dict[str, Any]) -> Any:
    """Look up a dotted path. Returns ``None`` when any segment is missing."""
    current: Any = context
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    import json

    return json.dumps(value, default=str)


def render(template: str, context: dict[str, Any]) -> tuple[str, list[str]]:
    """Interpolate placeholders. Returns the text and any unresolved paths."""
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        path = match.group(1)
        value = resolve(path, context)
        if value is None:
            missing.append(path)
            return ""
        return _stringify(value)

    rendered = PLACEHOLDER.sub(replace, template)
    if len(rendered) > MAX_RENDERED_CHARS:
        rendered = rendered[:MAX_RENDERED_CHARS] + "\n[truncated]"
    return rendered, missing


def render_arguments(
    arguments: dict[str, Any], context: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Interpolate every string leaf of a tool's arguments."""
    missing: list[str] = []

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            rendered, gaps = render(value, context)
            missing.extend(gaps)
            return rendered
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    return walk(arguments), missing
