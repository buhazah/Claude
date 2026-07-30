# Phoenix — Risks, cost model, scaling, technical debt

---

## 1. Business risks

Ordered by how likely they are to kill the company.

### R1 — Meta commoditises the work *(likely, moderate impact — downgraded)*
Advantage+ already absorbed most of media buying. If Meta ships better automated
creative generation, the creative wedge narrows too.

**Why this is now moderate rather than high.** Two decisions changed the
exposure. Owning the **complete acquisition workflow** means Meta would have to
commoditise strategy, cross-channel measurement against the client's own store,
compliance, governance and institutional memory — not one stage of it. And a
**channel-agnostic core** means Meta commoditising Meta does not commoditise
Phoenix; it commoditises one adapter. A platform absorbing its own layer is
precisely the scenario the abstraction in ADR 0006 was bought for.

**What is genuinely not defensible:** any claim to beat the auction. That claim
is dropped in `00-STRATEGY.md §3`.

**Mitigation:** keep the defensible layer — measurement against the client's own
revenue, offer strategy, operational safety, and cross-channel knowledge — and
make sure none of it lives inside an adapter. Over time the layer that actually
compounds is the accumulated judgment in `08-MOAT.md`: a platform can commoditise
a capability, but it cannot hand a competitor ten thousand outcome-labelled
decisions taken on advertisers' behalf.

**Leading indicator:** creative win rate against the platform's own generated
assets. Track from Phase 2.

### R2 — AI creative is not good enough *(unknown, existential)*
The assumption everything rests on.

**Mitigation:** Phase 2 tests it for ~£4k in week three, with a written
decision rule for each of the three outcomes.

**Reframed slightly by `09-CREATIVE.md`:** the question is not whether a model
writes a better ad than a human — increasingly it will, for everyone, at no
advantage to us. It is whether a system that generates, predicts, tests, scores
and retires at volume moves a client's frontier faster than a studio does. That
is a question about the machinery around the generation, not about the
generation, and it is the version of R2 worth betting on.

### R3 — Nobody trusts an AI with their ad spend *(likely, now manageable)*
Rational customer behaviour, not a marketing problem.

**Mitigation:** recommendation mode is a better answer than shadow mode alone,
because the client sees the proposals and keeps their hands on the controls.
Sell Insight and Recommend first; earn write authority on evidence, per action
type. The decision ledger is the trust product.

The pricing structure now reflects this rather than fighting it: a client who
never grants write access is a full-price Recommend client, not a stalled sale.

### R4 — Ad account ban *(possible, severe per client)*
A policy strike can end a client relationship in an afternoon, and appeals run
on the platform's timetable, not ours.

**Mitigation:** compliance gate before every ship, scored on **recall** not
precision; conservative claim handling; never auto-resume a policy pause; never
hold billing permissions. Under the agency model the account is the client's, so
a strike is contained to one relationship rather than to an app that serves all
of them.

### R5 — Liability for the results of our decisions *(certain to arise, now bounded)*
Phoenix will eventually lose someone money. The question is whether the contract
answered it in advance.

**The agency model narrows this substantially.** The client is the advertiser of
record; the accounts, the billing relationship and the platform terms are
theirs. We act on instruction inside an envelope they set and can revoke, and we
never front or resell media, so there is no exposure on spend itself.

**Mitigation, settled before the first mandate:** mandate ceilings double as
contractual liability caps stated in the same numbers; the decision ledger is
the evidentiary record; professional indemnity insurance sized against the
aggregate of live mandate ceilings, not against revenue. Detail in
`01-PRD.md §11`.

**What remains genuinely open:** negligent *advice*. Recommendation mode moves
execution to the client but does not make bad advice free, and a premium fee
raises what a client reasonably expects of it. That is an insurance and
contract-drafting problem, not an architecture one.

### R6 — Services margin, not software margin *(likely — and partly accepted)*
If every client needs eight hours of human time a week, this is an agency with a
large AI bill.

**Reframed by the pricing decision.** At a premium fee, 2–4h/week of senior human
time is affordable and is part of what is sold; `07-RISKS.md §3` budgets it
rather than trying to eliminate it. The failure mode is not "this is services" —
it is **human time that scales with client spend**, which caps the business at
however many clients the founder can personally watch.

**Mitigation:** track human-minutes-per-client-per-week against *account size*,
not just in absolute terms, from Phase 5. Flat is the target. Rising with spend
is the kill signal.

### R7 — A platform cuts off API access *(unlikely per channel, no longer fatal)*
Platform risk in its purest form — and the one risk the channel abstraction was
bought to survive.

**Mitigation:** comply meticulously, and keep everything above the channel port
free of platform concepts so that losing one adapter is a commercial loss rather
than a rebuild. Being an agency operating on client accounts also means the
exposure is per client's Business Manager rather than one app whose suspension
ends every relationship simultaneously.

**Honestly stated:** if the first adapter is the only one built, this is still
close to fatal in the short term, because the second adapter is weeks of work we
would be doing under duress with no revenue. The abstraction converts an
extinction event into a bad quarter, which is worth what it costs — but it is
not the same as being diversified.

## 2. Technical risks

| | Risk | Likelihood | Mitigation |
|---|---|---|---|
| T1 | **Jarvis Core is single-principal.** Multi-client on one instance leaks data. | Certain | Control plane + isolated instances (ADR 0001). Non-negotiable. |
| T2 | Attribution is unreliable, so optimisation targets a wrong number | Certain | Truth service; reconciliation confidence gates the whole loop |
| T3 | External state drift — humans edit in Ads Manager, Meta auto-pauses | Certain | Reconciler surfaces drift, never blind-reapplies |
| T4 | Double-spend on retry after timeout | Likely | Idempotency keys on every write, tested by replay |
| T5 | Meta restates history inside the attribution window | Certain | Append-only snapshots with `as_of`; every quoted figure carries its date |
| T6 | Rate limits under fleet load | Likely | Per-tenant limiter, backoff, scheduled off-peak |
| T7 | Token expiry / revocation looks like a rate limit | Likely | Explicit connection health; loud degradation, never stale numbers |
| T8 | Prompt injection via competitor pages, reviews, ad comments | Likely | Jarvis's untrusted-content posture; no content can elevate a permission |
| T9 | AI cost per client exceeds margin | Unlikely at premium pricing | Cost governor per tenant, checked before each call; creative generation is the line item to watch |
| T10 | Multi-agent cost and latency explosion | Likely if departments talk | Workflow spine, not conversation (ADR 0004) |
| T11 | Evaluation corpus rots as the environment moves | Certain | Cases generated from history; baselines re-cut with justification |
| T12 | A model writes a number it was not given | Likely | `report` suite: any figure not passed in is a hard failure |
| T13 | **The channel abstraction leaks** — a Meta concept reaches strategy, mandates or memory | Likely without enforcement | Import-graph test in CI (ADR 0006); `native` in a prompt or report is a bug; conformance suite is written before the first adapter |
| T14 | The neutral graph cannot express something a channel needs | Certain, eventually | `native` escape hatch and adapter-namespaced verbs, both opt-in; `unsupported` verdict rate is tracked so the gap is visible rather than worked around |
| T15 | Capabilities and mandates drift apart — we believe we can write and cannot | Likely | Capabilities re-derived on every token refresh; authority is the intersection, never the union; action type falls to tier R rather than failing |
| T16 | **A claim leaks a client** through a scope narrow enough to identify them | Possible | Deterministic publication gate: k=5 tenants, controlled vocabulary, no verbatim, generalise-or-suppress (ADR 0007). Tested like the mandate checker. Irreversible if it happens. |
| T17 | The fleet learns a house style rather than what works | Likely without a counterweight | Mandatory 15% exploration quota that bypasses the filter; the filter scored against live outcomes, never against reviewer agreement (`08-MOAT.md §13`) |
| T18 | Stale cards recalled into briefs after the environment moved | Certain | Decay class with arithmetic confidence decay; platform-mechanical claims not stored as knowledge at all; `calibration.drifted` as the fleet-wide early warning |
| T19 | We believe the moat exists because we built it | **The most probable failure here** | The prior-lift holdout is designed to be able to return "no" (`08-MOAT.md §14`), and it runs every fourth cycle rather than once |
| T20 | **Exploration is ranked out of existence** while every decision looks correct | Certain under a single global score | Fixed tier allocation with a 10% hard floor (ADR 0009); explore-tier share of frontier jumps is a tracked diagnostic |
| T21 | A hypothesis is credited for a win its execution earned | Likely | ≥3 independent executions before a hypothesis becomes knowledge (`09-CREATIVE.md §13`) |
| T22 | A good angle is retired for execution fatigue | Likely without the check | Refresh ≠ retire; the cohort-wide exclusion means a market-wide decline is never diagnosed as fatigue |

T1 and T2 are the two that must be solved before anything else is built on top
of them. T13 is the one that is cheap now and very expensive in a year.

## 3. Cost model — premium managed service

**The pricing decision is taken: Phoenix is priced as a premium managed
service.** The architecture optimises for maintainability, reliability and
measurable results; infrastructure efficiency is a constraint, not an objective.

Two facts set the frame. First, under the agency model there is **no media
markup** — the client pays the platform directly, so the fee alone carries the
business. Second, the ICP spends £10k–£100k/month; a fee that is 10–20% of
media is both conventional in the category and comfortably above what these
numbers require.

### The offer, in tiers

| Tier | What the client gets | Needs | Indicative fee |
|---|---|---|---|
| **Insight** | Ingest, reconciliation, diagnosis, weekly report | read only | £1,500–2,500/mo |
| **Recommend** | The above, plus the full decision loop delivered as ranked, evidenced actions they execute, plus the creative pipeline | read only | £3,000–4,500/mo |
| **Managed** | The above, plus execution under mandate | read + write | £5,000–7,500/mo |
| Onboarding | Discovery, tracking verification, 90-day baseline, first strategy | — | £3,000–5,000 one-off |

Two things this structure buys that a single price does not. **Recommend is a
real tier, not a discount** — it is most of the work, and pricing it as a
consolation prize would be pricing our own read-only mode as a failure. And
**Managed is priced on accountability, not on labour saved**; the increment
between Recommend and Managed is what it costs to be responsible for the change.

### Per client per month, at steady state, Managed tier

Numbers are deliberately *generous* rather than lean. Where a cheaper option
exists and is worse, this model assumes we buy the better one.

| Line | Estimate | Notes |
|---|---|---|
| Creative generation | £150–400 | 40–60 variants using the best available models, not the cheapest. **The dominant and most variable line.** |
| Exploration cost | *(in media, not COGS)* | ~20% of creative spend goes to variants expected to lose. The price of a moving frontier (ADR 0009), bounded by the share-of-spend-on-losers constraint |
| LLM — research, strategy, briefs | £40–90 | Front-loaded at onboarding; frontier models, long context |
| LLM — diagnosis and proposals | £30–70 | Daily. Frontier model on the reasoning step — this is the one that must be right |
| LLM — reports and comms | £15–35 | Weekly, prose only |
| Embeddings and memory | £10–25 | |
| Evaluation runs | £20–50 | Nightly corpus, per-tenant cases. Not optional, therefore a line item |
| Infrastructure — instance, DB, storage | £60–120 | Isolation, plus headroom rather than right-sizing |
| **AI + infra subtotal** | **£325–790** | |
| Human — success, creative review, exceptions | £600–1,400 | 2–4h/week at a loaded senior rate. **Budgeted, not minimised.** |
| **Total COGS** | **£925–2,190** | |
| **Gross margin at £6,000** | **64–85%** | |
| **Gross margin at £3,750 (Recommend)** | **~55–75%** | Lower COGS too — no actuation, less review |

### What the numbers say

**Premium pricing buys correctness, and correctness is the product.** At
£925–2,190 COGS against a £6,000 fee there is no pressure to route diagnosis to
a cheap model, skip the evaluation run, or share a database between tenants. Every
one of those savings is worth £30–80/month and costs credibility that is worth
the whole account. That is the entire argument for not optimising the price
downward.

**Creative generation is the cost centre, not the LLM calls.** Text is cheap;
images and video are not. Two consequences that survive premium pricing because
they improve quality as well as cost: cache and reuse aggressively via lineage,
and generate in tiers — cheap models to *explore*, expensive ones only for
concepts that survive internal filtering. That is a better creative process, not
just a cheaper one.

**Human time is budgeted at 2–4h/week, not squeezed toward zero.** At a premium
fee, a senior human reviewing creative and handling exceptions is affordable and
is part of what is being bought. The number that matters is not whether it falls
to one hour; it is whether it stays *flat* as accounts get larger. Human time
that scales with client spend is the thing that breaks the model.

**The isolation tax is now explicitly accepted.** £60–120/client for a separate
instance and database is not a cost to engineer away. It is the confidentiality
story, and at a premium fee it rounds to nothing. Revisit at 200+ clients, not
before.

**What premium pricing does not excuse.** A higher fee raises the bar on
reliability and evidence rather than lowering it: a client paying £6,000/month
who receives a wrong number churns faster than one paying £900, not slower.
Every zero-tolerance metric in `05-EVALUATION.md §8` gets stricter here, not
looser.

### Break-even sketch

Fixed costs — control plane, two engineers, tooling, insurance — call it
£28k/month. At a £4,500 blended fee and 70% gross margin, break-even is roughly
**9 clients**. At 20 clients the operation supports a second engineer and a
dedicated client-success hire. These are estimates against an indicative price,
not a forecast, and the sensitivity that matters is human hours per client, not
infrastructure.

## 4. Scaling

**1–10 clients.** Everything manual that can be. One instance per client. The
founder reviews every creative batch. Optimise for learning, not efficiency.

**10–50.** Human time per client is the binding constraint. Automate review
triage, not review. Fleet scheduling from the control plane. Per-tenant cost
attribution becomes necessary rather than nice.

**50–200.** Instance-per-tenant starts to show: provisioning, migrations,
per-instance idle cost. At premium pricing the infra cost is not the reason to
change — *operational* cost is. Automate provisioning and migration rollout
before considering pooling. This is also the range where a second channel adapter
becomes a retention question rather than a roadmap item.

**200+.** Different company. Rate limits, platform partnership terms, pooled
tenancy, and a support organisation all become first-order problems.

**What scales badly and should be watched:** anything requiring a human to look
at every unit of output. Creative review is the obvious one, which is why the
internal filter in `04-DEPARTMENTS.md` exists and why its job is to make the
human review twenty candidates rather than two hundred.

## 5. Technical debt strategy

Debt is a loan. The question is only whether it is recorded and priced.

**Debt taken deliberately, in the roadmap:**

| Debt | Why | Repayment trigger |
|---|---|---|
| Instance-per-tenant | Isolation beats efficiency, and premium pricing pays for it | >200 clients, or infra cost >10% of revenue |
| **One adapter**, not one architecture | Depth before breadth — but the *port* is not deferred | A client's retention depends on a second channel |
| Manual creative review | We do not know what to automate yet, and at this price we can afford not to | Review time >4h/client/week, or rising with account size |
| No fine-tuning on client data | Unlearning is impossible in weights and mechanical in data (ADR 0008) | **Never** for tenant data. Task-specific models trained on *published cards only*, with a retrain-from-ledger path, may be revisited if measured lift justifies it |
| k-anonymity + suppression rather than formal differential privacy | DP with a meaningful ε destroys signal at our n; claims are already ≥5-tenant aggregates in buckets | 500+ tenants, where cell sizes make DP affordable (ADR 0007) |
| No federated learning | Solves a problem we do not have, at complexity we cannot justify | Same trigger as above |
| Counterfactual scoring in shadow | Cheaper than universal holdouts | When a decision's stakes justify a real holdout |
| Human onboarding | The first fifty teach us the workflow | >2 onboardings/week |

**Debt that will not be taken, at any point:**

- shortcuts in the mandate checker
- money arithmetic in floats
- a shared database across tenants
- a model computing a number that reaches a client
- an approval path around the hard floor in `03-AUTONOMY.md §3`
- a channel concept above the channel port
- a model deciding what crosses the tenant boundary
- learned state that cannot be recomputed without a departing tenant

Those eight are the invariants. Everything else is negotiable under deadline.

The last one is new and is the easiest to breach under deadline, because every
individual breach looks harmless: one Meta field on a report, one `campaign_id`
in a prompt, one adapter import in the strategy service. It is enforced the same
way Jarvis enforces its kernel rule — by a test in CI, not by intention.

**The repayment discipline:** every deliberate debt gets a row in this table
with a trigger. A debt without a trigger is not debt; it is a decision nobody
admitted to making.

**Under the architecture freeze (ADR 0010) this table gets busier, on purpose.**
Shipping to the first twenty clients will produce per-client special cases, and
the deal is explicit: a hack is fine, a hack nobody wrote down is how the
untangling later becomes impossible. Manual effort is the preferred workaround
and is tracked in the effort ledger (`10-VALIDATION.md §6`), which keeps the
codebase clean and converts each gap into data. The eight invariants above are
the part that does not bend — shipping pressure is precisely the condition they
were written for.

## 6. What would make me abandon this

Stated in advance, because the time to write the kill criteria is before you
are emotionally invested:

1. **Clients will not pay a premium fee for Recommend, and will not grant write
   access either.** This is the replacement for the old "Meta write access is
   refused" criterion, and it is a better test: write access being slow is
   survivable, but a market that values neither the analysis nor the execution
   has told us the workflow is not the product.
2. **AI creative loses badly in Phase 2** *and* the volume advantage does not
   compensate. The wedge is gone.
3. **Human time per client rises with account size** and will not flatten by
   Phase 5. Not "it is an agency" — a premium agency is a fine business — but a
   business that cannot grow past the founder's attention.
4. **Reconciliation confidence cannot reach 0.9 on typical accounts.** If we
   cannot measure correctly, we cannot optimise honestly, and the central
   promise fails. This is the one that would end it fastest, because
   recommendation mode makes measurement the *whole* product for some clients.
5. **The prior-lift holdout stays flat through Phase 6 and beyond ~100 clients.**
   Primed briefs do not beat cold briefs, and cohort curves do not separate.
   Phoenix is then a well-built services business with no compounding advantage —
   which is a real company, and not one worth the learning machinery. Delete the
   machinery, keep the client moat, and price accordingly.

Each has a phase that tests it and a number that answers it. That is the point
of the ordering in `06-ROADMAP.md`.
