# 7. Knowledge crosses tenants as gated claims, never as data

Status: proposed

## Context

ADR 0001 isolates tenants by database because that is the only isolation a
customer's counsel believes. But `08-MOAT.md` argues the only durable advantage
is learning that accumulates *across* clients — and those two requirements point
in opposite directions.

The tempting resolutions are all bad. Reading sideways between tenants defeats
ADR 0001 outright. A shared "insights" table is the same thing with a nicer name.
Letting a model summarise one client's results into another client's brief moves
confidentiality from a boundary into a prompt, which is the failure mode this
architecture rejects everywhere else it appears.

The question is not *whether* knowledge crosses. It is what crosses, in what
shape, decided by what.

## Decision

**Knowledge crosses the tenant boundary only as a claim that has passed a
deterministic publication gate. Raw data never crosses. A model never decides
what crosses.**

The gate is the second safety boundary in Phoenix and gets the same treatment as
the first (ADR 0002's mandate checker): pure, synchronous, side-effect-free,
one place, exhaustively tested, never a prompt.

An observation is publishable only if **all** hold:

```
k-anonymity    ≥ 5 distinct tenants support the claim's scope
independence   ≥ 3 independent tests
vocabulary     every feature and scope value is in the versioned vocabulary
no verbatim    no copy, no image hash, no URL, no product or brand token
no rare scope  every scope value has ≥ 5 tenants in the fleet
measurement    reconciliation confidence ≥ 0.8 at observation time
consent        the contributing tenant's contract permits publication, now
```

Three mechanisms make this structural rather than aspirational:

**A controlled vocabulary, not free text.** Features and scopes come from a
versioned enumeration. Free text is where identity leaks — a product name, a
niche claim that identifies the brand to anyone in the category — and a fixed
vocabulary makes leakage impossible to express rather than unlikely to occur.
It is checkable by a test, which free text is not.

**Generalise or suppress, never fail.** A claim too narrow to be anonymous is
retried at its parent scope; if it fails there it stays tenant-local, where it
still serves the client moat. Nothing is lost, it just does not travel — so
there is never pressure to weaken the gate to avoid losing a finding.

**The control plane pulls from a tenant outbox.** No control-plane service holds
a tenant database credential; no tenant can reach another. The blast radius of a
fully compromised control plane is the set of outboxes, which contain only
observations already shaped for publication.

## Alternatives rejected

**A model summarises cross-client learnings.** The obvious build, and it puts
confidentiality inside a prompt. A prompt can be argued with; a validator cannot.
Same reasoning as the mandate checker.

**Formal differential privacy.** Correct in principle. At our n, a meaningful ε
destroys the signal — and the claims are already aggregates over ≥5 tenants and
≥3 tests, reported in buckets, against an adversary (a competitor reading a card)
far weaker than DP's threat model. **Revisit at 500+ tenants**, where cell sizes
make it affordable. Recorded in `07-RISKS.md §5` with that trigger.

**Federated learning with secure aggregation.** Real, and heavy. It solves a
problem we do not yet have, at a complexity we cannot yet justify. Same trigger
as above.

**Publish nothing; every tenant learns alone.** Defensible, and it forfeits the
entire fleet moat. It also fails its own goal: clients ask to benefit from what
we have learned elsewhere, and answering "we deliberately do not" loses deals to
firms who answer yes and mean it carelessly.

## Consequences

- **Cross-client learning becomes a defensible sentence to a client's counsel:**
  aggregated over five or more businesses, category-level, no content, consented,
  revocable, and enforced by code we can show you.
- **The first ~50 clients contribute more than they receive.** k=5 blocks most
  claims until the fleet is wide. That is the shape of the asset, not a defect —
  and it is why `08-MOAT.md §17` builds the plumbing early and the intelligence
  late.
- **Some genuinely useful knowledge is permanently unpublishable.** A brilliant
  finding from one client stays with that client. Accepted: it still compounds
  in the client moat, which is the moat that holds revenue.
- **The vocabulary becomes a versioned, load-bearing artefact.** Observations
  record which version tagged them, so a revision does not silently invalidate
  history. Extending it is a schema change with a migration, deliberately.
- **The gate needs the same test discipline as the mandate checker** — every
  boundary, every threshold, every off-by-one. A leak here is a confidentiality
  incident, and unlike a bad budget change it cannot be reversed.
