# ADR 0003 — Route lexically first, arbitrate with a model only when ambiguous

**Status:** accepted · M1

## Context

Something must decide which agent handles a request. Using an LLM for every
routing decision is the simple design, but it adds a model call — latency and
cost — to every single message, including the many that are unmistakable
("fix the failing test", "draft a reply to Sarah").

## Decision

Two stages:

1. **Lexical.** Score every spec on keyword, phrase and capability matches with
   a saturating curve, nudged by the agent's rolling success rate. Free,
   deterministic, unit-testable.
2. **Arbiter.** Only when stage one is ambiguous — top confidence below
   threshold, or two candidates within 0.08 — ask a fast, cheap model to pick
   from the shortlist.

The arbiter's reply is accepted **only if it is a bare agent id**. A model that
restates the request must not be mistaken for a decision — a real failure mode
we hit and now have a regression test for.

## Consequences

- Most requests route in microseconds with no token spend.
- Routing is explainable: the API returns the matched keywords and confidence,
  which is what the command palette renders before you commit.
- Keyword lists need curation; overly generic keywords cause collisions. Every
  collision found so far became a test case, and the fix was making the *spec*
  more precise (phrases carry intent, bare generic terms are removed) rather
  than special-casing the router.
