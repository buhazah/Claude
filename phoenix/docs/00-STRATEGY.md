# Phoenix — strategy memo

**Read this one first.** You asked me not to assume your ideas are correct. Six
of them aren't, and one of them is a blocker that has to be settled before any
code is written. Everything else in this blueprint follows from the corrections
below.

None of this is a reason not to build Phoenix. It is a set of reasons to build
a different, smaller, more defensible Phoenix than the brief describes.

---

## 1. Jarvis Core cannot host a multi-client agency today

`docs/ARCHITECTURE.md §7`, written in M1 and still true:

> **Non-goals (deliberately deferred):** Multi-tenancy, RBAC beyond a single
> principal…

Every store, every memory scope, every approval queue, every cost ledger in
Jarvis assumes one principal. An agency serving fifteen clients on one Jarvis
instance would have fifteen clients' ad performance in one memory namespace,
one approval queue, and one audit log. That is not a feature gap; it is a
confidentiality incident waiting for its first customer.

**Two ways out, and I recommend the first:**

**(a) Control plane + one Jarvis per client.** A thin agency-level service owns
tenants, billing, and cross-client learning. Each client gets an isolated
Jarvis instance — own database, own vault, own memory, own audit log. Isolation
is by process and by database, which is the only kind a customer's lawyer
believes. Cross-client learning happens by *publishing* anonymised, structured
knowledge cards upward, never by reading sideways.

Cost: orchestration complexity, per-client baseline spend, and a control plane
to build. At 10 clients this is trivially fine. At 500 it needs revisiting.

**(b) Add tenancy to Jarvis Core.** Every store grows a `tenant_id`, every
query grows a filter, and one missing `WHERE` clause leaks a client's data to
another. It is faster to write and permanently more dangerous.

I recommend (a), with the stores designed so (b) remains possible later. See
[ADR 0001](adr/0001-control-plane-and-isolated-tenants.md).

## 2. "AI company with 21 departments" is a good story and a bad spec

The department list in the brief is an org chart. Org charts describe *who
talks to whom*, and a system where twenty-one agents talk to each other is:

- **expensive** — every hop is a model call, and hops multiply
- **non-deterministic** — the same request takes different paths on different days
- **undebuggable** — when the output is wrong, no single component owns it
- **error-compounding** — a bad research summary becomes a bad strategy becomes
  a bad brief becomes a bad ad, with each step adding confidence and nobody
  adding a check

Jarvis learned this already. Phase 11's audit found that the Chief of Staff's
prompt had promised delegation for ten milestones while the runtime executed
exactly one agent — and the fix, when it came, was deliberately *one level
deep*, because "without a depth limit this is a recursion whose base case is
the user's budget."

**What to do instead.** Departments stay — as a **customer-facing metaphor** and
as a **namespace**. A department is a Jarvis mode + a set of agent specs + a
memory scope + an evaluation suite. That is real, it reuses machinery that
exists, and it gives you the org-chart narrative for sales.

But the *unit of execution* is a **durable workflow**, not a conversation
between departments. Jarvis already has an engine whose suspended runs survive
a restart. The client lifecycle and the campaign lifecycle in your brief are
already drawn as state machines. Build them as state machines.

See [ADR 0004](adr/0004-departments-are-a-metaphor.md).

## 3. You are not competing with agencies on optimisation. You have already lost that.

This is the most important business point in this document.

Meta's own automation — Advantage+ campaigns, broad targeting, automatic
placements, algorithmic bidding — has absorbed most of what media buyers used
to do by hand. Meta sees every conversion on the platform. Phoenix will see
one advertiser's. Any pitch of the form *"our AI optimises your campaigns
better than a human"* is a pitch to out-optimise a system with orders of
magnitude more data, running on its own infrastructure, for free.

Manual audience research, interest stacking, and daily bid tinkering are
largely theatre now. A product built around them is a product built around
2019.

**Where the value actually is, in order:**

1. **Creative throughput.** Accounts die of creative fatigue. An operation that
   reliably ships 30–50 on-brand, on-strategy variants a week, and knows which
   to kill, is doing the thing that still moves ROAS. This is genuinely hard
   and genuinely valuable.
2. **Measurement that is correct.** Post-ATT, in-platform ROAS is a
   directional number, not a true one. An advertiser who knows their real
   blended CAC and incrementality is making better decisions than one who does
   not. Most agencies do not deliver this. It is deterministic engineering
   work, which is exactly what we are good at.
3. **Offer and angle.** The largest performance swings come from what is being
   sold and how it is framed, not from campaign structure.
4. **Not screwing up.** No overspend, no policy strike, no account ban, no
   creative that violates a trademark. Boring, and worth more than it sounds.

Notice that 1, 2 and 4 are the parts Meta will never do for you, and 3 is where
an LLM is genuinely strong. That is the wedge.

**Recommendation: reposition from "AI media buyer" to "AI creative and
measurement operation."** Same customer, same money, defensible.

## 4. The riskiest assumption is untested, and it is cheap to test

Everything in the brief rests on: *AI-generated creative can perform at or
above agency standard.* If that is false, Phoenix is a reporting tool with a
large bill.

Do not build twenty-one departments to find out. **Phase 2 is a creative
bake-off**: same offer, same audience, same budget, AI-generated creative
against a human control set, in a real account, with a real holdout. A few
thousand dollars and three weeks buys the answer to the question the entire
company depends on.

If it wins, build everything. If it loses, you have learned it for the price of
a month's ad spend instead of a year's engineering.

## 5. Meta API access is the critical path, and it is not a coding task

Writing to the Marketing API on behalf of other businesses requires app review
and business verification, and operating as a tech provider for other
advertisers carries its own platform obligations. These are process gates
measured in weeks, and they are outside your control.

*(I have not verified current requirements or timelines — Meta changes them.
Treat this as "confirm before planning around it," not as fact.)*

**Consequence for the roadmap:** start the access process on day one, in
parallel with everything else, and design Phase 1 to be valuable using
**read-only** access on **your own** ad account. That work — ingestion,
normalisation, correct metrics, diagnosis — is the measurement plane from §3,
it is the foundation for everything after it, and it is not blocked on Meta's
review queue.

## 6. Autonomy is a liability surface, and "approval workflows" are the wrong shape

The brief lists actions requiring approval. That model breaks at scale: every
budget change becomes a notification, the customer approves fifty a week
without reading them, and the approval becomes a rubber stamp that transfers
liability without transferring judgement. You end up with the cost of a human
in the loop and none of the safety.

**The right primitive is a mandate, borrowed from how trading desks work.** A
customer grants a bounded, revocable, expiring authorisation:

```
Northbound — Meta — Aug 2026
  daily spend ceiling         £400
  max single budget change    ±25%, max 2 per campaign per week
  may:      shift budget between existing ad sets, pause underperformers,
            launch pre-approved creative into existing campaigns
  may not:  create campaigns, raise total budget, change the offer,
            touch the payment method
  expires   31 Aug 2026, or on one click
```

Inside the mandate, the system acts and reports. Outside it, the system asks.
The customer approves the *envelope* once a month rather than fifty individual
decisions, which is both safer and vastly less annoying — and every action
inside it is checked against the envelope deterministically, before execution,
by code that cannot be talked out of it.

See [ADR 0003](adr/0003-mandates-not-approvals.md) and `03-AUTONOMY.md`.

## 7. Autonomy has to be earned, in public, before it is granted

Nobody hands a new system £50k/month on day one, and they should not.

**Shadow mode** is the answer, and it is directly the Phase 11 evaluation
discipline applied to money. The decision loop runs in full — signals,
diagnosis, proposals, mandate checks — and executes **nothing**. Every proposal
is recorded with what it *would* have done. Weeks later, the actual outcome is
known, and each proposal is scored against it.

That produces a number nobody can argue with: *"over 60 days, 143 proposals; if
executed, ROAS would have been X% higher/lower."* Autonomy is then granted per
action type, on evidence, by a customer who has watched it work.

It also means the first version of Phoenix is safe by construction: it cannot
spend money, because that code path does not exist yet.

---

## What I would actually build

Same ambition, different order.

**The wedge:** an AI creative and measurement operation for DTC ecommerce
brands spending £10k–£100k/month on Meta.

**Why that customer:** they have enough spend that creative fatigue is their
binding constraint, enough data that measurement is tractable, a clean
conversion event, and a Shopify/Stripe source of truth to measure against.
They are also underserved — too big for a freelancer, too small for a good
agency's A-team.

**What you sell:**
1. *Truth* — what is actually working, measured against the store, not the
   platform.
2. *Volume* — 30–50 tested creative variants a month at a cost no human studio
   matches.
3. *Diagnosis* — why performance moved, with evidence.
4. *Safe hands* — mandates, guardrails, and an audit trail.

**What you deliberately do not sell yet:** autonomous strategy, autonomous
campaign creation, or beating Meta's algorithm.

The twenty-one departments in the brief still get built. They get built in the
order that de-risks the business, and several of them turn out to be a
scheduled function rather than an agent.

---

## The corrections, in one table

| Brief says | Recommendation | Why |
|---|---|---|
| Build on Jarvis Core | Build a **control plane** above **isolated per-client Jarvis instances** | Core is single-principal by design; one instance for many clients is a confidentiality incident |
| 21 departments as agents | Departments as **metaphor + namespace**; durable **workflows** as the execution spine | Free-form multi-agent systems are expensive, non-deterministic and undebuggable |
| AI optimises campaigns | AI produces **creative** and **measurement**; Meta optimises | You cannot out-optimise the platform on its own data |
| Approval per action | **Mandates**: bounded, revocable, expiring envelopes | Per-action approval degrades into rubber-stamping |
| Autonomy is configurable | Autonomy is **earned in shadow mode**, per action type | Nobody grants spend authority to an unproven system, and they are right |
| Build the company, then sell | **Test the creative assumption in week 3** | It is the assumption everything else rests on, and it costs a month of ad spend to check |
| Meta API is an integration | Meta API access is the **critical path**, started day one | It is a review process, not a coding task |

---

## What happens if you disagree

These are recommendations, not conditions. Tell me which ones you reject and I
will build what you asked for — the architecture in `02-ARCHITECTURE.md` is
mostly agnostic to §3 and §4, and §6 can be simplified to per-action approvals
in an afternoon.

The one I would push back on twice is **§1**. Building a multi-client agency on
a single-principal core is not a trade-off; it is a defect with a delay fuse.
