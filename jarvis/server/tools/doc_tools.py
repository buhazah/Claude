"""Document export tool: turn content into a downloadable PDF / Word / text file."""
from __future__ import annotations

import re
from urllib.parse import quote

from ..config import settings
from ..files.download import sign
from ..files.generate import render
from .base import ToolParam, tool


@tool(
    "export_document",
    "Create a downloadable document from markdown content. Formats: pdf, docx "
    "(Word), txt, md. Returns a download link. Use for reports, letters, plans, "
    "summaries the user wants to keep.",
    [
        ToolParam("title", "string", "Document title (also the file name)"),
        ToolParam("content", "string", "The document body as markdown (headings, lists, paragraphs)"),
        ToolParam("format", "string", "File format", required=False, enum=["pdf", "docx", "txt", "md"]),
    ],
    timeout=45,
)
async def export_document(title: str, content: str, format: str = "pdf") -> str:
    fmt = format if format in ("pdf", "docx", "txt", "md") else "pdf"
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", title).strip() or "document"
    name = f"{safe[:60]}.{fmt}"
    path = settings.sandbox_dir / name
    i = 1
    while path.exists():
        name = f"{safe[:60]} ({i}).{fmt}"
        path = settings.sandbox_dir / name
        i += 1
    try:
        data = render(content, fmt, title)
    except Exception as exc:
        return f"Could not create the {fmt} file: {type(exc).__name__}: {exc}"
    path.write_bytes(data)
    url = f"/api/files/download/{quote(name)}?t={sign(name)}"
    kb = max(1, len(data) // 1024)
    return f"Created **{name}** (~{kb} KB). [Download it]({url})"
