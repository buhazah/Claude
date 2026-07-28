"""Ingestion — turning a source into retrievable, citable chunks.

Deliberate properties:

* **Re-ingesting unchanged content is free.** Documents are fingerprinted by
  content hash, so pointing Jarvis at the same folder twice does not double
  every chunk and skew retrieval toward whatever was ingested most often.
* **Unsupported formats say so.** An image or audio file produces a clear
  "not yet" rather than an empty document that silently matches nothing.
* **A folder is ingested file by file.** One unreadable file reports its error
  and the rest still land — a single corrupt PDF must not abort a repository.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import structlog

from jarvis.knowledge.chunk import chunk_blocks
from jarvis.knowledge.extract import (
    ExtractionError,
    extract_html_document,
    extract_path,
)
from jarvis.knowledge.models import DEFERRED_KINDS, Document, Extracted, SourceKind, kind_for
from jarvis.knowledge.store import KnowledgeStore

log = structlog.get_logger(__name__)

MAX_FETCH_BYTES = 2_000_000
SKIP_DIRECTORIES = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
)


@dataclass(slots=True)
class IngestResult:
    documents: list[Document] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    unchanged: list[str] = field(default_factory=list)

    @property
    def chunks(self) -> int:
        return sum(d.chunk_count for d in self.documents)

    def to_dict(self) -> dict[str, object]:
        return {
            "ingested": [
                {
                    "id": d.id,
                    "title": d.title,
                    "kind": d.kind.value,
                    "chunks": d.chunk_count,
                    "source": d.source,
                }
                for d in self.documents
            ],
            "chunks": self.chunks,
            "skipped": self.skipped,
            "unchanged": self.unchanged,
        }


def fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


class Ingestor:
    """Reads sources into the knowledge store."""

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    async def _store_extracted(
        self, extracted: Extracted, *, source: str, scope: str, size: int
    ) -> Document | None:
        """Chunk and store, unless identical content is already present."""
        digest = fingerprint(extracted.text)
        if existing := await self._store.find_by_fingerprint(digest):
            return existing if existing.source == source else None

        document = Document(
            title=extracted.title,
            source=source,
            kind=extracted.kind,
            scope=scope,
            metadata=extracted.metadata,
            bytes=size,
            fingerprint=digest,
        )
        chunks = chunk_blocks(extracted.blocks, document_id=document.id)
        if not chunks:
            return None
        return await self._store.add(document, chunks)

    async def ingest_file(self, path: Path, *, scope: str = "global") -> IngestResult:
        result = IngestResult()
        kind = kind_for(path.suffix)

        if reason := DEFERRED_KINDS.get(kind):
            result.skipped[str(path)] = f"{kind.value} needs {reason}"
            return result
        if not path.is_file():
            result.skipped[str(path)] = "not a file"
            return result

        try:
            extracted = extract_path(path)
        except ExtractionError as exc:
            result.skipped[str(path)] = str(exc)
            return result

        if not extracted.blocks:
            result.skipped[str(path)] = "no readable text"
            return result

        digest = fingerprint(extracted.text)
        if existing := await self._store.find_by_fingerprint(digest):
            result.unchanged.append(existing.title)
            return result

        document = await self._store_extracted(
            extracted, source=str(path), scope=scope, size=path.stat().st_size
        )
        if document:
            result.documents.append(document)
        return result

    async def ingest_directory(
        self, root: Path, *, scope: str = "global", max_files: int = 500
    ) -> IngestResult:
        """Walk a folder. One unreadable file never stops the others."""
        combined = IngestResult()
        if not root.is_dir():
            combined.skipped[str(root)] = "not a directory"
            return combined

        seen = 0
        for path in sorted(root.rglob("*")):
            if seen >= max_files:
                combined.skipped[str(root)] = f"stopped after {max_files} files"
                break
            if any(part in SKIP_DIRECTORIES for part in path.parts) or not path.is_file():
                continue
            if path.stat().st_size > MAX_FETCH_BYTES:
                combined.skipped[str(path)] = "too large"
                continue

            seen += 1
            one = await self.ingest_file(path, scope=scope)
            combined.documents.extend(one.documents)
            combined.skipped.update(one.skipped)
            combined.unchanged.extend(one.unchanged)
        return combined

    async def ingest_url(self, url: str, *, scope: str = "global") -> IngestResult:
        result = IngestResult()
        if not url.startswith(("http://", "https://")):
            result.skipped[url] = "only http and https urls are supported"
            return result

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"user-agent": "Jarvis/0.1"})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            result.skipped[url] = str(exc)
            return result

        body = response.text[:MAX_FETCH_BYTES]
        extracted = extract_html_document(body, source=url)
        if not extracted.blocks:
            result.skipped[url] = "no readable text"
            return result

        digest = fingerprint(extracted.text)
        if existing := await self._store.find_by_fingerprint(digest):
            result.unchanged.append(existing.title)
            return result

        document = await self._store_extracted(extracted, source=url, scope=scope, size=len(body))
        if document:
            result.documents.append(document)
        return result

    async def ingest_text(
        self,
        text: str,
        *,
        title: str,
        source: str = "pasted",
        scope: str = "global",
        kind: SourceKind = SourceKind.TEXT,
    ) -> IngestResult:
        """Ingest raw text — a pasted note, an email body, a transcript."""
        from jarvis.knowledge.models import Block

        result = IngestResult()
        blocks = [
            Block(text=part.strip(), locator=f"¶{i + 1}", order=i)
            for i, part in enumerate(text.split("\n\n"))
            if part.strip()
        ]
        if not blocks:
            result.skipped[source] = "no readable text"
            return result

        digest = fingerprint("\n\n".join(b.text for b in blocks))
        if existing := await self._store.find_by_fingerprint(digest):
            result.unchanged.append(existing.title)
            return result

        document = await self._store_extracted(
            Extracted(title=title, kind=kind, blocks=blocks),
            source=source,
            scope=scope,
            size=len(text),
        )
        if document:
            result.documents.append(document)
        return result
