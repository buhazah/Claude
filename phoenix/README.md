# Phoenix

An AI-operated customer acquisition function, sold as a premium managed service,
built on Jarvis Core. **Meta is the first execution channel, not the
foundation.**

**Nothing is implemented.** This is the blueprint. The first deliverable is an
architecture coherent enough to build against, and a set of decisions worth
disagreeing with before code exists rather than after.

*Revision 2 — incorporates the five directions given after the first draft: own
the complete acquisition workflow, operate as an agency on the client's own
accounts, price as a premium managed service, treat write access as a capability
rather than a phase, and keep the core channel-agnostic.*

---

## Start here

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

| | |
|---|---|
| [00 — Strategy](docs/00-STRATEGY.md) | What I would change, and why. Read first. |
| [01 — PRD](docs/01-PRD.md) | ICP, jobs, scope, non-goals, lifecycle, success metrics |
| [02 — Architecture](docs/02-ARCHITECTURE.md) | Topology, service boundaries, data model, events, memory, integrations, security, deployment |
| [03 — Autonomy](docs/03-AUTONOMY.md) | Mandates, the decision ledger, shadow mode, failure modes |
| [04 — Departments](docs/04-DEPARTMENTS.md) | Nineteen departments: mission, KPIs, I/O, tools, boundaries, escalation |
| [05 — Evaluation](docs/05-EVALUATION.md) | Four layers, and the hardest measurement problem in the project |
| [06 — Roadmap](docs/06-ROADMAP.md) | Eight phases, ordered by risk retired, each with an exit criterion |
| [07 — Risks](docs/07-RISKS.md) | Risk register, cost model, scaling, technical debt, kill criteria |
| [ADRs](docs/adr/README.md) | The six decisions everything else depends on |

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
