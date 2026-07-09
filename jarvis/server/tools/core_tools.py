"""Built-in tools: web search, web fetch, sandboxed filesystem, sandboxed
shell, code execution, and document generation.

Filesystem and shell tools are confined to settings.sandbox_dir; paths are
resolved and checked to stay inside the sandbox root, blocking traversal.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx

from ..config import settings
from .base import ToolParam, tool

SANDBOX = settings.sandbox_dir.resolve()


def _safe_path(relative: str) -> Path:
    """Resolve a user-supplied path inside the sandbox, or raise."""
    candidate = (SANDBOX / relative.lstrip("/")).resolve()
    if candidate != SANDBOX and SANDBOX not in candidate.parents:
        raise ValueError("path escapes the sandbox directory")
    return candidate


# --------------------------------------------------------------- web search

@tool(
    "web_search",
    "Search the web and return the top results (title, url, snippet).",
    [
        ToolParam("query", "string", "The search query"),
        ToolParam("count", "integer", "Number of results (1-10)", required=False),
    ],
    timeout=30,
)
async def web_search(query: str, count: int = 5) -> str:
    count = max(1, min(int(count), 10))
    if settings.search_provider == "brave" and settings.brave_api_key:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": settings.brave_api_key},
                params={"q": query, "count": count},
            )
            resp.raise_for_status()
            results = resp.json().get("web", {}).get("results", [])
        lines = [
            f"{i+1}. {r.get('title','')}\n   {r.get('url','')}\n   {r.get('description','')}"
            for i, r in enumerate(results[:count])
        ]
        return "\n".join(lines) or "No results."
    # DuckDuckGo Instant Answer + HTML fallback (no key required).
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (JARVIS)"},
        )
        resp.raise_for_status()
    matches = re.findall(
        r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.DOTALL
    )
    snippets = re.findall(r'result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)

    def clean(html: str) -> str:
        return re.sub(r"<[^>]+>", "", html).strip()

    lines = []
    for i, (url, title) in enumerate(matches[:count]):
        snippet = clean(snippets[i]) if i < len(snippets) else ""
        lines.append(f"{i+1}. {clean(title)}\n   {url}\n   {snippet}")
    return "\n".join(lines) or "No results."


@tool(
    "web_fetch",
    "Fetch a URL and return its text content (HTML stripped, truncated).",
    [ToolParam("url", "string", "The URL to fetch")],
    timeout=30,
)
async def web_fetch(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (JARVIS)"})
        resp.raise_for_status()
    text = resp.text
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:15000]


# ---------------------------------------------------------------- filesystem

@tool(
    "fs_write",
    "Write text to a file inside the workspace sandbox.",
    [
        ToolParam("path", "string", "Relative path within the sandbox"),
        ToolParam("content", "string", "Text content to write"),
    ],
)
async def fs_write(path: str, content: str) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {len(content)} bytes to {path}"


@tool(
    "fs_read",
    "Read a text file from the workspace sandbox.",
    [ToolParam("path", "string", "Relative path within the sandbox")],
)
async def fs_read(path: str) -> str:
    target = _safe_path(path)
    if not target.exists():
        return f"File not found: {path}"
    return target.read_text()[:20000]


@tool(
    "fs_list",
    "List files and directories in the workspace sandbox.",
    [ToolParam("path", "string", "Relative directory path", required=False)],
)
async def fs_list(path: str = "") -> str:
    target = _safe_path(path) if path else SANDBOX
    if not target.exists():
        return f"Directory not found: {path}"
    entries = []
    for item in sorted(target.iterdir()):
        kind = "dir " if item.is_dir() else "file"
        size = item.stat().st_size if item.is_file() else 0
        entries.append(f"{kind} {item.name} ({size}b)")
    return "\n".join(entries) or "(empty)"


# --------------------------------------------------------------------- shell

@tool(
    "shell",
    "Run a shell command inside the sandbox directory. Returns stdout/stderr.",
    [ToolParam("command", "string", "The shell command to execute")],
    timeout=settings.shell_timeout_seconds,
    dangerous=True,
)
async def shell(command: str) -> str:
    if not settings.enable_shell_tool:
        return "Shell tool is disabled by configuration (JARVIS_ENABLE_SHELL_TOOL=false)."
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(SANDBOX),
        env={**os.environ, "HOME": str(SANDBOX)},
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=settings.shell_timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Command timed out after {settings.shell_timeout_seconds}s"
    return (out.decode(errors="replace") or "(no output)")[:15000]


@tool(
    "python_exec",
    "Execute a Python 3 snippet in the sandbox and return stdout. Use for "
    "calculations, data processing, and generating files.",
    [ToolParam("code", "string", "Python source to execute")],
    timeout=settings.shell_timeout_seconds,
    dangerous=True,
)
async def python_exec(code: str) -> str:
    if not settings.enable_shell_tool:
        return "Code execution is disabled by configuration."
    script = SANDBOX / "_exec_tmp.py"
    script.write_text(code)
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(SANDBOX),
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=settings.shell_timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        return f"Execution timed out after {settings.shell_timeout_seconds}s"
    finally:
        script.unlink(missing_ok=True)
    return (out.decode(errors="replace") or "(no output)")[:15000]


# ---------------------------------------------------------- document output

@tool(
    "generate_document",
    "Generate a document (markdown, html, csv, or json) and save it to the "
    "sandbox. Returns the saved path.",
    [
        ToolParam("filename", "string", "Output filename, e.g. report.md"),
        ToolParam("content", "string", "Full document content"),
        ToolParam(
            "format", "string", "Document format",
            required=False, enum=["markdown", "html", "csv", "json", "text"],
        ),
    ],
)
async def generate_document(filename: str, content: str, format: str = "markdown") -> str:
    if format == "json":
        try:
            content = json.dumps(json.loads(content), indent=2)
        except json.JSONDecodeError:
            return "Invalid JSON content for json format."
    if format == "html" and "<html" not in content.lower():
        content = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{filename}</title></head><body>{content}</body></html>"
        )
    target = _safe_path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Saved {format} document to {filename} ({len(content)} bytes)"


# Import here so registering these tools happens on package import.
DEFAULT_TOOL_NAMES = [
    "web_search", "web_fetch", "fs_write", "fs_read", "fs_list",
    "shell", "python_exec", "generate_document",
]
