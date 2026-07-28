"""Document generation: outline, sections, and citations that survive.

The claim this milestone makes is that a generated document is *attributable* —
every section says which passages it was written from. So the tests that matter
are about citations being real: captured from what the section was handed, not
invented afterwards, and dropped when the section did not use them.
"""

from __future__ import annotations

import pytest

from jarvis.documents.compose import parse_outline
from jarvis.documents.models import Citation, Document, DocumentKind, DocumentState, Section
from jarvis.documents.render import to_html, to_markdown
from jarvis.documents.store import InMemoryDocumentStore
from jarvis.kernel import container
from jarvis.llm.providers.echo import EchoProvider

# ── The outline ───────────────────────────────────────────────────────────────


def test_a_clean_outline_is_read() -> None:
    outline = parse_outline(
        '{"title": "Q3 review", "sections": ['
        '{"heading": "Revenue", "intent": "establish the number"},'
        '{"heading": "Risks", "intent": "what could break it"}]}',
        fallback_title="x",
    )
    assert outline.title == "Q3 review"
    assert [h for h, _ in outline.sections] == ["Revenue", "Risks"]
    assert outline.sections[0][1] == "establish the number"


@pytest.mark.parametrize(
    "wrapped",
    [
        '```json\n{"title": "T", "sections": [{"heading": "A"}]}\n```',
        'Here is the outline:\n{"title": "T", "sections": [{"heading": "A"}]}',
        '```\n{"title": "T", "sections": [{"heading": "A"}]}\n```\nHope that helps!',
    ],
)
def test_the_ways_models_wrap_json_are_tolerated(wrapped: str) -> None:
    """Not defensive clutter: every provider does at least one of these."""
    assert parse_outline(wrapped, fallback_title="x").title == "T"


@pytest.mark.parametrize("junk", ["", "I could not do that", "{{{", '{"sections": []}'])
def test_an_unusable_outline_degrades_to_one_section(junk: str) -> None:
    """The user asked for a document. One badly-shaped document beats an error."""
    outline = parse_outline(junk, fallback_title="The thing they asked for")
    assert outline.title == "The thing they asked for"
    assert len(outline.sections) == 1


def test_headings_without_text_are_dropped() -> None:
    outline = parse_outline(
        '{"title": "T", "sections": [{"heading": "A"}, {"heading": "  "}, {"heading": "B"}]}',
        fallback_title="x",
    )
    assert [h for h, _ in outline.sections] == ["A", "B"]


# ── Citations ─────────────────────────────────────────────────────────────────


def _cite(n: int) -> Citation:
    return Citation(
        document_id=f"doc{n}",
        document_title=f"Source {n}",
        locator=f"p. {n}",
        reference=f"Source {n}, p. {n}",
        snippet="...",
    )


def test_a_documents_bibliography_is_deduplicated_in_first_use_order() -> None:
    """Alphabetical order would tell the reader nothing about which claim came
    from where."""
    document = Document(
        title="T",
        sections=[
            Section(heading="A", citations=[_cite(2), _cite(1)]),
            Section(heading="B", citations=[_cite(1), _cite(3)]),
        ],
    )
    assert [c.document_id for c in document.citations] == ["doc2", "doc1", "doc3"]


def test_the_same_document_cited_at_two_locators_is_two_citations() -> None:
    """Page 4 and page 90 of the same book are different claims."""
    document = Document(
        title="T",
        sections=[
            Section(
                heading="A",
                citations=[
                    Citation(
                        document_id="d",
                        document_title="Book",
                        locator="p. 4",
                        reference="Book, p. 4",
                    ),
                    Citation(
                        document_id="d",
                        document_title="Book",
                        locator="p. 90",
                        reference="Book, p. 90",
                    ),
                ],
            )
        ],
    )
    assert len(document.citations) == 2


async def test_only_the_passages_a_section_actually_used_are_cited(jarvis, clock) -> None:
    """Handing a section four passages and listing all four regardless would
    make the bibliography a claim nobody checked."""
    await jarvis.ingestor.ingest_text(
        "The pricing floor for enterprise accounts is a 40 percent gross margin. "
        "Renewals below that threshold require the finance lead to sign off.",
        title="Pricing policy",
    )

    seen: list[Document] = []
    async for event, document, _ in jarvis.composer.compose(
        "What is our pricing floor?", kind=DocumentKind.BRIEF
    ):
        if event in ("done", "error"):
            seen.append(document)

    assert seen, "composition must terminate"
    final = seen[-1]
    assert final.state is DocumentState.COMPLETE

    # The echo provider replays the brief, so any passage it was handed appears
    # in the body — but only bracketed markers count as citations.
    for section in final.sections:
        for index, _ in enumerate(section.citations, start=1):
            assert f"[{index}]" in section.body


async def test_a_document_with_no_knowledge_says_so_rather_than_inventing(jarvis) -> None:
    """An empty knowledge base must produce an unsourced document, not a
    confidently sourced one."""
    finals = [
        document
        async for event, document, _ in jarvis.composer.compose("Write a memo about nothing")
        if event == "done"
    ]
    assert finals
    assert finals[0].citations == []
    assert finals[0].state is DocumentState.COMPLETE


# ── Composition ───────────────────────────────────────────────────────────────


async def test_composition_streams_the_outline_before_any_prose(jarvis) -> None:
    """The outline landing first is when the user can tell it is going wrong."""
    events = [
        event async for event, _, _ in jarvis.composer.compose("Report on oat milk competitors")
    ]
    assert events[0] == "outline"
    assert events[-1] == "done"
    assert "section" in events


async def test_every_section_gets_written(jarvis) -> None:
    finals = [d async for event, d, _ in jarvis.composer.compose("Brief on Q3") if event == "done"]
    document = finals[0]
    assert document.sections
    assert all(s.body for s in document.sections), "a section with no body is a missing section"
    assert document.words > 0


async def test_a_document_records_what_it_cost(jarvis) -> None:
    finals = [d async for event, d, _ in jarvis.composer.compose("Brief on Q3") if event == "done"]
    assert finals[0].tokens > 0


async def test_the_composer_uses_the_requested_agent_without_widening_it(settings, clock) -> None:
    """A composed section runs through the ordinary runtime, so it is subject
    to the same tool wall as anything else that agent does."""
    system = container.build(settings, providers=[EchoProvider()], clock=clock)
    spec = system.agents.get("research")

    finals = [
        d
        async for event, d, _ in system.composer.compose("Brief", agent_id="research")
        if event == "done"
    ]
    assert finals
    # The agent's own allowlist is unchanged by having composed something.
    assert system.agents.get("research").tools == spec.tools


async def test_an_unknown_agent_falls_back_rather_than_failing(jarvis) -> None:
    finals = [
        d
        async for event, d, _ in jarvis.composer.compose("Brief", agent_id="not_an_agent")
        if event == "done"
    ]
    assert finals and finals[0].state is DocumentState.COMPLETE


# ── Rendering ─────────────────────────────────────────────────────────────────


def _document() -> Document:
    return Document(
        title="Q3 review",
        kind=DocumentKind.REPORT,
        sections=[
            Section(heading="Revenue", body="Revenue grew 12% [1].", citations=[_cite(1)]),
            Section(heading="Risks", body="Two suppliers dominate.\n\nBoth renew in Q4."),
        ],
    )


def test_markdown_carries_headings_body_and_sources() -> None:
    rendered = to_markdown(_document())
    assert "# Q3 review" in rendered
    assert "## Revenue" in rendered
    assert "Revenue grew 12% [1]." in rendered
    assert "## Sources" in rendered
    assert "1. Source 1, p. 1" in rendered


def test_html_is_self_contained_and_escapes_the_body() -> None:
    """A document goes to other people. It must not carry script with it."""
    document = _document()
    document.sections[0].body = "<script>alert('x')</script> and 5 < 6"
    rendered = to_html(document)

    assert "<script>alert" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "5 &lt; 6" in rendered
    assert "http://" not in rendered and "https://" not in rendered, "no external assets"
    assert rendered.startswith("<!doctype html>")


def test_html_turns_blank_line_blocks_into_paragraphs() -> None:
    rendered = to_html(_document())
    assert "<p>Two suppliers dominate.</p>" in rendered
    assert "<p>Both renew in Q4.</p>" in rendered


def test_a_document_with_no_citations_has_no_empty_sources_section() -> None:
    document = Document(title="T", sections=[Section(heading="A", body="Body.")])
    assert "Sources" not in to_markdown(document)
    # The stylesheet always mentions `.sources`; what must not appear is the
    # element itself.
    assert '<section class="sources">' not in to_html(document)


# ── The store ─────────────────────────────────────────────────────────────────


async def test_the_store_hands_out_copies_not_live_references() -> None:
    """In-memory and SQL stores must behave identically; a SQL store returns
    detached objects. Handing out live references made the workflow stores
    diverge in M6."""
    store = InMemoryDocumentStore()
    saved = await store.save(Document(title="Original"))

    fetched = await store.get(saved.id)
    assert fetched is not None
    fetched.title = "Mutated"

    again = await store.get(saved.id)
    assert again is not None and again.title == "Original"


async def test_documents_list_newest_first_and_filter_by_mode() -> None:
    store = InMemoryDocumentStore()
    await store.save(Document(title="First", mode="personal"))
    await store.save(Document(title="Second", mode="business"))

    assert [d.title for d in await store.list()] == ["Second", "First"]
    assert [d.title for d in await store.list(mode="business")] == ["Second"]


async def test_deleting_a_document_removes_it_once() -> None:
    store = InMemoryDocumentStore()
    document = await store.save(Document(title="T"))

    assert await store.delete(document.id) is True
    assert await store.delete(document.id) is False
    assert await store.get(document.id) is None
    assert await store.list() == []
