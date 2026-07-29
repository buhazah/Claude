# ADR 0006 — A locator travels with every chunk, from extraction to answer

**Status:** accepted · M5

## Context

Retrieval-augmented answers are only worth having if they can be checked. The
usual shortcut is to attach the *filename* to a retrieved passage and call it a
citation. That is not a citation — with a 200-page PDF it tells the reader to
go and find it themselves, and it makes a wrong answer indistinguishable from a
right one at a glance.

The temptation is to reconstruct location later: retrieve the passage, then
search the document for it to work out the page. That is fragile (the text may
appear twice, or have been normalised) and it fails silently, which is the
worst property a citation mechanism can have.

## Decision

Location is captured at extraction and carried structurally:

* **Extractors emit located blocks.** A PDF page is `p. 4`, a slide is
  `slide 2`, a sheet range is `Revenue!1:40`, a code span is `lines 1–80`, a
  Markdown section is its heading. The locator is the document's own idea of
  where something is, not a byte offset.
* **The chunker preserves it.** Packing pages 3 and 4 together yields
  `pp. 3–4`, never `p. 3`. Splitting an oversized block yields
  `p. 7 (part 2/3)`. A citation is never allowed to claim more precision, or
  more breadth, than the passage it points at.
* **Retrieval returns citations, not strings.** `Citation` carries the
  document, source, locator, snippet and the signals that surfaced it. The
  agent-facing tool returns the reference *with* the passage, so using the text
  without attributing it takes deliberate effort.

Retrieved document content is labelled `untrusted_content` for the same reason
fetched pages are: an ingested PDF is a document someone else wrote.

## Consequences

- Every extractor must decide what "where" means for its format before it can
  be added. That is a real constraint, and the right one.
- Chunk sizing is now partly a citation-quality decision, not only a retrieval
  one: bigger chunks mean vaguer locators.
- Knowledge is stored separately from memory — a 400-page PDF must not drown
  out a recorded decision — but ranked by the *same* code (ADR 0004), so "why
  did that surface?" still has one answer across the system.
- Images and audio are recognised and explicitly deferred to M7/M8 rather than
  silently ingesting as empty documents.
