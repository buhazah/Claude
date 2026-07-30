# 3. Mandates, not per-action approvals

Status: proposed

## Context

The brief proposes approval for certain action classes. At agency scale a
client generates ~50 budget decisions a week. Either they read fifty approval
requests — in which case nothing was saved and they are doing media buying with
extra steps — or they stop reading and bulk-approve.

The second is what happens. It is worse than no approval: liability transfers
to the customer, judgement does not.

## Decision

**A mandate: a bounded, revocable, expiring grant of authority**, checked
deterministically before every external write.

```
daily ceiling · max single change % · max changes per week ·
may[] · may_not[] · escalate_when[] · expires_at
```

Five properties: bounded (every dimension has a number), deterministic
(checked by code in one place), versioned (every decision records the version
that authorised it), expiring (forces a monthly conversation), revocable
(one click, effective mid-flight).

**Magnitude is clamped. Kind is escalated.** A 40% increase against a 25% limit
becomes 25%, executes, and is recorded as clamped. "Create a campaign" when not
in `may` escalates — there is no smaller version of it.

**A hard floor sits outside every mandate, unconfigurable:** payment methods,
account creation, raising the total envelope, changing the offer, deletion,
PII export. Same reasoning as Jarvis's computer control refusing credential
fields outright — that one is not an approval you can click through.

## Alternatives rejected

**Per-action approval.** Degrades to rubber-stamping. Above.

**Fully autonomous with post-hoc review.** Reviewing a £4,000 mistake after it
happened is not a control.

**Approval thresholds only ("ask above £X").** Bounds magnitude, not kind, not
frequency, not duration. Fifty £99 changes pass a £100 threshold.

## Consequences

- The customer approves an envelope monthly instead of decisions daily.
- Every action carries the authority it acted under, versioned.
- Mandate expiry is also the monthly business review, which is also retention.
- `clamped_from` is persisted: systematic clamping is evidence the mandate is
  too tight, arguable at renewal with data.
- **The mandate checker becomes the most safety-critical code in the system.**
  100% branch coverage, non-negotiable.
