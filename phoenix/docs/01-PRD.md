# Phoenix — Product Requirements

Read `00-STRATEGY.md` first. This document assumes its recommendations.

---

## 1. What Phoenix is

**An AI-operated customer acquisition function, sold as a premium managed
service.** A business grants access to their existing store and ad accounts,
agrees an operating mandate, and Phoenix runs the acquisition workflow
end to end:

```
strategy → research → creative generation → campaign orchestration
        → measurement → optimisation recommendations → continuous learning
```

**Media buying is one capability inside that loop, not the product.** What no
agency and no point tool has is the *whole loop under one memory*: the research
that produced an angle links to the brief that tested it, to the variant that
ran, to the reconciled outcome, to the knowledge card that changes the next
brief.

Three framing decisions that everything else depends on:

**Agency, not software vendor, and not a spend reseller.** Phoenix operates
inside the client's own Business Manager and ad accounts under permissions they
grant. We never hold the accounts, never touch billing, and never resell media.
The client's relationship with the platform stays theirs.

**Meta is the first execution channel, not the foundation.** Strategy, creative,
measurement, approvals, memory and workflows are channel-neutral by
construction, so Google Ads and TikTok are adapters rather than rewrites
([ADR 0006](adr/0006-channels-are-adapters.md)).

**Execution authority is earned per action, per channel.** Phoenix delivers
value in *recommendation mode* on read-only access from day one, and executes
only what the client has both permitted and mandated (`03-AUTONOMY.md §6`).

It is staffed by AI departments coordinated by Jarvis Core, with a small human
team handling exceptions, relationships, and the judgement calls the mandate
reserves.

## 2. What Phoenix is not

- **Not a dashboard.** Dashboards make the customer do the work. Phoenix does
  the work and reports what it did.
- **Not a chatbot with ad tools.** The primary interface is outcomes and a
  weekly report, not a chat window. Chat is an escape hatch.
- **Not an auction optimiser.** The platform's algorithm allocates spend better
  than we will. We supply it with better creative, better offers, and better
  conversion signal, then measure honestly. This is the *only* part of the brief
  we drop — not the optimisation stage of the workflow, which we own.
- **Not a spend reseller.** We do not hold ad accounts, front media budgets, or
  mark up spend. The client pays the platform directly; they pay us a fee.
- **Not a creative marketplace.** We do not sell assets. We sell managed
  performance.
- **Not priced to be the cheap option.** The architecture optimises for
  maintainability, reliability and measurable results, and the price reflects
  that (`07-RISKS.md §3`).
- **Not self-serve, initially.** The first fifty customers are onboarded by a
  human who is watching very closely.

## 3. Who it is for

**Primary ICP.** DTC ecommerce brands on Shopify, spending £10k–£100k/month on
paid social — Meta first — with one clear conversion event and at least three
months of history.

**Why this ICP:**

| Requirement | Why it matters |
|---|---|
| £10k+/month spend | Below this, creative fatigue is not the binding constraint, there is not enough data to diagnose anything, and a premium fee cannot be justified against the spend |
| Under £100k/month | Above this they have an in-house team and buy tools, not services |
| Shopify or similar | A source of revenue truth that is not Meta's attribution |
| One conversion event | Measurement is tractable; multi-touch B2B pipelines are not |
| 3+ months history | Something to learn from and a baseline to be measured against |

**Explicitly out of scope for v1:** lead gen, B2B, apps, local services,
regulated verticals (finance, health claims, gambling), and anything where
the conversion happens off-platform and unmeasurably.

**Who the buyer is.** Founder or head of growth. They are not looking for
software. They are looking for someone to hand the problem to.

## 4. Jobs to be done

In the customer's words, ranked by how often they are actually said:

1. *"I don't know what's working."* → measurement and diagnosis
2. *"We're out of creative and the ads are fatiguing."* → creative throughput
3. *"My agency charges £6k/month and I don't know what they do."* → transparency
4. *"I don't have time to manage this."* → operational autonomy
5. *"Scale it without blowing up the CAC."* → disciplined scaling

Note that (1) and (3) are about **trust**, and they come first. Phoenix has to
be legible before it is allowed to be autonomous.

## 5. The product, by surface

### 5.1 Onboarding (human-assisted, 1 week)
Connect the ad channel, Shopify, and analytics. Verify the conversion signal end to end
— this is where most agencies quietly fail. Business discovery interview
(AI-conducted, human-reviewed). Baseline the last 90 days. Agree the first
mandate. **Exit criterion: Phoenix can reproduce the customer's own revenue
numbers to within a stated tolerance.** If it cannot, nothing downstream is
trustworthy and onboarding does not complete.

### 5.2 The weekly report
The primary deliverable. Not a metrics dump — an executive read: what happened,
what it means, what was done about it, what is next, what needs a decision.
Built on the same discipline as the Jarvis morning briefing: leads with the one
thing, says what it could not measure, does not pad.

### 5.3 The creative pipeline
Hypothesis → brief → concepts → generation → gates → internal review → customer
approval (first month; later by mandate) → matched test → resolution → refresh,
retire or scale. Shipped in **generations** of ~20 every fortnight, so "did this
batch beat the last one" is a question with an answer.

Throughput is ~40 tested variants per month, but that is an output rather than
the target. **The goal is that each generation moves the frontier**, and the
client-facing artefact is the generation brief: eight hypotheses, why we believe
each one, what would falsify it — followed two weeks later by what happened to
each. Full design in `09-CREATIVE.md`.

### 5.4 The decision ledger
Every proposal Phoenix made, whether it executed or was delivered as a
recommendation, why, and what happened. This is the transparency product and the
trust-building mechanism. Customers can read it. So can we, when something goes
wrong.

### 5.5 The recommendation queue *(read-only clients, and every client at first)*
When Phoenix has read access but not write access, the decision loop still runs
to a decision — and the decision is **delivered** rather than executed: a ranked
list, each item with its evidence, expected effect, confidence, and the exact
change to make. The client's own buyer applies it. Phoenix measures the outcome
a week later regardless, because measuring needs only read access.

This is a supported end state, not a trial. Some clients will never grant write
access, and they are still full clients (`03-AUTONOMY.md §6`, tier R).

### 5.6 The mandate
The customer's control surface. What Phoenix may do, on which channel and
account, up to what limit, until when. Revocable in one click. Reviewed monthly.
Authority is the intersection of the mandate and the permissions actually
granted — never the union.

### 5.7 Chat
An escape hatch onto the same system: *"why did CPA jump on Tuesday",*
*"pause the UGC set",* *"what did we learn about the bundle offer".* Backed by
the same data and the same mandate — chat cannot exceed what the mandate
allows.

## 6. Client lifecycle

The brief's lifecycle, with exit criteria, because a stage without one is a
stage that never ends.

| Stage | Owner | Exit criterion |
|---|---|---|
| Lead | Sales | ICP fit confirmed: spend, platform, conversion event |
| Qualification | Sales | Access confirmed possible; expectations set in writing |
| Onboarding | Client Success + Ops | **Revenue reconciliation passes** |
| Business discovery | Business Strategy | Offer, margins, constraints, brand rules documented |
| Product & audience research | Market Research + Audience Intelligence | Segments and angles documented with evidence |
| Competitor research | Market Research | Positioning gap stated as a testable claim |
| Strategy | Business Strategy | Named hypotheses, each with a test and a success threshold |
| Creative production | Creative Studio | First batch approved |
| Campaign creation | Media Buying | Structure agreed against mandate |
| Launch | Campaign Ops | Live, tracking verified post-launch |
| Daily optimisation | Campaign Ops | *(continuous)* |
| Weekly review | Reporting | Report delivered and read |
| Monthly business review | Executive Office | Mandate renewed or revised |
| Continuous learning | Knowledge Mgmt | Knowledge cards published |

**A stage cannot be skipped, and reconciliation cannot be waived.** The failure
mode of every agency is launching before measurement works, then optimising
against numbers that are wrong.

## 7. Campaign lifecycle

Research → Strategy → Brief → Generation → Review → Structure → Audience →
Budget → Launch → Monitoring → Optimisation → Scaling → Refresh → Reporting →
Knowledge capture.

Implemented as a durable Jarvis workflow, not as a conversation. Each
transition is a persisted state change; a campaign waiting for creative
approval is a database row, and it survives a restart (ADR 0007 in Jarvis
Core).

## 8. Autonomy

Full model in `03-AUTONOMY.md`. Summary:

| Always autonomous | Mandate-gated *(and capability-gated)* | Never autonomous |
|---|---|---|
| Research, monitoring, analysis | Budget shifts within limits | Connecting payment methods |
| Creative ideation and drafts | Pausing underperformers | Creating ad accounts |
| Reports and **delivered recommendations** | Launching pre-approved creative | Raising total spend |
| Knowledge capture | Scaling winners within limits | Changing the offer |
| Internal documentation | Creative refresh | Deleting campaigns |

The right-hand column is not configurable. Those actions require a human, every
time, regardless of mandate — because their blast radius is unbounded or their
reversal is impossible. Under the agency model the first two are enforced twice
over: we never request billing or account-management scope at all.

The middle column has a second gate. A mandated action on a connection without
the matching write capability does not fail and does not wait — it moves to the
left-hand column as a **recommendation**, delivered with its evidence for the
client to execute.

## 9. Success metrics

**For the customer** — the only ones that matter commercially:

| Metric | Definition | Target |
|---|---|---|
| Blended CAC | Total spend ÷ new customers, from **store data** | ↓ vs 90-day baseline |
| Contribution margin | Revenue − COGS − spend | ↑ |
| Incremental ROAS | Measured by holdout where volume allows | Stated with confidence interval, never a point estimate |
| Generational lift | Top-quartile CPA of this batch vs the last | ↓ each generation |
| Creative win rate | Variants beating control ÷ variants shipped | >15% — a **floor**; it falls as the control strengthens (`09-CREATIVE.md §1`) |
| Time to first insight | Access granted → first reconciled diagnosis | <7 days |
| Time to first launch | Onboarding start → live | <14 days |

**For Phoenix** — whether the company works:

| Metric | Why |
|---|---|
| Gross margin per client | Whether a premium fee covers a premium service |
| Human minutes per client per week | The number that decides whether it scales |
| Proposal accuracy, per action type | Whether autonomy is earned |
| Recommendation adoption rate | Whether read-only clients are getting value, or politely ignoring us |
| Mandate breach count | Must be zero. Not "low." |
| **Prior lift vs cold briefs** | Whether the moat exists, as a percentage (`08-MOAT.md §14`) |
| **Cohort separation at equal tenure** | Whether client 10,000 starts better than client 100 |
| Client retention at 6 months | The only real verdict |

**Metrics deliberately not targeted:** in-platform ROAS (unreliable
post-ATT), CTR (a vanity proxy), impressions, "engagement", and anything
a platform reports that the store cannot corroborate.

## 10. Non-functional requirements

- **Correctness over autonomy.** A wrong number is worse than a missing one.
  Every reported figure traces to a source, and unmeasurable things are
  labelled unmeasurable.
- **Explainability.** Every action has a human-readable sentence, an evidence
  trail, and an actor. Inherited from Jarvis's audit log and computer-control
  design.
- **Tenant isolation.** A client's data cannot reach another client's context.
  Enforced by separate databases, not by a `WHERE` clause. Knowledge crosses only
  as claims aggregated over five or more businesses, through a deterministic gate
  a model never touches (ADR 0007).
- **Revocable contribution.** A departing client can require that what was
  learned from them be removed, and Phoenix can honour it by recomputation rather
  than by promise. Nothing is fine-tuned, ever (ADR 0008).
- **Idempotency.** Every external write carries an idempotency key. A retry
  after a timeout must not double a budget.
- **Reconciliation.** External state drifts — the client's own team edits in the
  platform UI, the platform auto-pauses. Phoenix detects drift and surfaces it;
  it does not blindly re-apply its own intent. Under the agency model this is
  the normal case, not the exception: it is their account and their team.
- **Degradation.** A dead integration degrades that capability and says so. It
  does not fabricate, and it does not take the system down.
- **Cost ceiling per client.** Enforced by Jarvis's cost governor, checked
  before each call.

## 11. Decisions taken, and what remains open

### Answered

**1. Meta write access.** Design assumes full Marketing API integration;
implementation operates in read-only analysis and recommendation mode until
write permissions exist, per client and per action type. Write access is a
declared capability on a channel connection, not a roadmap phase
([ADR 0006](adr/0006-channels-are-adapters.md)). Start Meta's review process on
day one because it takes as long as it takes — but nothing in the build waits
behind it.

**2. Agency, not software, and not a spend reseller.** Phoenix operates on the
client's existing Business Manager and ad accounts under permissions they grant.

| Consequence | Effect |
|---|---|
| **Cash flow** | We invoice a fee. Media spend never crosses our balance sheet — no float, no working-capital requirement, no receivables risk on someone else's ad budget. |
| **Legal exposure** | The advertiser of record is the client. Platform policy liability, VAT on media, and the advertising-standards relationship stay theirs. |
| **Platform risk** | A client's account issue is contained to that client. We are not a single app whose suspension ends every relationship at once. |
| **Trust** | "Your accounts, your data, your permissions, revocable in one click" is a materially easier sale than "give us your ad account." |
| **Cost** | We cannot mark up media, so the fee has to carry the business. See §5 below. |
| **Operational** | Permissions live on the client's side and can vanish with a staff change — which is exactly why capabilities are re-derived on every token refresh (`02-ARCHITECTURE.md §5.1`). |

**3. Liability when Phoenix loses someone money.** The agency model narrows this
but does not remove it. Four instruments, settled before the first mandate:

- **The mandate ceiling is the liability cap.** A client who grants a £400/day
  ceiling has bounded the worst case arithmetically, and the contract says so in
  the same numbers.
- **The client is the advertiser of record.** We act on instruction, within an
  envelope they set and can revoke.
- **The decision ledger is the evidentiary record.** Every action has a signal,
  a rationale, an authority and a timestamp. Disputes are resolved by query, not
  by recollection.
- **Professional indemnity insurance**, sized against the aggregate of live
  mandate ceilings rather than against revenue.

Recommendation mode is the cleanest position of all: the client executed it.
That is a genuine reason to be unhurried about write access.

**5. Price: premium managed service.** The architecture is optimised for
maintainability, reliability and measurable results, not for minimising
infrastructure cost. Concretely, this authorises the expensive choices the
blueprint already makes — instance-per-tenant isolation, generating creative
with the best models rather than the cheapest, holdout testing where volume
allows, human review in the loop, and the evaluation harness. Cost model in
`07-RISKS.md §3`.

### Still open

**4. Do we own the creative we generate?** Model provider terms vary and change.
Needs a legal read per provider before Phase 2, and the answer belongs in the
client contract rather than in an assumption.

**6. Which channel is second, and when.** Not a design question any more — the
port makes it an adapter — but a commercial one. The trigger is the first client
whose retention depends on it (`07-RISKS.md §5`).

**7. What "premium" is, in a number.** The tier structure and the fee are a
commercial decision with a range in `07-RISKS.md §3`, not an architectural one.
The architecture no longer changes if it moves.
