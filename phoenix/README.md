# Phoenix

An AI-operated customer acquisition function, sold as a premium managed service,
built on Jarvis Core. **Meta is the first execution channel, not the
foundation.**

**Nothing is implemented.** This is the blueprint. The first deliverable was an
architecture coherent enough to build against, and a set of decisions worth
disagreeing with before code exists rather than after.

> ## ⛔ The architecture is frozen
>
> **Design is done. It unfreezes when a named client exposes a named
> deficiency** — [ADR 0010](docs/adr/0010-architecture-is-frozen.md),
> [`docs/10-VALIDATION.md`](docs/10-VALIDATION.md).
>
> **Build freely inside the tenant boundary. Freeze everything that crosses it.**
> One client justifies onboarding, reconciliation, the report, diagnosis,
> recommendations and creative generations. Nothing above the tenant boundary
> pays off below ~50 clients — the publication gate needs five supporting tenants
> to clear a single claim.
>
> Gaps are filed in [`docs/DEFICIENCIES.md`](docs/DEFICIENCIES.md) with a
> client's name on them. Three clients hitting the same wall unfreezes it.
>
> **The goal is no longer to design the perfect AI advertising company. It is to
> find out what makes someone pay us again next month.**

---

## Start here

**[`CHARTER.md`](CHARTER.md)** — what this company is, independent of how it is
built. Who we serve, what we refuse, what must remain true when the technology
changes completely. Everything in `docs/` is an implementation and will be wrong
eventually; the charter should not be. **It outranks every document below it.**

> The test for any proposal, permanently: *does it make us more useful, more
> checkable, or more accountable to the person paying us? If it only makes us
> more capable, it is not yet a reason to build it.*

**[`docs/11-FIRST-TEN.md`](docs/11-FIRST-TEN.md)** — the operating plan. Who the
first ten customers are, what we sell them, the fourteen-day onboarding with its
day-five gate, the weekly rhythm, the five verbs of product that actually get
built, and what stays manual on purpose. This is the document you run a Monday
from. [`10-VALIDATION.md`](docs/10-VALIDATION.md) is the reasoning behind it.

> The one question the whole phase is instrumentation for: **what is the thing
> our clients would be most upset to lose?** If five of ten give the same answer,
> that is the product.

**[`docs/00-STRATEGY.md`](docs/00-STRATEGY.md)** — the memo that argues with the
brief. Eight sections, one of them still a blocker. Everything else follows from
it.

The short version:

| The brief says | The recommendation | Status |
|---|---|---|
| Build on Jarvis Core | Jarvis Core is **single-principal by design**. Build a control plane above isolated per-client instances, or this leaks client data. | open — the blocker |
| 21 departments as agents | Departments as metaphor and namespace. **Durable workflows** as the execution spine. | proposed |
| AI optimises campaigns | Own the **complete acquisition workflow** — strategy, research, creative, orchestration, measurement, recommendations, learning. Drop only the claim to beat the auction. **Media buying is one capability, not the product.** | accepted, narrowed |
| Approval per action | **Mandates** — bounded, revocable, expiring envelopes. Per-action approval degrades into rubber-stamping. | proposed |
| Autonomy is configurable | Autonomy is **earned**, per action type, on evidence. | proposed |
| Build the company, then sell | **Test the creative assumption in week three**, for the price of a month's ad spend. | proposed |
| Meta API is an integration | Write access is a **declared capability**, not a roadmap phase. Recommendation mode is a first-class way to operate, indefinitely. | accepted, revised |
| *(added)* Meta is the platform | Meta is the **first adapter**. Strategy, creative, measurement, approvals, memory and workflows are channel-neutral. | your requirement |

## The documents

**Frozen** unless a client exposes a deficiency. `10` is the live one.

| | |
|---|---|
| **[CHARTER](CHARTER.md)** | **The company, not the software. Outranks everything below.** |
| **[11 — First ten](docs/11-FIRST-TEN.md)** | **The operating plan. ICP, offer, onboarding, weekly rhythm, what stays manual. Run Monday from this one.** |
| **[10 — Validation](docs/10-VALIDATION.md)** | The freeze, six hypotheses, three cohorts |
| [DEFICIENCIES](docs/DEFICIENCIES.md) | Where a client's name unfreezes something |
| [EFFORT LEDGER](docs/EFFORT-LEDGER.md) | Every human minute. Becomes the automation backlog |
| [00 — Strategy](docs/00-STRATEGY.md) | What I would change, and why. Read first. |
| [01 — PRD](docs/01-PRD.md) | ICP, jobs, scope, non-goals, lifecycle, success metrics |
| [02 — Architecture](docs/02-ARCHITECTURE.md) | Topology, service boundaries, data model, events, memory, integrations, security, deployment |
| [03 — Autonomy](docs/03-AUTONOMY.md) | Mandates, the decision ledger, shadow mode, failure modes |
| [04 — Departments](docs/04-DEPARTMENTS.md) | Nineteen departments: mission, KPIs, I/O, tools, boundaries, escalation |
| [05 — Evaluation](docs/05-EVALUATION.md) | Four layers, and the hardest measurement problem in the project |
| [06 — Roadmap](docs/06-ROADMAP.md) | Eight phases, ordered by risk retired, each with an exit criterion |
| [07 — Risks](docs/07-RISKS.md) | Risk register, cost model, scaling, technical debt, kill criteria |
| [08 — Moat](docs/08-MOAT.md) | What compounds when every feature has been copied, and how to prove it |
| [09 — Creative engine](docs/09-CREATIVE.md) | Discovery, prediction, generation, ranking, fatigue, retirement — and why win rate is the wrong goal |
| [ADRs](docs/adr/README.md) | Nine decisions the design depends on, and one that freezes them |

## The two ideas

> **AI proposes. Deterministic code disposes.**

No model output ever mutates external state. A model produces a typed
*proposal*; deterministic code accepts, clamps, or rejects it. Budgets, limits,
retries, reconciliation and money arithmetic are code. Research, strategy,
creative, diagnosis and prose are models.

The brief's own philosophy, sharpened until it is testable — and the reason the
blast radius of a hallucination is a rejected proposal rather than a £4,000
budget change.

> **Channels are adapters. The acquisition workflow is the platform.**

Everything that is not literally an API call to an ad platform is
channel-neutral: strategy, research, creative and its lineage, the decision
spine, mandates, approvals, memory, knowledge, workflows, reporting, evaluation.
Phoenix stores a neutral graph — `Account → Program → Group → Placement` — and
lets each adapter supply the client's own vocabulary at the display layer.

A channel declares its **capabilities**, per connection, derived from the
permissions the client granted:

| Mode | Capabilities | Delivered as |
|---|---|---|
| **Shadow** | `read.*` | nothing — internal scoring |
| **Recommend** | `read.*` | a ranked, evidenced action list the client executes |
| **Execute** | `read.*` + `write.*` | the change itself, plus the ledger entry |

One code path, two booleans. That is why read-only is a product rather than a
waiting room ([ADR 0006](docs/adr/0006-channels-are-adapters.md)).

## The moat, in one paragraph

Assume every workflow, screen, prompt and adapter is copied within two years —
they will be. What does not copy is a stock of **outcome-labelled judgment**:
what we proposed, what we expected, what actually happened, and how often we were
wrong. The engine is a rate, not an archive:

```
        evidence accrual rate in a scope
  ρ  =  ───────────────────────────────────
        decay rate of knowledge in that scope
```

Below ρ = 1 a claim rots before enough evidence accrues to make it. Scale moves
ρ — at 10 clients you can only say *"video performs"*; at 500 you can resolve a
claim narrow enough to be surprising, and keep resolving it as the world moves.
Knowledge crosses tenants only as claims aggregated over ≥5 businesses through a
deterministic gate ([ADR 0007](docs/adr/0007-knowledge-crosses-as-gated-claims.md)),
and lives in data rather than weights so a departing client can take their
contribution with them ([ADR 0008](docs/adr/0008-learning-lives-in-data-not-weights.md)).

The whole claim is falsifiable by one cheap experiment: run every new client's
first creative cycle **twice** — once with fleet priors, once cold — and compare.
If primed does not beat cold, the moat does not exist and the machinery should be
deleted. [`docs/08-MOAT.md`](docs/08-MOAT.md).

## The creative engine, in one paragraph

Creative ships in **generations** — a batch built together, tested against a
common control, resolved together — and every variant carries a **falsifiable
prediction** whose rationale is the ranking's own score decomposition, not prose
written about it afterwards. Tier allocation is fixed by policy rather than
ranked, because a single global score puts exploratory variants last every cycle,
correctly, until exploration is zero
([ADR 0009](docs/adr/0009-creative-is-a-portfolio.md)).

The counterintuitive part is the objective. **Win rate is a floor, not a target
— and it should *fall* as the engine improves**, because the control is the
frontier and the frontier is rising:

```
Generation 12   win rate 34%   control CPA £31   best new CPA £24
Generation 13   win rate 29%   control CPA £24   best new CPA £21
                     ↓                                  ↓
               looks worse                        is better
```

The headline is frontier lift, and the metric worth putting on a wall is **cost
per resolved hypothesis** — because the engine's product is knowledge, and that
prices it. [`docs/09-CREATIVE.md`](docs/09-CREATIVE.md).

## The spine

Every automated action passes through the same seven-stage pipeline:

```
Signal → Diagnosis → Proposal → Mandate check → Decision → Action → Outcome
  code       AI          AI          code        record     code    measured
```

It buys explainability, safety, shadow mode, evaluation and learning at once.
Stop after `Decision` and you have shadow mode. Compare `Outcome` against the
proposal's expected effect and you have a labelled dataset generated by
operating.

## What gets built first

Not the impressive part.

1. **Phase 0** — the **channel port and its conformance suite**, written before
   the Meta adapter; legal; control-plane skeleton. Meta app review starts now
   but gates nothing.
2. **Phase 1** — read-only: ingest, reconcile, diagnose, report. Sellable alone.
   Answers *can we measure?*
3. **Phase 2** — a **£4k creative bake-off** against a human control set.
   Answers the question the company depends on.
4. **Phase 3** — the decision loop, in shadow and then **delivered to the client
   as recommendations**. Ships revenue without write access.
5. **Phase 4** — the first code path that can spend money. Blocks nothing before
   it; lands when permissions do.

Phase 6 builds the moat, and it is late on purpose — below ~50 clients the
learning machinery cannot clear its own anonymity gate. Its **plumbing** ships in
Phases 1, 3 and 4 anyway: a vocabulary, an observation extractor, a contribution
ledger. An outcome not recorded in a resolvable shape is gone forever, and two
years of unrecorded history is the same mistake as Meta-shaped rows, made in a
different dimension.

**Under the freeze, Phases 0–1 are the whole plan.** Phases 5–7 are frozen and
unbuilt; Phases 2–4 proceed only as far as the client cohorts in
[`docs/10-VALIDATION.md §5`](docs/10-VALIDATION.md) require. The plumbing
carve-out survives — record observations, predictions, overrides and provenance
from day one, build nothing that consumes them.

Phases 1 and 2 come before the machinery because they are cheap, independently
sellable, and between them they decide whether the rest is worth building. The
channel port is in Phase 0 for the opposite reason: it is the one thing that is
cheap now and ruinous later.

## Relationship to Jarvis Core

Phoenix is an **application on a platform**, not a fork. It inherits the
workflow engine, agents-as-data, the permission wall, MCP connectors, the cost
governor, the vault, Obsidian memory, the recommendation engine and the
evaluation harness.

It adds what Core deliberately does not have: multi-tenancy, the channel port,
OAuth and capability lifecycle, webhook ingestion, time-series metrics, a
financial ledger, fleet scheduling, and reconciliation of external drift.

Core's non-goals stay non-goals. Phoenix works around them rather than through
them.

## The four decisions, answered

| Question | Answer | Where it landed |
|---|---|---|
| Accept the repositioning? | **Partially.** Own the whole acquisition workflow; drop only the claim to beat Meta's auction. Media buying is one capability. | `00-STRATEGY.md §3`, `01-PRD.md §1` |
| Agency or software? | **Agency.** Operate on the client's own Business Manager and ad accounts under granted permissions. No spend reselling, no billing scope, ever. | `01-PRD.md §11`, `07-RISKS.md` R5 |
| What is the price? | **Premium managed service.** Maintainability, reliability and measurable results over infrastructure cost. Three tiers, £1.5k–7.5k/month. | `07-RISKS.md §3` |
| Can Meta write access be obtained? | **Design for it; do not wait for it.** Write is a capability flag on a connection; recommendation mode is a supported end state. | `00-STRATEGY.md §5`, ADR 0006 |

## What is still open

1. **The blocker survives.** `00-STRATEGY.md §1` — Jarvis Core is
   single-principal. Control plane above isolated instances, or add tenancy to
   Core. Nothing should be built until this is settled, and the agency model does
   not soften it.
2. **Creative IP ownership.** Model provider terms vary and change; needs a legal
   read before Phase 2.
3. **The fee, as a number.** The tiers in `07-RISKS.md §3` are indicative. The
   architecture no longer changes if they move, which is the point.
