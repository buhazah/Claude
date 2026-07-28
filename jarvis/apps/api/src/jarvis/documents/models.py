"""What a generated document is.

Not a blob of markdown. A document that Jarvis produces has to survive two
things a chat answer never does: being **read by someone who was not there**,
and being **checked**.

So it is structured — an outline of sections, each written separately — and it
carries its citations as data rather than as prose. M5 made every retrieved
passage carry a locator; a document that drops that on the floor is a document
whose claims cannot be traced back, which is the same as a document whose
claims cannot be trusted.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from jarvis.kernel.ids import new_id


class DocumentKind(StrEnum):
    REPORT = "report"
    BRIEF = "brief"
    PROPOSAL = "proposal"
    MEMO = "memo"
    SPEC = "spec"
    SUMMARY = "summary"


class DocumentState(StrEnum):
    PLANNING = "planning"
    WRITING = "writing"
    COMPLETE = "complete"
    FAILED = "failed"


class Citation(BaseModel):
    """A checkable pointer back into the knowledge base."""

    document_id: str
    document_title: str
    locator: str
    reference: str
    snippet: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.document_id, self.locator)


class Section(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sec"))
    heading: str
    # What this section is *for*, written during planning and handed to the
    # model that writes it. Kept after the fact because it is the only record
    # of what the section was supposed to do.
    intent: str = ""
    body: str = ""
    citations: list[Citation] = Field(default_factory=list)

    @property
    def words(self) -> int:
        return len(self.body.split())


class Document(BaseModel):
    id: str = Field(default_factory=lambda: new_id("doc"))
    title: str
    kind: DocumentKind = DocumentKind.REPORT
    request: str = ""
    mode: str = "personal"
    state: DocumentState = DocumentState.PLANNING
    sections: list[Section] = Field(default_factory=list)
    summary: str = ""
    error: str = ""
    cost_usd: float = 0.0
    tokens: int = 0
    run_id: str | None = None
    created_at: datetime | None = None

    @property
    def words(self) -> int:
        return sum(s.words for s in self.sections)

    @property
    def citations(self) -> list[Citation]:
        """Every citation, deduplicated, in the order they were first used.

        Order matters: a bibliography sorted alphabetically tells the reader
        nothing about which claim came from where.
        """
        seen: dict[tuple[str, str], Citation] = {}
        for section in self.sections:
            for citation in section.citations:
                seen.setdefault(citation.key, citation)
        return list(seen.values())

    def summarise(self) -> dict[str, Any]:
        """The listing shape — everything but the prose."""
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind.value,
            "state": self.state.value,
            "mode": self.mode,
            "sections": len(self.sections),
            "words": self.words,
            "citations": len(self.citations),
            "cost_usd": round(self.cost_usd, 6),
            "tokens": self.tokens,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
