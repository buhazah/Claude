# Phoenix — Development roadmap

Ordered by **risk retired per week**, not by dependency. The riskiest
assumptions are tested before the expensive machinery is built around them.

Every phase has an exit criterion. A phase without one never ends.

---

## Phase 0 — Access and foundations *(parallel, starts immediately)*

Mostly not code, and it is the critical path.

- Meta app review and business verification. **Start on day one.** Weeks of
  waiting outside our control, and Phases 3+ are blocked on it.
- Legal: liability for autonomous spend, creative IP ownership, data
  processing terms, whether we hold the ad accounts or the client does.
- Decide the pricing, because `07-RISKS.md §3` is built on an assumed number.
- Control-plane skeleton: tenancy, provisioning, one isolated Jarvis instance.
- Integration ports with recorded fixtures, so everything after this runs
  offline and deterministically.

**Exit:** a client instance can be provisioned, connects to a real Meta account
read-only, and the entire test suite runs with no network.

**Risk retired:** whether this is legally and technically possible at all.

## Phase 1 — The Observatory *(read-only, sellable alone)*

Ingest, normalise, reconcile, diagnose, report. Zero write access. Zero
autonomy.

- Meta insights ingest with `as_of` snapshots (Meta restates history for ~28
  days — get this right now or every number is wrong later)
- Shopify and Stripe ingest
- **The Truth service** — reconciliation and blended CAC from store data
- Signal detectors (deterministic)
- Diagnosis agent, grounded in snapshots
- Weekly report

**Exit:** for three real accounts, Phoenix reproduces the client's own revenue
to within 2%, and a human reviewer agrees with its diagnosis of what moved in
8 of 10 weeks.

**Risk retired:** can we measure correctly? If not, nothing downstream means
anything. This is also the first thing that is independently sellable — *"we
will tell you what is actually working"* is a product.

## Phase 2 — The creative bake-off *(the decisive experiment)*

Not infrastructure. An experiment, run cheaply, that decides whether the
company is what `00-STRATEGY.md` says it is.

- Brief → concept → generation pipeline, roughest viable version
- Brand-rule validator (deterministic)
- Human review queue
- Manual upload — no API writes yet
- Run the design in `05-EVALUATION.md §7`: AI variants against a human control
  set, real spend, real account, ~3 weeks, ~£3–5k

**Exit:** a number. AI creative wins, ties, or loses against the control.

**Risk retired:** the assumption the entire business rests on, for the price of
a month's ad spend rather than a year of engineering.

> **Stop here and re-plan if AI loses on both quality and volume.** Phoenix is
> then a measurement product — still real, much smaller — and everything after
> Phase 3 should be rewritten before it is built.

## Phase 3 — The spine, in shadow

The decision loop, executing nothing.

- Signal → Diagnosis → Proposal → Mandate check → Decision, all persisted
- The mandate model, with exhaustive tests
- Shadow-mode scoring: outcomes measured at 7/14/28 days
- Decision ledger, visible to the client
- Human console for escalations

**Exit:** 60 days of shadow across three accounts, ≥100 scored proposals, and
proposal accuracy stated per action type with the counterfactual lift.

**Risk retired:** are the decisions any good? Answered before a single pound
moves.

## Phase 4 — Actuation

The first code path that can spend money.

- Actuation service: idempotency keys, retry, backoff
- Reconciler: desired vs actual, drift surfaced not overwritten
- Tier 1 autonomy (notify-after) for the two action types that scored best in
  shadow — likely budget shifts and pausing
- Immediate demotion on any breach

**Exit:** 30 days at tier 1, zero mandate breaches, zero unexplained drift, and
one client who has voluntarily moved an action type to tier 2.

**Risk retired:** can we act on real accounts without breaking them?

## Phase 5 — The agency

The parts that make it a company rather than a tool.

- Onboarding workflow with reconciliation as the gate
- Campaign creation and launch (mandate-gated, human approval in v1)
- Client Success and comms
- Monthly business review and mandate renewal
- Compliance gate before every ship
- Billing and margin tracking

**Exit:** a client onboarded end to end with under 8 hours of human time, and
running with under 60 human minutes a week.

**Risk retired:** does it scale past the founder doing everything manually?

## Phase 6 — Learning

The moat, built only once there is something to learn from.

- Outcome scoring across all clients
- Knowledge cards: claim, evidence, **scope**, confidence
- Anonymised publication to agency memory
- Contradiction detection
- Cards fed into briefs, and measured on whether they change outcomes

**Exit:** creative win rate for clients onboarded after this phase measurably
exceeds those onboarded before, at stated confidence.

**Risk retired:** does the company actually get smarter, or does it just
accumulate files?

## Phase 7 — Scale

Only once the unit economics in `07-RISKS.md §3` are real numbers rather than
estimates.

- Fleet scheduling and per-tenant cost attribution
- Self-serve onboarding for qualified accounts
- Tier 3 autonomy where earned
- Possibly a second platform — but breadth only after depth

---

## Why this order

| Phase | Risk it retires | Cost if wrong later |
|---|---|---|
| 0 | Legal and platform feasibility | Everything |
| 1 | Can we measure? | Every downstream number |
| 2 | **Is AI creative good enough?** | The whole company |
| 3 | Are the decisions good? | Client money and trust |
| 4 | Can we act safely? | An ad account, a client |
| 5 | Does it scale past heroics? | The margin |
| 6 | Does it compound? | The moat |

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

Google Ads, TikTok, LinkedIn. Fine-tuning. A mobile app. A creative
marketplace. Real-time bidding. Multi-touch attribution.

Each of them is a plausible good idea and each of them competes for the
attention that Phases 1–3 need. They can be argued for again once there is a
paying client whose retention depends on one.
