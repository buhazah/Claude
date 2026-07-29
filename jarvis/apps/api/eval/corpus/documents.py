"""Document generation: outline, sections, citations.

The dearest suite in the corpus — a document is an outline call plus one call
per section — so it is small and every case earns its place.

What is being measured is the *composer*, not one prompt. Three things can go
wrong independently and the report has to be able to tell them apart:

* the outline is wrong, in which case every section is answering the wrong
  question and the prose quality is irrelevant;
* the outline is right but a section drifts off its own heading;
* both are right and the citations are decorative — references that appear in
  the text but point at nothing retrieved for that section, which is the
  failure M5's structural citations exist to make impossible.

Section-level checks run against the assembled body. Outline-level checks run
against the headings, which is why `Outcome.extra` carries them separately.
"""

from __future__ import annotations

from eval.checks import Check, Outcome, mentions, no_filler, no_preamble
from eval.scoring import Case, Suite, Tier

_n = 0


def outline_between(low: int, high: int) -> Check:
    """A sane number of sections. Two is a memo; fifteen is a table of contents
    nobody asked for, and each one costs a model call."""

    def predicate(outcome: Outcome) -> bool | None:
        headings = outcome.extra.get("outline")
        if not isinstance(headings, list):
            return None
        return low <= len(headings) <= high

    return Check(f"{low}–{high} sections", predicate)


def outline_mentions(*terms: str) -> Check:
    """The outline engages with the actual question rather than producing the
    generic five-part business report every time."""

    def predicate(outcome: Outcome) -> bool | None:
        headings = outcome.extra.get("outline")
        if not isinstance(headings, list):
            return None
        joined = " ".join(str(h) for h in headings).lower()
        return any(t.lower() in joined for t in terms)

    return Check(f"outline engages with {' / '.join(terms)}", predicate)


def finished() -> Check:
    def predicate(outcome: Outcome) -> bool | None:
        state = outcome.extra.get("state")
        return None if state is None else state == "ready"

    return Check("composed to completion", predicate)


def citations_are_real() -> Check:
    """Every reference the document lists was actually retrieved.

    With an empty knowledge base the honest outcome is *no* citations, and a
    document that invents them is worse than one with none — so this is not
    applicable when nothing was ingested, and a failure when the count is
    non-zero without retrieval behind it.
    """

    def predicate(outcome: Outcome) -> bool | None:
        cited = outcome.extra.get("citations")
        retrieved = outcome.extra.get("retrieved")
        if not isinstance(cited, list) or retrieved is None:
            return None
        if not retrieved:
            return not cited
        return bool(cited)

    return Check("citations trace to retrieved passages", predicate)


def _doc(
    request: str,
    kind: str,
    *,
    behaviour: str,
    must: tuple[Check, ...] = (),
    should: tuple[Check, ...] = (),
    confidence: float = 0.6,
) -> Case:
    global _n
    _n += 1
    return Case(
        id=f"document-{_n:03d}",
        suite=Suite.DOCUMENTS,
        request=request,
        behaviour=behaviour,
        agent=kind,  # carries the DocumentKind for this suite
        must=(finished(), *must),
        should=should,
        confidence=confidence,
        tier=Tier.DOCUMENT,
    )


DOCUMENT_CASES: tuple[Case, ...] = (
    _doc(
        "A one-page brief on whether to move our supplement line to subscription pricing",
        "brief",
        behaviour="A brief is one page. The failure to watch for is a fourteen-section "
        "report wearing the word 'brief'.",
        should=(
            outline_between(2, 5),
            outline_mentions("subscription", "pricing", "recommend"),
            citations_are_real(),
            no_filler(),
        ),
        confidence=0.7,
    ),
    _doc(
        "A short report on what changed in EU cosmetics labelling rules and what we must do",
        "report",
        behaviour="Two questions in one request — what changed, and what we do about "
        "it. An outline that only covers the first has misread it.",
        should=(
            outline_between(3, 7),
            outline_mentions("action", "what we", "next", "implication", "do"),
            citations_are_real(),
        ),
        confidence=0.7,
    ),
    _doc(
        "A technical proposal for moving our event log off Postgres",
        "proposal",
        behaviour="A proposal has to end in a recommendation. An options survey with "
        "no choice is the failure the Architect prompt names.",
        should=(
            outline_between(3, 7),
            outline_mentions("recommend", "decision", "proposal", "chosen"),
            no_preamble(),
        ),
        confidence=0.6,
    ),
    _doc(
        "A summary of everything we know about our churn problem",
        "summary",
        behaviour="Nothing has been ingested about churn. The honest document says "
        "what it does not have; the dishonest one invents a churn analysis.",
        should=(
            citations_are_real(),
            mentions("no data", "not have", "unknown", "would need", "assum"),
        ),
        confidence=0.5,
    ),
)
