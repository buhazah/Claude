"""Documents, chunks and citations.

The unit of retrieval is a **chunk**, but the unit a person recognises is a
**document**. Everything here exists to keep those connected: a chunk always
knows the document it came from and *where inside it* — page 4, slide 2,
``Sheet1!A1``, lines 40–60 — because a citation that only names the file is
not a citation, it is a shrug.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from jarvis.kernel.ids import new_id


class SourceKind(StrEnum):
    """Where a document came from. Drives extraction and re-ingestion."""

    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"
    HTML = "html"
    URL = "url"
    CODE = "code"
    IMAGE = "image"
    AUDIO = "audio"
    UNKNOWN = "unknown"


# Formats whose extraction lands in a later milestone. Named explicitly so
# ingestion can say "not yet" instead of silently producing an empty document.
DEFERRED_KINDS = {SourceKind.IMAGE: "vision (M8)", SourceKind.AUDIO: "speech-to-text (M7)"}

SUFFIX_KINDS: dict[str, SourceKind] = {
    ".txt": SourceKind.TEXT,
    ".md": SourceKind.MARKDOWN,
    ".markdown": SourceKind.MARKDOWN,
    ".rst": SourceKind.TEXT,
    ".pdf": SourceKind.PDF,
    ".docx": SourceKind.DOCX,
    ".pptx": SourceKind.PPTX,
    ".xlsx": SourceKind.XLSX,
    ".xlsm": SourceKind.XLSX,
    ".csv": SourceKind.CSV,
    ".tsv": SourceKind.CSV,
    ".html": SourceKind.HTML,
    ".htm": SourceKind.HTML,
    ".png": SourceKind.IMAGE,
    ".jpg": SourceKind.IMAGE,
    ".jpeg": SourceKind.IMAGE,
    ".gif": SourceKind.IMAGE,
    ".webp": SourceKind.IMAGE,
    ".mp3": SourceKind.AUDIO,
    ".wav": SourceKind.AUDIO,
    ".m4a": SourceKind.AUDIO,
}

CODE_SUFFIXES = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".php",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".swift",
        ".sql",
        ".sh",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".css",
        ".scss",
    }
)


def kind_for(suffix: str) -> SourceKind:
    lowered = suffix.lower()
    if lowered in SUFFIX_KINDS:
        return SUFFIX_KINDS[lowered]
    if lowered in CODE_SUFFIXES:
        return SourceKind.CODE
    return SourceKind.UNKNOWN


class Block(BaseModel):
    """One extracted region of a document, with where it came from.

    Extractors produce blocks; the chunker packs them. Keeping the locator on
    the block rather than deriving it later is what makes citations survive
    chunking.
    """

    text: str
    locator: str = ""  # human-readable: "p. 4", "slide 2", "Sheet1!A1"
    order: int = 0


class Extracted(BaseModel):
    """The result of reading a source, before chunking."""

    title: str
    kind: SourceKind
    blocks: list[Block] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


class Chunk(BaseModel):
    id: str = Field(default_factory=lambda: new_id("chk"))
    document_id: str = ""
    content: str
    locator: str = ""
    position: int = 0
    tokens: int = 0
    embedding: list[float] | None = Field(default=None, exclude=True)


class Document(BaseModel):
    id: str = Field(default_factory=lambda: new_id("doc"))
    title: str
    source: str  # path, url, or a description of where it came from
    kind: SourceKind = SourceKind.UNKNOWN
    scope: str = "global"
    metadata: dict[str, str] = Field(default_factory=dict)
    chunk_count: int = 0
    bytes: int = 0
    created_at: datetime | None = None
    # Content hash, so re-ingesting an unchanged file is a no-op.
    fingerprint: str = ""


class Citation(BaseModel):
    """A retrieved chunk, carrying enough to attribute it."""

    document_id: str
    document_title: str
    source: str
    locator: str
    snippet: str
    score: float
    signals: dict[str, float] = Field(default_factory=dict)

    def reference(self) -> str:
        """How this appears to an agent, and in an answer."""
        where = f", {self.locator}" if self.locator else ""
        return f"{self.document_title}{where}"
