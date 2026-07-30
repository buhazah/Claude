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

  channel: meta                   # a mandate authorises one channel
  account: act_1029384756         # …on one account the client owns

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

**Seven properties that make it work:**

**Channel-scoped.** A mandate authorises one channel on one account. A client
running Meta and Google grants two mandates with two ceilings, and the checker
never sums across them into an authority nobody granted. The `may` verbs are the
neutral ones from `02-ARCHITECTURE.md §5.4`, so the same mandate grammar works
on a channel that does not exist yet; channel-specific verbs
(`meta.enable_advantage_plus`) must be listed by name and are never implied.

**Capability-bounded.** Authority is the *intersection* of
what the client's permissions allow and what the mandate grants — never the
union. A mandate that permits `shift_budget` on a connection without
`write.budget` is not an error and does not fail: it resolves to
**recommendation mode** for that verb. Grants and capabilities move
independently, and the system stays correct when they disagree.

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

**The hard floor is channel-neutral by construction.** It is expressed in the
neutral verbs, so a new adapter inherits every one of these prohibitions on the
day it is written rather than re-litigating them. An adapter cannot introduce a
channel-specific action that routes around the floor: adapter-namespaced verbs
are checked against it first, and a verb that would modify billing, create or
close an account, or delete an entity is rejected at registration.

**The agency model reinforces the floor rather than replacing it.** Phoenix
operates inside the client's Business Manager and never requests billing scope
at all — so "may not modify the payment method" is enforced twice: once by the
mandate checker, and once by a permission we deliberately never hold.

## 4. The clamp

When a proposal exceeds a limit, the interesting question is what happens next.

Four options: **reject** it, **escalate** it, **clamp** it to the limit and
proceed, or **recommend** it. Phoenix clamps for *magnitude*, escalates for
*kind*, and recommends when the verb is authorised but the capability is absent.

- Proposal: increase budget 40%. Limit: 25%. → **clamped to 25%**, executed,
  recorded as clamped, and the delta reported.
- Proposal: create a new campaign. Not in `may`. → **escalated**, never clamped.
- Proposal: pause an ad set. In `may`, but the connection has no `write.status`.
  → **recommended**: delivered to the client with its evidence, and its outcome
  measured whether or not they act.

A fifth verdict, **unsupported**, comes from the adapter rather than the mandate:
the verb is authorised and permitted but this channel cannot express it. It is
recorded as an adapter gap, not a client-facing failure, and it is the metric
that tells us where the neutral verb set is too ambitious.

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

**Shadow, recommend and execute are one code path**
(`02-ARCHITECTURE.md §5.1`). They differ in two booleans: whether the decision is
shown to the client, and whether `apply()` is called. That is deliberate — a
separate read-only build would rot, and the mode a client is in would stop being
a property of their permissions and start being a property of which branch we
deployed.

See [ADR 0005](adr/0005-autonomy-is-earned-in-shadow.md).

## 6. Autonomy tiers

Progression is per action type, per client, on evidence.

| Tier | Meaning | Needs | Entry criterion |
|---|---|---|---|
| **0 — Shadow** | Proposes, shows nobody | `read.*` | Default. Always. |
| **R — Recommend** | Proposes, delivers to the client, they execute | `read.*` | ≥20 shadow proposals of this type, ≥70% correct |
| **1 — Notify** | Executes, tells you after | `write.*` | ≥30 proposals of this type at tier 0/R, ≥80% correct |
| **2 — Mandated** | Executes within the envelope | `write.*` | 30 days at tier 1, zero breaches, customer agrees |
| **3 — Broad** | Wider limits, weekly reporting | `write.*` | 90 days at tier 2, positive measured outcome |

**Tier R is not a waiting room.** It is a supported end state. A client who never
grants write access sits at tier R indefinitely and receives most of the value in
`00-STRATEGY.md §3` — diagnosis, ranked decisions, evidence, measured outcomes,
compounding knowledge. Some clients will stay there by policy, and the pricing
in `07-RISKS.md §3` assumes a meaningful share of them do.

It is also the best evidence generator in the model. A recommendation the client
executed produces a **real** outcome rather than a counterfactual, so tier R
proposals count toward tier 1 entry at full weight while tier 0 proposals carry
the estimate caveat in §5.

Demotion is automatic and immediate: any mandate breach, any outcome verdict
worse than a stated threshold, or any customer request drops the action type to
tier 0. Earning back requires going through the tiers again.

**Losing a capability is not a demotion.** If a token refresh comes back without
`write.status`, the action type drops to tier R and keeps its earned standing;
when the permission returns, so does the tier. Demotion is about trust, and a
staff change at the client is not a trust event.

## 7. What is autonomous from day one

Reading is not acting. These need no mandate and never did:

- ingesting data, reconciling revenue, computing metrics
- raising signals, forming diagnoses
- researching markets, competitors, audiences
- generating creative concepts, copy, and assets **as drafts**
- writing reports, briefings, and recommendations
- **delivering ranked recommendations to the client** — a recommendation is
  speech, not an action; the client's own hands are between it and their account
- capturing knowledge

Everything on that list is reversible, invisible to the outside world, and
costs money only in tokens — which Jarvis's cost governor already ceilings
before each call.

## 8. The decision ledger

Every proposal ever made — executed, delivered, or neither — with its evidence,
verdict, mode, mandate version, and outcome. Queryable by the customer.

In recommendation mode the ledger is doing double duty: it is the transparency
record *and* the work product, because a delivered recommendation is the
deliverable rather than a footnote to one.

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
| Client's staff removes our permission | Capabilities re-derived on every token refresh. The action type drops to tier R, the client sees a mode change, and nothing fails silently for a week. |
| A confident recommendation is wrong and the client acts on it | The one place tier R is *not* safer than shadow. Delivered recommendations carry the same confidence, evidence and expected effect as executed ones, and the `recommendation` corpus suite scores whether the uncertainty survived being written into prose. A recommendation that reads as an instruction is a defect. |
| An adapter cannot express an authorised verb | Verdict `unsupported`, recorded against the adapter, never surfaced to the client as a failure of their account. |
| Optimising against wrong numbers | `reconciliation_confidence < 0.8` blocks the whole loop. The most important guard here. |
| Thrash — change, revert, change | `min_hours_between_changes` and per-week caps. |
| Cost runaway on tokens | Jarvis cost governor, checked before each call, per tenant. |
| Proposal is *technically* fine and *commercially* stupid | This is the one code cannot catch. It is what shadow mode, outcome scoring and the human console are for — and it is why tier 3 still reports weekly. |

That last row is the honest one. A mandate bounds magnitude and kind; it cannot
bound judgement. Some proportion of proposals will be inside every limit and
still wrong. The system is designed so those are visible, reversible, and
bounded in cost — not so they never happen.
