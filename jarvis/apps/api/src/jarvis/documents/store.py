"""Where documents live.

In memory for now, behind a Protocol, exactly as every other store started
(ADR 0001) — a SQL backend is a swap, not a redesign. Copy on read and write,
because the in-memory and SQL stores must behave identically and a SQL store
returns detached objects; handing out live references made the workflow stores
diverge in M6 and is not a mistake worth making twice.
"""

from __future__ import annotations

from typing import Protocol

from jarvis.documents.models import Document
from jarvis.kernel.ids import new_id


class DocumentStore(Protocol):
    async def save(self, document: Document) -> Document: ...

    async def get(self, document_id: str) -> Document | None: ...

    async def list(self, *, limit: int = 50, mode: str | None = None) -> list[Document]: ...

    async def delete(self, document_id: str) -> bool: ...


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._order: list[str] = []

    async def save(self, document: Document) -> Document:
        if document.id not in self._documents:
            self._order.append(document.id)
        self._documents[document.id] = document.model_copy(deep=True)
        return document

    async def get(self, document_id: str) -> Document | None:
        found = self._documents.get(document_id)
        return found.model_copy(deep=True) if found else None

    async def list(self, *, limit: int = 50, mode: str | None = None) -> list[Document]:
        # Newest first, by insertion rather than by id: ids sort well but
        # insertion order is what the user watched happen.
        documents = [self._documents[i] for i in reversed(self._order) if i in self._documents]
        if mode:
            documents = [d for d in documents if d.mode == mode]
        return [d.model_copy(deep=True) for d in documents[:limit]]

    async def delete(self, document_id: str) -> bool:
        if document_id not in self._documents:
            return False
        del self._documents[document_id]
        self._order.remove(document_id)
        return True


__all__ = ["DocumentStore", "InMemoryDocumentStore", "new_id"]
