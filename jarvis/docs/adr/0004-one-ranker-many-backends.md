# ADR 0004 — Ranking is shared code; only candidate retrieval is per-backend

**Status:** accepted · M3

## Context

Adding Postgres+pgvector alongside the in-memory store creates an obvious
temptation: push the hybrid recall scoring into SQL, where pgvector can order
by distance and the database does the work.

Doing that would give Jarvis two implementations of *what counts as relevant*.
They would drift — a weight tweaked in Python and not in SQL, a tiebreak
handled differently — and "why did Jarvis recall that?" would have a different
answer depending on which backend was deployed. Recall order is product
behaviour, not an implementation detail.

## Decision

Split recall into two phases with a hard line between them:

1. **Candidate retrieval** is per-backend. Postgres uses an HNSW ANN scan
   unioned with a lexical `ILIKE` match; SQLite takes a bounded recency window;
   the in-memory store takes everything. Each narrows to a superset.
2. **Ranking** is `jarvis.memory.ranking`, shared by all three, scoring
   lexical + semantic + recency and weighting by salience.

The union in the Postgres path is load-bearing. An exact identifier
(`zephyr-7`) can sit far away in embedding space, so an ANN-only candidate set
would never let the ranker see it — the lexical arm is what makes hybrid recall
actually hybrid rather than nominally so.

## Consequences

- The same contract test suite runs against memory, SQLite and Postgres and
  asserts identical behaviour. That test is only meaningful *because* ranking
  is shared.
- Adding a backend can change performance but cannot change results.
- Ranking cost is O(candidates) in Python rather than in the database. At a
  personal-scale corpus this is microseconds; if it ever stops being, the fix
  is a tighter candidate set, not a second ranker.
