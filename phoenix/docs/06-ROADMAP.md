# Phoenix — Development roadmap

Ordered by **risk retired per week**, not by dependency. The riskiest
assumptions are tested before the expensive machinery is built around them.

Every phase has an exit criterion. A phase without one never ends.

---

## Phase 0 — Foundations *(parallel, starts immediately)*

Mostly not code. **No longer the critical path** — write access is a capability,
not a gate (ADR 0006), so nothing downstream waits behind a review queue.

- **The channel port** and its conformance suite, written *before* the Meta
  adapter. This is the two weeks that makes a second channel weeks rather than a
  quarter, and it is only cheap now.
- Meta app review and business verification. **Start on day one** anyway,
  because it takes as long as it takes.
- Legal: liability under the agency model, creative IP ownership, data
  processing terms, the partner-permission model on the client's Business
  Manager.
- Control-plane skeleton: tenancy, provisioning, one isolated Jarvis instance.
- Integration ports with recorded fixtures, so everything after this runs
  offline and deterministically.

**Exit:** a client instance can be provisioned, connects to a real ad account
with read-only permissions on the client's Business Manager, the fixture adapter
and the Meta adapter both pass the same conformance suite, and the entire test
suite runs with no network.

**Risk retired:** whether this is legally and technically possible at all — and
whether the channel port is real, which is answered by two adapters passing one
suite rather than by intention.

## Phase 1 — The Observatory *(read-only, sellable alone)*

Ingest, normalise, reconcile, diagnose, report. Zero write access. Zero
autonomy. **This is the Insight tier, sold at full price.**

- Channel ingest with `as_of` snapshots (platforms restate history for ~28 days
  — get this right now or every number is wrong later)
- Shopify and Stripe ingest
- **The Truth service** — reconciliation and blended CAC from store data
- Signal detectors (deterministic)
- Diagnosis agent, grounded in snapshots
- Weekly report
- **The controlled vocabulary and the observation extractor.** Nothing consumes
  them yet. They ship now because an outcome not recorded in a resolvable shape
  is gone, and the first two years of history are the seed corpus for Phase 6
  (`08-MOAT.md §17`).

**Exit:** for three real accounts, Phoenix reproduces the client's own revenue
to within 2%, and a human reviewer agrees with its diagnosis of what moved in
8 of 10 weeks.

**Risk retired:** can we measure correctly? If not, nothing downstream means
anything. This is also the first thing that is independently sellable — *"we
will tell you what is actually working"* is a product.

## Phase 2 — The creative bake-off *(the decisive experiment)*

Not infrastructure. An experiment, run cheaply, that decides whether the
company is what `00-STRATEGY.md` says it is.

- Hypothesis → brief → concept → generation pipeline, roughest viable version
- Brand-rule validator and claim-provenance gate (both deterministic)
- Human review queue
- Manual upload — no API writes yet
- **Predictions recorded from the very first variant.** Expected effect as an
  interval, the evidence supporting it, and a kill condition. Nothing consumes
  them yet; without them the bake-off's own result cannot be scored, and there is
  no retroactive way to state a prediction after the outcome is known
  (`09-CREATIVE.md §18`).
- Run the design in `05-EVALUATION.md §7`: AI variants against a human control
  set, real spend, real account, ~3 weeks, ~£3–5k

**Exit:** a number. AI creative wins, ties, or loses against the control.

**Risk retired:** the assumption the entire business rests on, for the price of
a month's ad spend rather than a year of engineering.

> **Stop here and re-plan if AI loses on both quality and volume.** Phoenix is
> then a measurement product — still real, much smaller — and everything after
> Phase 3 should be rewritten before it is built.

## Phase 3 — The spine, in shadow *(and then in front of the client)*

The decision loop, executing nothing. **This phase now ships revenue**, because
its second half is the Recommend tier.

- Signal → Diagnosis → Proposal → Mandate check → Decision, all persisted
- The mandate model, with exhaustive tests, channel-scoped and
  capability-intersected
- Shadow-mode scoring: outcomes measured at 7/14/28 days
- Decision ledger, visible to the client
- **Recommendation delivery**: the ranked, evidenced queue in `01-PRD.md §5.5`,
  plus adoption tracking and outcome scoring on what the client applied
- Human console for escalations
- **Contribution ledger and publication outbox.** Empty of consumers until Phase
  6. Retrofitting provenance onto a knowledge base is the same class of refactor
  as retrofitting the channel abstraction, and it arrives after the data does.
- **Creative generations**: tier allocation (ADR 0009), diversity constraints,
  prediction scoring, fatigue detection, refresh-vs-retire

**Exit:** 60 days across three accounts, ≥100 scored proposals, proposal accuracy
stated per action type with the counterfactual lift — **and** ≥50% of delivered
recommendations applied by clients within 7 days.

**Risk retired:** are the decisions any good, and will anyone act on them?
Answered before a single pound moves, and the second half of that question is
one the old plan never asked.

## Phase 4 — Actuation

The first code path that can spend money. Note what it is *not*: a different
system. It is `apply()` being called on a decision that already existed.

- Actuation service: idempotency keys, retry, backoff
- Reconciler: desired vs actual, drift surfaced not overwritten
- Tier 1 autonomy (notify-after) for the two action types that scored best at
  tiers 0/R — likely budget shifts and pausing
- Immediate demotion on any breach; capability loss drops to tier R without
  demotion
- **Override capture with reason codes** at internal review and at client
  decline. Costs a dropdown; it is the input to the model that eventually keeps
  human review time flat as accounts grow (`08-MOAT.md §13`).

**Exit:** 30 days at tier 1, zero mandate breaches, zero unexplained drift, and
one client who has voluntarily moved an action type to tier 2.

**Risk retired:** can we act on real accounts without breaking them?

**Not a gate on anything before it.** If Meta write access is still pending when
Phase 3 finishes, Phases 5 and 6 proceed and Phase 4 lands when permissions do.
That reordering is the whole point of treating write access as a capability.

## Phase 5 — The operation

The parts that make it a company rather than a tool. (The agency *model* was
settled in Phase 0; this is the machinery that makes it deliverable.)

- Onboarding workflow with reconciliation as the gate
- Campaign creation and launch (mandate-gated, human approval in v1)
- Client Success and comms
- Monthly business review and mandate renewal
- Compliance gate before every ship
- Billing and margin tracking

**Exit:** a client onboarded end to end with under 8 hours of human time, and
running with under 90 human minutes a week — **flat across account sizes**, which
is the number that actually decides scalability (`07-RISKS.md` R6).

**Risk retired:** does it scale past the founder doing everything manually?

## Phase 6 — Learning

The moat, built only once there is something to learn from — which is why the
*plumbing* for it ships in Phases 1, 3 and 4 and the *intelligence* waits until
here. Full design in `08-MOAT.md`.

- **Publication gate** (ADR 0007) — deterministic, k=5, exhaustively tested,
  same discipline as the mandate checker
- Claim store: cards with scope, evidence, confidence, **decay class**
- Contradiction detection and **scope splitting** — the mechanism that makes the
  taxonomy finer over time
- **Calibration service** — reliability curves per action type, and the
  `calibration.drifted` alert that notices when the world moved
- Cards retrieved into briefs, with **utilisation persisted** so §14's metrics
  are computable
- **Unlearning**: contribution withdrawal recomputes the fleet (ADR 0008)

**Exit — two numbers, both required:**

1. **Prior-lift holdout is positive at stated confidence.** Primed briefs beat
   cold briefs across ≥10 clients. This is the moat's value as a percentage, and
   the experiment is designed to be able to return *no*.
2. **Cohort curves separate.** Clients onboarded this quarter beat clients
   onboarded four quarters ago, compared at equal tenure, on time-to-first-win
   and 30-day creative win rate.

**Risk retired:** does the company actually get smarter, or does it just
accumulate files? If both numbers come back flat, the honest response is to
delete the machinery rather than to call it an investment.

## Phase 7 — Scale, and the second channel

Only once the unit economics in `07-RISKS.md §3` are real numbers rather than
estimates.

- Fleet scheduling and per-tenant cost attribution
- Self-serve onboarding for qualified accounts
- Tier 3 autonomy where earned
- **The second channel adapter.** By now this is an adapter plus an evaluation
  suite against a conformance suite that has existed since Phase 0 — weeks, not
  a redesign. The trigger is commercial: the first client whose retention depends
  on it.

---

## Why this order

| Phase | Risk it retires | Cost if wrong later |
|---|---|---|
| 0 | Legal feasibility, and whether the channel port is real | Everything |
| 1 | Can we measure? | Every downstream number |
| 2 | **Is AI creative good enough?** | The whole company |
| 3 | Are the decisions good, and will clients act on them? | Client money and trust |
| 4 | Can we act safely? | An ad account, a client |
| 5 | Does it scale past heroics? | The margin |
| 6 | Does it compound? | The moat — and two years of unrecorded history |
| 7 | Is a second channel really weeks? | The platform-risk story in R7 |

Phase 6 is late on purpose and its *plumbing* is early on purpose. Below ~50
clients the learning machinery is overhead that cannot clear a k=5 gate; but an
outcome that was never recorded in a resolvable shape cannot be recovered, so the
vocabulary, the extractor and the ledger ship years before anything reads them.

Phases 1 and 2 are deliberately ahead of the impressive machinery. They are
cheap, they are independently sellable, and between them they answer whether
the rest is worth building.

## Definition of done, every phase

Same discipline as Jarvis:

1. Architecture written before code, trade-offs stated
2. Tests alongside the code; deterministic parts at 100% on safety paths
3. Evaluation suite extended and baselined
4. `ruff` and `mypy --strict` clean
5. ADR for any decision that would otherwise be re-argued
6. Committed with a message explaining *why*
7. **Exit criterion met and evidenced** — not "roughly done"

## What is not on this roadmap

Fine-tuning. A mobile app. A creative marketplace. Real-time bidding.
Multi-touch attribution. Holding client ad accounts or reselling media spend.

Each of the first four is a plausible good idea and each competes for the
attention that Phases 1–3 need. They can be argued for again once there is a
paying client whose retention depends on one. The last is not deferred; it is
declined.

**Google Ads and TikTok have moved off this list.** Not because they are being
built now — the *adapters* wait until Phase 7 or until a client's retention
demands one — but because the abstraction that makes them possible is Phase 0
work. Deferring the abstraction and deferring the adapter are different
decisions, and the first draft of this roadmap conflated them.
