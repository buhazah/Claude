# Phoenix — Risks, cost model, scaling, technical debt

---

## 1. Business risks

Ordered by how likely they are to kill the company.

### R1 — Meta commoditises the work *(likely, high impact)*
Advantage+ already absorbed most of media buying. If Meta ships better
automated creative generation, the creative wedge narrows too.

**Mitigation:** the defensible layer is measurement, offer strategy, and
operational safety — things Meta will never do for an advertiser because they
require the advertiser's own data and interests. Do not build a business whose
only claim is out-optimising the platform on its own data.

**Leading indicator:** creative win rate against Meta's own generated assets.
Track from Phase 2.

### R2 — AI creative is not good enough *(unknown, existential)*
The assumption everything rests on.

**Mitigation:** Phase 2 tests it for ~£4k in week three, with a written
decision rule for each of the three outcomes.

### R3 — Nobody trusts an AI with their ad spend *(likely, high)*
Rational customer behaviour, not a marketing problem.

**Mitigation:** shadow mode is the entire answer. Sell measurement first (Phase
1), earn autonomy on evidence, per action type. The decision ledger is the
trust product.

### R4 — Ad account ban *(possible, severe per client)*
A policy strike can end a client relationship in an afternoon, and appeals run
on Meta's timetable, not ours.

**Mitigation:** compliance gate before every ship, scored on **recall** not
precision; conservative claim handling; never auto-resume a policy pause; never
hold billing permissions.

### R5 — Liability for autonomous spend *(certain to arise, unbounded)*
Phoenix will eventually lose someone money. The question is whether the
contract answered it in advance.

**Mitigation:** settle in Phase 0, before the first mandate. Mandate ceilings
double as contractual liability caps. Insurance. Decide whether we hold the ad
accounts — it changes the exposure entirely.

### R6 — Services margin, not software margin *(likely)*
If every client needs eight hours of human time a week, this is an agency with
a large AI bill.

**Mitigation:** human-minutes-per-client-per-week is a tracked metric with a
target from Phase 5. If it does not fall, the business is an agency and should
be priced as one.

### R7 — Meta cuts off API access *(unlikely, fatal)*
Platform risk in its purest form.

**Mitigation:** none that is honest. Comply meticulously, keep the measurement
layer platform-agnostic so it survives, and do not pretend this risk is
managed. It is accepted.

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
| T9 | AI cost per client exceeds margin | Possible | Cost governor per tenant, checked before each call; creative generation is the line item to watch |
| T10 | Multi-agent cost and latency explosion | Likely if departments talk | Workflow spine, not conversation (ADR 0004) |
| T11 | Evaluation corpus rots as the environment moves | Certain | Cases generated from history; baselines re-cut with justification |
| T12 | A model writes a number it was not given | Likely | `report` suite: any figure not passed in is a hard failure |

T1 and T2 are the two that must be solved before anything else is built on top
of them.

## 3. Cost model

**Assumed price: £2,500/month per client.** Every number below moves if that
changes, and settling it is a Phase 0 task.

### Per client per month, at steady state

| Line | Estimate | Notes |
|---|---|---|
| Creative generation | £80–200 | 40 variants; **the dominant and most variable line** |
| LLM — research, strategy, briefs | £25–60 | Front-loaded at onboarding |
| LLM — diagnosis and proposals | £15–40 | Daily, cheap models, short context |
| LLM — reports and comms | £10–25 | Weekly, prose only |
| Embeddings and memory | £5–15 | |
| Infrastructure — instance, DB, storage | £30–60 | The isolation tax |
| **AI + infra subtotal** | **£165–400** | |
| Human — success, review, exceptions | £250–800 | **The variable that decides the business** |
| **Total COGS** | **£415–1,200** | |
| **Gross margin at £2,500** | **52–83%** | |

### What the numbers say

**Creative generation is the cost centre, not the LLM calls.** Text is cheap;
images and video are not. Two consequences: cache and reuse aggressively via
lineage, and generate in tiers — cheap models to explore, expensive ones only
for concepts that survive internal filtering.

**Human time is the whole business.** At 8h/week/client this is an agency with
software costs. At 1h/week it is software with a services wrapper. The gap
between 52% and 83% margin is almost entirely that number.

**The isolation tax is real but small.** £30–60/client for a separate instance
and database is a fair price for a confidentiality story that survives
scrutiny. At 500 clients it needs revisiting; at 50 it does not.

### Break-even sketch

Fixed costs — control plane, one engineer, tooling — call it £12k/month.
At 70% gross margin, break-even is roughly **7 clients**. At 15 clients the
operation is profitable enough to hire. These are estimates on an assumed
price, not a forecast.

## 4. Scaling

**1–10 clients.** Everything manual that can be. One instance per client. The
founder reviews every creative batch. Optimise for learning, not efficiency.

**10–50.** Human time per client is the binding constraint. Automate review
triage, not review. Fleet scheduling from the control plane. Per-tenant cost
attribution becomes necessary rather than nice.

**50–200.** Instance-per-tenant starts to hurt: provisioning, migrations,
per-instance idle cost. Two options — pooled instances for small clients with
tenancy inside Jarvis Core, or accept the cost and price for it. Decide with
data, not now.

**200+.** Different company. Rate limits, Meta partnership terms, and a support
organisation all become first-order problems.

**What scales badly and should be watched:** anything requiring a human to look
at every unit of output. Creative review is the obvious one, which is why the
internal filter in `04-DEPARTMENTS.md` exists and why its job is to make the
human review twenty candidates rather than two hundred.

## 5. Technical debt strategy

Debt is a loan. The question is only whether it is recorded and priced.

**Debt taken deliberately, in the roadmap:**

| Debt | Why | Repayment trigger |
|---|---|---|
| Instance-per-tenant | Isolation now beats efficiency now | >50 clients, or infra cost >10% of revenue |
| Meta only | Depth before breadth | A client's retention depends on a second platform |
| Manual creative review | We do not know what to automate yet | Review time >3h/client/week |
| No fine-tuning | Removes a class of leakage argument | Only if measured lift justifies it |
| Counterfactual scoring in shadow | Cheaper than universal holdouts | When a decision's stakes justify a real holdout |
| Human onboarding | The first fifty teach us the workflow | >2 onboardings/week |

**Debt that will not be taken, at any point:**

- shortcuts in the mandate checker
- money arithmetic in floats
- a shared database across tenants
- a model computing a number that reaches a client
- an approval path around the hard floor in `03-AUTONOMY.md §3`

Those five are the invariants. Everything else is negotiable under deadline.

**The repayment discipline:** every deliberate debt gets a row in this table
with a trigger. A debt without a trigger is not debt; it is a decision nobody
admitted to making.

## 6. What would make me abandon this

Stated in advance, because the time to write the kill criteria is before you
are emotionally invested:

1. **Meta write access is refused or takes more than six months.** Phases 3+
   are impossible; Phase 1 is a different, smaller company.
2. **AI creative loses badly in Phase 2** *and* the volume advantage does not
   compensate. The wedge is gone.
3. **Human time per client will not fall below ~4h/week by Phase 5.** It is an
   agency. That can be a good business, but it is not this one, and it should
   be priced and staffed as an agency from that point.
4. **Reconciliation confidence cannot reach 0.9 on typical accounts.** If we
   cannot measure correctly, we cannot optimise honestly, and the central
   promise fails.

Each has a phase that tests it and a number that answers it. That is the point
of the ordering in `06-ROADMAP.md`.
