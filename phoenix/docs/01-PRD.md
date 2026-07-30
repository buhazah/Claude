# Phoenix — Product Requirements

Read `00-STRATEGY.md` first. This document assumes its recommendations.

---

## 1. What Phoenix is

An AI-operated Meta advertising company. A business owner connects their store
and their ad account, agrees an operating mandate, and Phoenix runs the
advertising: researching, producing creative, launching, measuring, diagnosing,
optimising within its mandate, and reporting.

It is staffed by AI departments coordinated by Jarvis Core, with a small human
team handling exceptions, relationships, and the judgement calls the mandate
reserves.

## 2. What Phoenix is not

- **Not a dashboard.** Dashboards make the customer do the work. Phoenix does
  the work and reports what it did.
- **Not a chatbot with ad tools.** The primary interface is outcomes and a
  weekly report, not a chat window. Chat is an escape hatch.
- **Not a Meta optimiser.** Meta's algorithm allocates spend better than we
  will. We supply it with better creative, better offers, and better
  conversion signal, then measure honestly.
- **Not a creative marketplace.** We do not sell assets. We sell managed
  performance.
- **Not self-serve, initially.** The first fifty customers are onboarded by a
  human who is watching very closely.

## 3. Who it is for

**Primary ICP.** DTC ecommerce brands on Shopify, spending £10k–£100k/month on
Meta, with one clear conversion event and at least three months of history.

**Why this ICP:**

| Requirement | Why it matters |
|---|---|
| £10k+/month spend | Below this, creative fatigue is not the binding constraint and there is not enough data to diagnose anything |
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
Connect Meta, Shopify, and analytics. Verify the conversion signal end to end
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
Brief → concepts → generation → internal review → customer approval (first
month; later by mandate) → launch → performance → kill or scale. Target: 30–50
tested variants per month per client.

### 5.4 The decision ledger
Every proposal Phoenix made, whether it executed, why, and what happened. This
is the transparency product and the trust-building mechanism. Customers can
read it. So can we, when something goes wrong.

### 5.5 The mandate
The customer's control surface. What Phoenix may do, up to what limit, until
when. Revocable in one click. Reviewed monthly.

### 5.6 Chat
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

| Always autonomous | Mandate-gated | Never autonomous |
|---|---|---|
| Research, monitoring, analysis | Budget shifts within limits | Connecting payment methods |
| Creative ideation and drafts | Pausing underperformers | Creating ad accounts |
| Reports and recommendations | Launching pre-approved creative | Raising total spend |
| Knowledge capture | Scaling winners within limits | Changing the offer |
| Internal documentation | Creative refresh | Deleting campaigns |

The right-hand column is not configurable. Those actions require a human, every
time, regardless of mandate — because their blast radius is unbounded or their
reversal is impossible.

## 9. Success metrics

**For the customer** — the only ones that matter commercially:

| Metric | Definition | Target |
|---|---|---|
| Blended CAC | Total spend ÷ new customers, from **store data** | ↓ vs 90-day baseline |
| Contribution margin | Revenue − COGS − spend | ↑ |
| Incremental ROAS | Measured by holdout where volume allows | Stated with confidence interval, never a point estimate |
| Creative win rate | Variants beating control ÷ variants shipped | >15% |
| Time to first launch | Onboarding start → live | <14 days |

**For Phoenix** — whether the company works:

| Metric | Why |
|---|---|
| Gross margin per client | Is this software or is it services with extra steps? |
| Human minutes per client per week | The number that decides whether it scales |
| Proposal accuracy in shadow mode | Whether autonomy is earned |
| Mandate breach count | Must be zero. Not "low." |
| Client retention at 6 months | The only real verdict |

**Metrics deliberately not targeted:** in-platform ROAS (unreliable
post-ATT), CTR (a vanity proxy), impressions, "engagement", and anything
Meta reports that the store cannot corroborate.

## 10. Non-functional requirements

- **Correctness over autonomy.** A wrong number is worse than a missing one.
  Every reported figure traces to a source, and unmeasurable things are
  labelled unmeasurable.
- **Explainability.** Every action has a human-readable sentence, an evidence
  trail, and an actor. Inherited from Jarvis's audit log and computer-control
  design.
- **Tenant isolation.** A client's data cannot reach another client's context.
  Enforced by separate databases, not by a `WHERE` clause.
- **Idempotency.** Every external write carries an idempotency key. A retry
  after a timeout must not double a budget.
- **Reconciliation.** External state drifts — humans edit in Ads Manager, Meta
  auto-pauses. Phoenix detects drift and surfaces it; it does not blindly
  re-apply its own intent.
- **Degradation.** A dead integration degrades that capability and says so. It
  does not fabricate, and it does not take the system down.
- **Cost ceiling per client.** Enforced by Jarvis's cost governor, checked
  before each call.

## 11. Open questions

Things I cannot answer from here and that change the design:

1. **Can we get Meta Marketing API write access, and how long does it take?**
   Critical path. Start immediately.
2. **Agency or software?** Do we hold the ad accounts and bill the spend, or
   operate on the customer's? This changes the legal exposure, the cash flow,
   and the tax position entirely.
3. **What happens when Phoenix loses someone money?** Contractual liability,
   and it needs answering before the first mandate is signed.
4. **Do we own the creative we generate?** Model provider terms vary and change.
5. **What is the price?** The whole cost model in `07-RISKS.md §3` is built on
   an assumed £2,500/month. If it is £900, the architecture has to be cheaper.
