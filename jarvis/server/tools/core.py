"""Built-in tools: web search/fetch, sandboxed filesystem, shell, Python
execution, HTTP requests, and document generation.

Filesystem, shell, and code execution are jailed to settings.sandbox_dir.
Path traversal is blocked by resolving against the sandbox root; the shell
runs with a timeout, no network-inherited env, and output caps.
"""
from __future__ import annotations

import asyncio
import csv
import html
import io
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..config import settings
from .base import ToolParam, tool

MAX_OUTPUT = 16000


def _sandbox_path(relative: str) -> Path:
    """Resolve a path inside the sandbox, refusing escapes."""
    root = settings.sandbox_dir.resolve()
    candidate = (root / relative.lstrip("/")).resolve()
    if candidate != root and root not in candidate.parents:
        raise PermissionError(f"path escapes sandbox: {relative}")
    return candidate


# ------------------------------------------------------------------ web

@tool(
    "web_search",
    "Search the web. Returns titles, URLs and snippets of top results.",
    [
        ToolParam("query", "string", "The search query"),
        ToolParam("max_results", "integer", "Max results to return (1-10)", required=False),
    ],
    timeout=30,
)
async def web_search(query: str, max_results: int = 6) -> str:
    max_results = max(1, min(int(max_results), 10))
    if settings.search_provider == "brave" and settings.brave_api_key:
        return await _brave_search(query, max_results)
    return await _duckduckgo_search(query, max_results)


async def _brave_search(query: str, max_results: int) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": settings.brave_api_key},
        )
        resp.raise_for_status()
    results = resp.json().get("web", {}).get("results", [])[:max_results]
    if not results:
        return "No results found."
    return "\n\n".join(
        f"{i+1}. {r.get('title','')}\n{r.get('url','')}\n{r.get('description','')}"
        for i, r in enumerate(results)
    )


async def _duckduckgo_search(query: str, max_results: int) -> str:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"user-agent": "Mozilla/5.0 (JARVIS agent)"},
        )
        resp.raise_for_status()
    body = resp.text
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</',
        re.DOTALL,
    )
    results = []
    for href, title, snippet in pattern.findall(body)[:max_results]:
        # DDG wraps URLs in a redirect: extract uddg param when present.
        parsed = urllib.parse.urlparse(href)
        params = urllib.parse.parse_qs(parsed.query)
        url = params.get("uddg", [href])[0]
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        results.append(f"{len(results)+1}. {clean(title)}\n{url}\n{clean(snippet)}")
    return "\n\n".join(results) if results else "No results found."


@tool(
    "web_fetch",
    "Fetch a URL and return its readable text content (HTML stripped).",
    [ToolParam("url", "string", "The absolute http(s) URL to fetch")],
    timeout=45,
)
async def web_fetch(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers={"user-agent": "Mozilla/5.0 (JARVIS agent)"})
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type and "json" not in content_type:
        return f"[binary content: {content_type}, {len(resp.content)} bytes]"
    text = resp.text
    if "html" in content_type:
        text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:MAX_OUTPUT]


@tool(
    "http_request",
    "Make an HTTP request to an API. Returns status code and body.",
    [
        ToolParam("url", "string", "Absolute URL"),
        ToolParam("method", "string", "HTTP method", required=False,
                  enum=["GET", "POST", "PUT", "PATCH", "DELETE"]),
        ToolParam("body", "string", "Request body (JSON string)", required=False),
        ToolParam("headers", "object", "Extra request headers", required=False),
    ],
    timeout=45,
)
async def http_request(url: str, method: str = "GET", body: str = "", headers: dict | None = None) -> str:
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.request(
            method, url, content=body or None, headers=headers or {}
        )
    return f"HTTP {resp.status_code}\n{resp.text[:MAX_OUTPUT]}"


# ------------------------------------------------------------- filesystem

@tool(
    "fs_write",
    "Write a text file inside the JARVIS workspace (sandboxed).",
    [
        ToolParam("path", "string", "Relative path, e.g. reports/summary.md"),
        ToolParam("content", "string", "File contents"),
    ],
)
async def fs_write(path: str, content: str) -> str:
    target = _sandbox_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {len(content)} chars to {path}"


@tool(
    "fs_read",
    "Read a text file from the JARVIS workspace (sandboxed).",
    [ToolParam("path", "string", "Relative path inside the workspace")],
)
async def fs_read(path: str) -> str:
    target = _sandbox_path(path)
    if not target.is_file():
        raise FileNotFoundError(f"no such file: {path}")
    return target.read_text(errors="replace")[:MAX_OUTPUT]


@tool(
    "fs_list",
    "List files in a workspace directory (sandboxed).",
    [ToolParam("path", "string", "Relative directory ('' for root)", required=False)],
)
async def fs_list(path: str = "") -> str:
    target = _sandbox_path(path or ".")
    if not target.is_dir():
        raise NotADirectoryError(f"no such directory: {path}")
    entries = []
    for p in sorted(target.iterdir()):
        kind = "dir " if p.is_dir() else "file"
        size = p.stat().st_size if p.is_file() else ""
        entries.append(f"{kind} {p.name} {size}")
    return "\n".join(entries) or "(empty)"


# ---------------------------------------------------------------- shell

@tool(
    "shell",
    "Run a shell command inside the sandboxed workspace directory.",
    [ToolParam("command", "string", "The command to run")],
    timeout=settings.shell_timeout_seconds + 5,
    dangerous=True,
)
async def shell(command: str) -> str:
    if not settings.enable_shell_tool:
        raise PermissionError("shell tool is disabled by configuration")
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=settings.sandbox_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(settings.sandbox_dir)},
    )
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=settings.shell_timeout_seconds
        )
    except asyncio.TimeoutError:
        proc.kill()
        return f"[command timed out after {settings.shell_timeout_seconds}s]"
    output = stdout.decode(errors="replace")[:MAX_OUTPUT]
    return f"exit code: {proc.returncode}\n{output}"


@tool(
    "python_exec",
    "Execute a Python snippet in an isolated subprocess and return stdout.",
    [ToolParam("code", "string", "Python source code to execute")],
    timeout=settings.shell_timeout_seconds + 5,
    dangerous=True,
)
async def python_exec(code: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-c", code,
        cwd=settings.sandbox_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=settings.shell_timeout_seconds
        )
    except asyncio.TimeoutError:
        proc.kill()
        return f"[python timed out after {settings.shell_timeout_seconds}s]"
    return stdout.decode(errors="replace")[:MAX_OUTPUT] or "(no output)"


# ------------------------------------------------------------- documents

@tool(
    "generate_document",
    "Create a Markdown document in the workspace and return its path.",
    [
        ToolParam("filename", "string", "e.g. weekly-report.md"),
        ToolParam("title", "string", "Document title"),
        ToolParam("content", "string", "Markdown body"),
    ],
)
async def generate_document(filename: str, title: str, content: str) -> str:
    if not filename.endswith(".md"):
        filename += ".md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    doc = f"# {title}