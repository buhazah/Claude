# Phoenix — strategy memo

**Read this one first.** You asked me not to assume your ideas are correct.
Eight sections follow: seven argue with the brief, and the eighth argues with my
own first draft. One of them — §1 — is still a blocker that has to be settled
before any code is written. Everything else in this blueprint follows from them.

None of this is a reason not to build Phoenix. It is a set of reasons to build
a more defensible Phoenix than the brief describes.

> **Revision 2.** You have since answered the four open decisions and added a
> fifth requirement. The changes, and where they land:
>
> | Your decision | What changed |
> |---|---|
> | Own the **complete acquisition workflow**; media buying is one capability, not the product | §3 below — the repositioning is narrowed, not the scope |
> | **Agency model**: operate on the client's own Business Manager and ad accounts under granted permissions | `01-PRD.md §11`, `07-RISKS.md` R5 |
> | **Premium managed service**, not low price. Maintainability, reliability and measured results over infrastructure cost | `07-RISKS.md §3` rebuilt |
> | Meta write access is a **phased capability**, not a phased roadmap | [ADR 0006](adr/0006-channels-are-adapters.md), `03-AUTONOMY.md §6` |
> | **Channel-agnostic core.** Meta is the first execution channel, not the foundation | [ADR 0006](adr/0006-channels-are-adapters.md), `02-ARCHITECTURE.md §5` |
>
> §8 below is new and is the largest structural consequence.

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

## 3. Do not compete with Meta's optimiser. Compete on the workflow around it.

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

1. **Creative throughput — and, more precisely, creative *learning rate*.**
   Accounts die of creative fatigue. An operation that reliably ships on-brand,
   on-strategy variants and knows which to kill is doing the thing that still
   moves ROAS. But volume alone converges on a house style: the harder and more
   valuable version is an engine whose *hit rate* rises because each generation
   is built on measured outcomes rather than taste (`09-CREATIVE.md`).
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

**Recommendation, as revised.** Do not pitch out-optimising Meta's auction —
that specific claim is unwinnable and everything above still holds. But the
correction stops there, and my first draft over-extended it into "sell creative
and measurement only." That was too narrow.

**What Phoenix owns is the complete acquisition workflow:**

```
strategy → research → creative generation → campaign orchestration
        → measurement → optimisation recommendations → continuous learning
```

**Media buying is one capability inside that loop, not the product.** The value
is that the whole loop is operated by one system with one memory: the research
that produced an angle is linked to the brief that tested it, to the variant
that ran, to the reconciled outcome, to the knowledge card that changed the next
brief. No agency has that, because agencies are teams handing artefacts between
tools, and no point tool has it, because each owns one stage.

The distinction that matters:

| Losing claim | Winning claim |
|---|---|
| "Our AI beats Meta's algorithm" | "Our system runs the entire acquisition function, correctly, continuously, and shows its work" |
| "We optimise bids" | "We know what is actually working, and we act on it inside a mandate you set" |
| "AI ads, cheaper" | "One accountable operation from strategy to learning, priced as a managed service" |

Meta's optimiser is not a competitor in this framing. It is a **component we
feed** — better creative, better signal, better structure — and one of several
execution channels the workflow can drive (§8).

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

## 5. Meta write access is a capability, not a milestone

Writing to the Marketing API on behalf of other businesses requires app review
and business verification, and operating as a tech provider for other
advertisers carries its own platform obligations. These are process gates
measured in weeks, and they are outside your control.

*(I have not verified current requirements or timelines — Meta changes them.
Treat this as "confirm before planning around it," not as fact.)*

My first draft called this **the critical path** and blocked Phases 3+ on it.
That was wrong, and you corrected it: the architecture should assume full
Marketing API integration while the implementation operates in read-only
analysis and recommendation mode until write permissions exist.

**How that is expressed.** Write access is a **declared capability on a channel
connection**, not a phase of the roadmap ([ADR 0006](adr/0006-channels-are-adapters.md)):

```
connection: meta / northbound
  capabilities: read.entities, read.metrics, read.creative_library
  # write.budget, write.status, write.creative — not granted
```

The decision loop is identical in both modes. It runs signals → diagnosis →
proposal → mandate check → decision. With `write.*` present, the decision is
executed. Without it, the decision is **delivered** — a ranked, evidenced,
one-click-to-copy recommendation the client's own buyer applies in Ads Manager,
and whose outcome Phoenix still measures a week later because it can read.

Three consequences worth stating plainly:

- **Recommendation mode is sellable on its own.** It is most of the value of
  §3's workflow, it needs only read permissions the client can grant in an
  afternoon, and it is how every client starts regardless.
- **It is also the safest possible ramp.** A client watching recommendations be
  right for six weeks is the person who grants a write mandate. Shadow mode
  (§7) and recommendation mode share a code path and differ only in whether the
  proposal is shown to the client.
- **Nothing waits on Meta's review queue.** Start the process on day one anyway,
  because it takes as long as it takes — but no phase of the build is blocked
  behind it.

And because the operating model is **agency** — Phoenix works inside the
client's existing Business Manager and ad accounts under permissions they grant,
never holding the accounts and never reselling the spend — the permission is
theirs to give, per account, at whatever pace their trust moves. We are not
waiting on one platform decision that unblocks every client at once; we are
earning one grant at a time.

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

## 8. Meta is the first channel, not the foundation

Your requirement, and the largest structural change in this revision: the core
stays channel-agnostic so Google Ads, TikTok and others can be added without a
redesign.

I agree, and I would have got this wrong. My first draft named the data model
after Meta's nouns — `Campaign`, `AdSet`, `Ad` — enumerated Meta verbs in the
mandate, and filed "a second platform" under *not on this roadmap*. That is the
version of this system that is cheapest to ship and most expensive to change,
because the retrofit lands in the data model, the mandate checker and the
historical metric store simultaneously, after there is client history sitting in
Meta-shaped rows.

**The correction, stated as an invariant:**

> Everything that is not literally an API call to an ad platform must be
> channel-neutral. Strategy, research, briefs, creative and its lineage, the
> signal→outcome spine, mandates, approvals, memory, knowledge cards, workflows,
> reporting and evaluation import no channel. One composition root knows Meta
> exists.

Concretely, the graph Phoenix stores is four neutral levels that every adapter
maps onto, with the client's own vocabulary restored at the display layer:

```
Account → Program → Group → Placement
   Meta:  Ad Account / Campaign / Ad Set / Ad
   Google: Customer / Campaign / Ad Group / Ad
   TikTok: Advertiser / Campaign / Ad Group / Ad
```

Actions are verbs with magnitudes — `shift_budget`, `set_status`,
`launch_creative` — validated by a mandate checker that has never heard of
Meta. Metrics are normalised at the boundary with their attribution basis
attached, so cross-channel arithmetic is refused rather than silently wrong.

**What this costs:** roughly two weeks of extra work in Phase 1, one indirection
layer, and the ongoing discipline of not letting a Meta concept leak upward when
it would be convenient. **What it buys:** a second channel is an adapter and an
evaluation suite, and the knowledge layer — the actual moat — can see across
channels, which is the one place where cross-channel is worth more than the sum
of its parts.

The honest caveat: a neutral graph cannot express everything. Advantage+
specifics, Meta's experiment tooling, Google's asset groups. Those are exposed
as adapter-specific actions that a mandate must enumerate explicitly, treated as
opt-in rather than pretended to generalise. Full design in
[ADR 0006](adr/0006-channels-are-adapters.md).

---

## What I would actually build

Same ambition, different order.

**The wedge:** an AI-operated acquisition function for DTC ecommerce brands
spending £10k–£100k/month, with Meta as the first execution channel.

**Why that customer:** they have enough spend that creative fatigue is their
binding constraint, enough data that measurement is tractable, a clean
conversion event, and a Shopify/Stripe source of truth to measure against.
They are also underserved — too big for a freelancer, too small for a good
agency's A-team.

**What you sell:** an accountable acquisition function, priced as a premium
managed service.

1. *Truth* — what is actually working, measured against the store, not the
   platform.
2. *Volume* — 30–50 tested creative variants a month at a cost no human studio
   matches.
3. *Diagnosis* — why performance moved, with evidence.
4. *Decisions* — ranked, evidenced, and either executed under mandate or handed
   over to be executed, depending on what the client has granted.
5. *Safe hands* — mandates, guardrails, and an audit trail.
6. *Compounding* — knowledge cards that make client fifty better served than
   client five.

**What you deliberately do not sell yet:** autonomous campaign creation, offer
changes, or beating Meta's auction.

**What defends it once every competitor has copied the product:** not the
features — all of them copy — but the stock of outcome-labelled judgment that
only operating produces, and the rate at which it is resolved against decay.
Designed in `08-MOAT.md`, and deliberately falsifiable: if primed briefs do not
beat cold briefs, there is no moat and the machinery should go.

The twenty-one departments in the brief still get built. They get built in the
order that de-risks the business, and several of them turn out to be a
scheduled function rather than an agent.

---

## The corrections, in one table

| Brief says | Recommendation | Status | Why |
|---|---|---|---|
| Build on Jarvis Core | Build a **control plane** above **isolated per-client Jarvis instances** | open — §1 blocker | Core is single-principal by design; one instance for many clients is a confidentiality incident |
| 21 departments as agents | Departments as **metaphor + namespace**; durable **workflows** as the execution spine | proposed | Free-form multi-agent systems are expensive, non-deterministic and undebuggable |
| AI optimises campaigns | Own the **complete acquisition workflow**; do not claim to beat Meta's auction. Media buying is one capability | **accepted, narrowed** | The auction claim is unwinnable; the workflow claim is defensible and larger |
| Approval per action | **Mandates**: bounded, revocable, expiring envelopes | proposed | Per-action approval degrades into rubber-stamping |
| Autonomy is configurable | Autonomy is **earned in shadow mode**, per action type | proposed | Nobody grants spend authority to an unproven system, and they are right |
| Build the company, then sell | **Test the creative assumption in week 3** | proposed | It is the assumption everything else rests on, and it costs a month of ad spend to check |
| Meta API is an integration | Meta write access is a **declared capability**; recommendation mode is a first-class operating mode | **accepted, revised** | A capability flag makes read-only a product; a roadmap phase makes it a waiting room |
| *(new)* Meta is the platform | Meta is the **first adapter**; the core is channel-agnostic | **your requirement** | Retrofitting a channel abstraction is the most expensive refactor available |

## The four decisions, now answered

| Question | Your answer | Where it lands |
|---|---|---|
| Accept the repositioning? | Partially — own the whole workflow, drop only the auction claim | §3, `01-PRD.md §1` |
| Agency or software? | **Agency.** Client's own Business Manager and ad accounts, granted permissions, no spend reselling | `01-PRD.md §11`, `07-RISKS.md` R5 |
| What is the price? | **Premium managed service.** Do not optimise the architecture for a low price point | `07-RISKS.md §3` |
| Can Meta write access be obtained? | Design for full integration, implement so read-only works indefinitely | §5, ADR 0006 |

---

## What happens if you disagree

> **As of ADR 0010, this argument is closed and the architecture is frozen.**
> Disagreement from here needs a client's name attached — file it in
> `DEFICIENCIES.md`. The section below is kept as the record of how the argument
> was settled.

These were recommendations, not conditions. Tell me which ones you reject and I
will build what you asked for.

The one I would push back on twice is **§1**. Building a multi-client agency on
a single-principal core is not a trade-off; it is a defect with a delay fuse.
It is also the one decision the agency model does not soften: operating on the
client's own Business Manager reduces our financial exposure, and changes
nothing about the fact that fifteen clients' performance data would share one
memory namespace.
