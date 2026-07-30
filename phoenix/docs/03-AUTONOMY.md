# Phoenix — Autonomy, mandates and the decision ledger

The part that decides whether this company is viable or uninsurable.

---

## 1. The problem with approval workflows

The brief proposes: certain actions require approval, others are autonomous.
That model fails in a specific, predictable way.

A client spending £40k/month generates perhaps fifty budget decisions a week.
Send fifty approval requests and one of two things happens. Either the customer
reads them — in which case you have not saved them any time and they are doing
media buying with extra steps — or they stop reading and approve in bulk. The
second is what actually happens, and it is worse than no approval at all: the
liability has transferred to the customer while the judgement has not.

Approval-per-action optimises for the appearance of control.

## 2. Mandates

A **mandate** is a bounded, revocable, expiring grant of authority. It is the
same instrument a trading desk gives a trader, an employer gives a purchasing
manager, or a board gives a CEO: *here is what you may do, up to here, until
then.*

```yaml
mandate:
  tenant: northbound
  version: 4
  granted_by: sarah@northbound.co
  granted_at: 2026-08-01
  expires_at: 2026-08-31          # expiry is not optional

  spend:
    daily_ceiling_gbp: 400
    monthly_ceiling_gbp: 11000
    max_single_change_pct: 25
    max_changes_per_campaign_per_week: 2
    min_hours_between_changes: 24   # stops thrash

  may:
    - shift_budget_between_adsets
    - pause_adset                   # when CPA > 2× target over 3 days, 50+ clicks
    - resume_adset
    - launch_approved_creative
    - scale_winner                  # ≤25%, ROAS > target for 5 consecutive days

  may_not:
    - create_campaign
    - raise_total_budget
    - change_offer_or_landing_page
    - modify_payment_method
    - delete_anything

  escalate_to_human_when:
    - daily_spend > 0.9 × ceiling
    - CPA > 1.5 × target for 2 consecutive days
    - any_policy_warning
    - reconciliation_confidence < 0.8
    - proposal_confidence < 0.6
```

**Five properties that make it work:**

**Bounded.** Every dimension has a number. "Reasonable budget changes" is not a
mandate; ±25% twice a week is.

**Deterministic.** Checked by code, before actuation, in one place. It is not a
prompt instruction, because a prompt can be argued with and a validator cannot.

**Versioned.** Every decision records which mandate version authorised it. When
a customer asks "why did you do that in August", the answer includes the
authority it acted under.

**Expiring.** A mandate that never expires is a permanent grant nobody
re-examines. Monthly expiry forces a monthly conversation, which is also the
monthly business review, which is also the retention mechanism.

**Revocable in one click**, taking effect immediately, mid-flight actions
included.

See [ADR 0003](adr/0003-mandates-not-approvals.md).

## 3. The hard floor

Some actions are never inside any mandate, at any tier, for any customer:

- connecting or modifying a payment method
- creating or closing an ad account
- raising the total budget envelope
- changing the offer, price, or landing page
- deleting a campaign, ad set, or ad
- anything touching a customer list or PII export

Not configurable. Their blast radius is unbounded or their reversal is
impossible, and a system that lets a customer configure away the last safeguard
has no safeguard. Same reasoning as Jarvis's computer control, where credential
fields are refused outright with no approval path — *"that one is not an
approval you can click through."*

## 4. The clamp

When a proposal exceeds a limit, the interesting question is what happens next.

Three options: **reject** it, **escalate** it, or **clamp** it to the limit and
proceed. Phoenix clamps for *magnitude* and escalates for *kind*.

- Proposal: increase budget 40%. Limit: 25%. → **clamped to 25%**, executed,
  recorded as clamped, and the delta reported.
- Proposal: create a new campaign. Not in `may`. → **escalated**, never clamped.

Clamping is right for magnitude because the direction was correct and the
system's job is to act within its authority, not to stall. Escalation is right
for kind because there is no smaller version of "create a campaign."

`clamped_from` is a persisted field. Systematic clamping is a signal that the
mandate is too tight for what the account needs, and it should show up in the
monthly review as an argument for widening it — with the evidence attached.

## 5. Shadow mode

**No mandate is granted before shadow mode has run.**

The full loop executes — ingest, signals, diagnosis, proposals, mandate checks
— and stops at the decision record. Nothing touches Meta. Every proposal is
persisted with what it *would* have done and what it expected to happen.

Then time passes, and the outcome is knowable. Each proposal is scored:

```
proposal:  pause adset "UGC-Hook-3", CPA £52 vs £28 target, 4 days, 61 clicks
expected:  blended CPA −8%
actual:    the customer's buyer paused it two days later
verdict:   correct, and earlier
```

After 30–60 days this produces a sentence no one can argue with: *"143
proposals. If executed, blended CAC would have been 11% lower. Six proposals
would have been wrong; here they are."*

That is how autonomy gets granted — on evidence, per action type, by a customer
who has watched it work. It also means the first version of Phoenix is safe by
construction: it cannot spend money, because the code path does not exist yet.

Shadow mode never gets turned off. Every new action type enters shadow first,
and shadow proposals continue alongside live ones as a permanent control.

See [ADR 0005](adr/0005-autonomy-is-earned-in-shadow.md).

## 6. Autonomy tiers

Progression is per action type, per client, on evidence.

| Tier | Meaning | Entry criterion |
|---|---|---|
| **0 — Shadow** | Proposes only | Default. Always. |
| **1 — Notify** | Executes, tells you after | ≥30 shadow proposals of this type, ≥80% correct |
| **2 — Mandated** | Executes within the envelope | 30 days at tier 1, zero breaches, customer agrees |
| **3 — Broad** | Wider limits, weekly reporting | 90 days at tier 2, positive measured outcome |

Demotion is automatic and immediate: any mandate breach, any outcome verdict
worse than a stated threshold, or any customer request drops the action type to
tier 0. Earning back requires going through the tiers again.

## 7. What is autonomous from day one

Reading is not acting. These need no mandate and never did:

- ingesting data, reconciling revenue, computing metrics
- raising signals, forming diagnoses
- researching markets, competitors, audiences
- generating creative concepts, copy, and assets **as drafts**
- writing reports, briefings, and recommendations
- capturing knowledge

Everything on that list is reversible, invisible to the outside world, and
costs money only in tokens — which Jarvis's cost governor already ceilings
before each call.

## 8. The decision ledger

Every proposal ever made, executed or not, with its evidence, verdict, mandate
version, and outcome. Queryable by the customer.

This is the transparency product. The most common complaint about agencies in
`01-PRD.md §4` is *"I don't know what they do."* The decision ledger is a
literal answer to it, generated as a by-product of operating rather than
written for the customer's benefit.

It is also the incident-response tool. When something goes wrong at 2am, the
question is always "what changed and who changed it", and the ledger answers it
in one query.

## 9. Failure modes and their answers

| Failure | Answer |
|---|---|
| Model hallucinates a huge budget increase | Mandate check clamps it. Deterministic, tested, cannot be prompted around. |
| Two proposals conflict | One decision at a time per entity, serialised. Second sees the first's effect. |
| Action times out — did it apply? | Idempotency key. Retry is safe by construction. |
| Human edits in Ads Manager | Reconciler detects drift, surfaces it, does **not** re-apply our intent. |
| Meta auto-pauses for policy | Signal → escalate. Never auto-resume a policy pause. |
| Customer revokes mid-flight | Mandate check runs immediately before every write, not at proposal time. |
| Optimising against wrong numbers | `reconciliation_confidence < 0.8` blocks the whole loop. The most important guard here. |
| Thrash — change, revert, change | `min_hours_between_changes` and per-week caps. |
| Cost runaway on tokens | Jarvis cost governor, checked before each call, per tenant. |
| Proposal is *technically* fine and *commercially* stupid | This is the one code cannot catch. It is what shadow mode, outcome scoring and the human console are for — and it is why tier 3 still reports weekly. |

That last row is the honest one. A mandate bounds magnitude and kind; it cannot
bound judgement. Some proportion of proposals will be inside every limit and
still wrong. The system is designed so those are visible, reversible, and
bounded in cost — not so they never happen.
