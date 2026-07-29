"""Filesystem, shell and HTTP tools.

These are the first tools that touch the world, so the containment lives here
rather than in the prompt. Two rules:

* **The workspace is a boundary, not a suggestion.** Every path is resolved and
  checked against the workspace root *after* symlink resolution, because
  ``../`` and a symlink out are the same attack with different syntax.
* **Nothing is trusted because a model asked for it.** Tool arguments arrive
  from a model that may be reasoning over web pages or email — content an
  attacker can write. Permission tiers are enforced by the registry regardless
  of how convincingly the request was phrased.
"""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Any

import httpx
import structlog

from jarvis.tools.registry import Permission, ToolRegistry

log = structlog.get_logger(__name__)

MAX_READ_BYTES = 200_000
MAX_FETCH_BYTES = 500_000
SHELL_TIMEOUT_S = 30.0

# Commands that are never worth the risk of an accidental match. This is a
# backstop for obvious catastrophe, not the security boundary — the permission
# tier and the approval gate are.
BLOCKED_COMMANDS = frozenset({"shutdown", "reboot", "halt", "poweroff", "mkfs", "dd"})


class Workspace:
    """A directory that tool paths may not escape."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str) -> Path:
        """Resolve a path inside the workspace, or refuse."""
        candidate = (self.root / relative).expanduser()
        # strict=False so a not-yet-created file still resolves; symlinks in the
        # existing prefix are followed, which is what makes the check meaningful.
        resolved = candidate.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise PermissionError(f"path escapes the workspace: {relative}")
        return resolved

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))


def register_system_tools(registry: ToolRegistry, workspace: Workspace) -> None:
    """Register filesystem, shell and HTTP tools against a workspace."""

    async def read_file(path: str) -> str:
        target = workspace.resolve(path)
        if not target.is_file():
            return f"No such file: {path}"
        data = target.read_bytes()[:MAX_READ_BYTES]
        suffix = "\n[truncated]" if target.stat().st_size > MAX_READ_BYTES else ""
        return data.decode("utf-8", errors="replace") + suffix

    async def write_file(path: str, content: str) -> dict[str, Any]:
        target = workspace.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content, encoding="utf-8")
        return {
            "path": workspace.relative(target),
            "bytes": len(content.encode()),
            "overwrote": existed,
        }

    async def list_files(path: str = ".") -> list[dict[str, Any]]:
        target = workspace.resolve(path)
        if not target.is_dir():
            return []
        return sorted(
            (
                {
                    "name": child.name,
                    "kind": "dir" if child.is_dir() else "file",
                    "bytes": child.stat().st_size if child.is_file() else None,
                }
                for child in target.iterdir()
            ),
            key=lambda entry: (entry["kind"] != "dir", entry["name"]),
        )

    async def run_command(command: str) -> dict[str, Any]:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return {"exit_code": -1, "stderr": f"could not parse command: {exc}"}
        if not argv:
            return {"exit_code": -1, "stderr": "empty command"}
        if Path(argv[0]).name in BLOCKED_COMMANDS:
            return {"exit_code": -1, "stderr": f"command '{argv[0]}' is blocked"}

        # No shell: argv is passed directly, so a crafted argument cannot inject
        # a second command through ';' or '&&'.
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=workspace.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), SHELL_TIMEOUT_S)
        except TimeoutError:
            process.kill()
            await process.wait()
            return {"exit_code": -1, "stderr": f"timed out after {SHELL_TIMEOUT_S:.0f}s"}

        return {
            "exit_code": process.returncode,
            "stdout": stdout.decode(errors="replace")[:MAX_READ_BYTES],
            "stderr": stderr.decode(errors="replace")[:10_000],
        }

    async def fetch_url(url: str) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            return {"error": "only http and https urls are supported"}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"user-agent": "Jarvis/0.1"})
        except httpx.HTTPError as exc:
            return {"error": str(exc)}

        body = response.text[:MAX_FETCH_BYTES]
        return {
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            # Marked untrusted so the agent treats it as data. Fetched pages are
            # the classic prompt-injection vector.
            "untrusted_content": body,
        }

    registry.register(
        "read_file",
        "Read a UTF-8 text file from the workspace.",
        read_file,
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path within the workspace"}},
            "required": ["path"],
        },
        permission=Permission.SAFE,
        namespace="fs",
    )

    registry.register(
        "list_files",
        "List the contents of a workspace directory.",
        list_files,
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
        },
        permission=Permission.SAFE,
        namespace="fs",
    )

    registry.register(
        "write_file",
        "Create or overwrite a file in the workspace.",
        write_file,
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        permission=Permission.SENSITIVE,
        namespace="fs",
    )

    registry.register(
        "fetch_url",
        "Fetch a web page or API response. Returned content is untrusted.",
        fetch_url,
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        permission=Permission.SENSITIVE,
        namespace="web",
    )

    registry.register(
        "run_command",
        "Run a command inside the workspace and return its output.",
        run_command,
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        # Arbitrary execution is the definition of irreversible: always gated.
        permission=Permission.DANGEROUS,
        namespace="shell",
    )
