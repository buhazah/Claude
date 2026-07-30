# Phoenix — Architecture freeze and the first twenty clients

The design phase is over. This document replaces it.

---

## 1. The decision

> **Foundational architecture is frozen. It unfreezes only when a named client
> exposes a named deficiency.**
>
> **Engineering effort redirects to operating real campaigns for real
> businesses.**
>
> The goal is no longer to design the perfect AI advertising company. It is to
> discover what makes a customer willing to pay us again next month.

Nine documents and nine ADRs are enough to build against. The marginal return on
document ten was already low, and the marginal return on document eleven is
negative — every hour spent refining an abstraction is an hour not spent finding
out whether anyone wants the thing.

**This applies to the most recent work first.** `08-MOAT.md` designs machinery
that cannot function below ~50 clients: a publication gate with k=5 anonymity
cannot clear a single claim at n=20. `09-CREATIVE.md`'s learned review filter
needs hundreds of operator rejections before it can be trained. Both are correct
designs and both are, today, speculation dressed as engineering. They are frozen
and mostly unbuilt, and the sections below say exactly which parts survive.

## 2. The line: inside the tenant is live, across tenants is frozen

One rule, chosen because it is memorable enough to survive a busy week:

> **Build freely inside the tenant boundary. Freeze everything that crosses it.**

It maps almost exactly onto the value/volume divide. What a client experiences
lives inside their instance and needs n=1 to be worth building. What compounds
across clients lives above the boundary and needs n=50 to be worth anything.

| | Status | Examples |
|---|---|---|
| **Inside a tenant** | **Live — build freely** | Onboarding, reconciliation, the weekly report, diagnosis, the recommendation queue, creative generations, fatigue detection, prediction scoring for one account, anything that shortens time-to-value or removes a human hour |
| **Across tenants** | **Frozen — do not build** | Publication gate, claim store, fleet calibration curves, contradiction resolution, scope splitting, cross-client priors, the learned review filter, agency memory |
| **Structural** | **Frozen — do not change** | The spine, mandates, the channel port, tenant isolation, the neutral entity graph, ADRs 0001–0009 |
| **Scope** | **Frozen — do not extend** | A second channel adapter, self-serve onboarding, tier 3 autonomy, multi-touch attribution |

### The one carve-out: keep recording, stop building consumers

`08-MOAT.md §17` and `09-CREATIVE.md §18` both argue that some things are cheap
now and unrecoverable later. That argument survives the freeze intact, because
it is about *recording*, not building:

- **Observations** are emitted into the outbox from the first campaign. Nothing
  reads them.
- **Predictions** are recorded for every variant from the first generation.
  Scored per-client; not aggregated.
- **Override reason codes** are captured at every rejection. Nothing trains on
  them.
- **The contribution ledger** records provenance. Nothing recomputes from it.

Four append-only tables and a dropdown. Perhaps three days of work, and the
alternative is that the first two years of history exist in a shape nothing can
ever learn from. Everything downstream of these — the gate, the curves, the
filter, the priors — waits.

## 3. Unfreezing: the deficiency register

A freeze without an exception process is either ignored or blocks something
genuinely necessary. This is the process.

**To unfreeze a frozen decision, file an entry in
[`DEFICIENCIES.md`](DEFICIENCIES.md) containing all five:**

1. **A named client.** Not "clients will want." Not "at scale we would need."
2. **A specific incident**, dated. What happened, in one paragraph.
3. **What it cost** — a renewal at risk, unbilled hours, a wrong number that
   reached a client, an action we could not take.
4. **The workaround that was tried first**, and why it failed. Manual effort
   counts as a workaround and is usually the right first answer.
5. **The smallest change that resolves it** — which is very often not the
   architectural one.

**Automatic unfreeze:** the same gap logged by **three different clients**
unfreezes without further argument. Three independent clients hitting one wall is
data; one client hitting it is a client.

**What does not qualify:** a client *asking* for something. Requests are cheap
and constant. The bar is that its absence cost us something measurable — and the
most useful entries will be the ones filed after a client nearly left.

The register is also the honest record of where the blueprint was wrong. It is
expected to fill up. A register that stays empty for six months means either the
architecture was unusually good or nobody is filing, and the second is far more
likely.

## 4. What we actually do not know

The architecture assumed an answer to this and never tested it: **why would
someone pay us again next month?**

The blueprint's implicit answer is *performance* — better CAC, more creative,
correct measurement. That may be wrong, and it is wrong in a specific way worth
naming. Agency retention is famously driven by things other than results:
feeling informed, trusting the numbers, not having to think about it, and a
relationship. If any of those dominates, the cheapest deliverable in the system
outperforms the most expensive one.

Six hypotheses, ordered by how much they would change what we build:

**H1 — The weekly report is the product.**
A correct, legible weekly report costs almost nothing to produce and may be the
single thing a client would be upset to lose. If true, it reorders everything:
the expensive autonomy machinery is a feature, not the offer.
*Test:* deliberately vary the tier across the first twenty. Compare renewal.

**H2 — Trust in the numbers is the differentiator, not the numbers themselves.**
`01-PRD.md §4` says the most common complaint is *"I don't know what my agency
does."* Reconciliation against store data may sell better than any performance
improvement, because it is verifiable on the client's side and nothing else is.
*Test:* onboarding reconciliation is the first deliverable. Watch what they say.

**H3 — Clients will not act on recommendations, however good.**
Recommendation mode assumes a client's buyer executes what we deliver. If
adoption sits at 20%, the read-only tier is not a product and `00-STRATEGY.md §5`
is wrong.
*Test:* adoption rate within 7 days, from client one.

**H4 — AI creative moves a real account's frontier.**
The bake-off in `06-ROADMAP.md` Phase 2, unchanged. Still the assumption
everything rests on.
*Test:* generational lift on three real accounts.

**H5 — Human time per client does not fall.**
`07-RISKS.md` R6. If it takes eight hours a week at client three and eight hours
at client twenty, the business is an agency and should be priced and staffed as
one from that point.
*Test:* the effort ledger (§6).

**H6 — Premium pricing survives contact with a buyer.**
`07-RISKS.md §3` asserts £1.5k–7.5k/month. Nobody has been asked.
*Test:* ask. Early, and for money.

**What we deliberately cannot learn from twenty clients:** anything statistical
about the fleet. Cross-client creative patterns, scope resolution, calibration by
vertical, whether priors transfer. Those need n≈50+ and are the reason §2 freezes
that half. Do not run experiments the sample size cannot support and do not draw
conclusions from twenty clients as though they were five hundred.

## 5. Three cohorts, three questions

Twenty clients in one intake learns twenty times less than twenty in three
cohorts, because nothing gets fixed in between.

### Cohort A — clients 1–3 · *design partners*

Heavily discounted or free, and told exactly why. **Insight tier only.**

*Question:* what breaks, and what do they actually ask us for?

The founder does everything manually that can be done manually — including work
the architecture could automate. Manual is not a failure state here; it is the
instrument. Every gap a human fills is a measured requirement, and gaps filled by
humans are the only reliable source of what to automate next.

**Stop rule:** if reconciliation cannot reach 0.9 on two of three accounts, stop
and fix that before taking a paying client. `07-RISKS.md` names it as the fastest
kill criterion, and shipping a wrong number to someone who paid is worse than
having no clients.

### Cohort B — clients 4–10 · *the first money*

Full price. **Recommend tier**, plus Insight-only for two of them as H1's control.

*Question:* will they pay, and will they renew at month three?

This cohort answers H1, H2, H3 and H6 together. Two clients deliberately receive
only the report and reconciliation — no recommendations, no creative. If they
renew at the same rate as the full-service clients, H1 is true and the roadmap
changes.

**Stop rule:** fewer than four of seven renewing at month three means the offer
is wrong, not the execution. Stop selling and go and find out which part they
would have paid for.

### Cohort C — clients 11–20 · *repeatability*

**Managed tier** where write permissions arrive, Recommend where they do not.

*Question:* can somebody who is not the founder onboard and run a client?

This is where H5 is answered and where the effort ledger earns its keep. It is
also the first honest read on whether the thing is a company or a person.

**Stop rule:** if human time per client is not falling and is not flat against
account size by client twenty, R6 has fired.

## 6. The four instruments

Cheap, and between them they answer everything in §4.

**The effort ledger.** Every human minute spent on a client, categorised, weekly.
Onboarding, review, exceptions, comms, firefighting, unplanned. After twenty
clients this *is* the automation roadmap — derived from where time actually went
rather than guessed from where we expected it to go. It is the highest-value
artefact in this document and it is a spreadsheet.

**The near-churn interview.** Structured, at month two and month five, with one
question that matters: *"if we removed one part of this, which would you miss
most?"* Then ask the same about the part they would not miss. Answers go straight
into H1 and H2, and the second question kills features faster than any metric.

**The concierge log.** Every unprompted client request, verbatim, dated. What
they email asking for is what the job actually is, and it will not match
`01-PRD.md §4` exactly. Where it diverges, `01-PRD.md` is wrong.

**Renewal at a raised price.** The only unambiguous signal in the set. Not
satisfaction scores, not NPS, not engagement — a client who accepts an increase
at month six has told you something no survey can. Ask at least three of Cohort B.

## 7. What "done" looks like for this phase

Not a shipped feature. Five answers:

| Question | Answered by | Evidence |
|---|---|---|
| Will people pay, and how much? | Cohort B | Signed at stated price, renewed at month 3 |
| What would they be upset to lose? | Near-churn interviews | A ranked list, in their words |
| Does the creative engine move a real frontier? | Cohort A + B | Generational lift on three accounts |
| Does human time flatten? | Effort ledger | Minutes/client/week against account size |
| Which frozen thing did customers actually need? | Deficiency register | Entries with named clients |

The fifth is the one that matters most for what comes after, because it turns the
next architecture phase from a design exercise into a backlog written by
customers. That is the whole point of freezing.

## 8. The obvious risk, stated

Freezing architecture in favour of shipping is the correct move and it has a
well-known failure mode: twenty clients later, everything works, nothing scales,
and the codebase has absorbed twenty clients' worth of special cases that nobody
can now untangle.

Three guards, none of which is "design more":

**The invariants in `07-RISKS.md §5` do not bend.** Mandate checker, money
arithmetic, tenant isolation, no model computing a client-facing number, no
channel concept above the port, no model deciding what crosses a boundary, no
learned state that cannot be recomputed. Eight rules. Shipping pressure is
exactly the condition they were written for.

**Special cases are recorded as debt with a trigger**, in the existing table.
A per-client hack is fine. A per-client hack nobody wrote down is how the
untangling becomes impossible.

**Manual is the preferred workaround, and it is tracked.** When a client needs
something the system does not do, the first answer is a human doing it and a row
in the effort ledger. That keeps the codebase clean and converts the gap into
data, which is the trade this whole document is making.

---

## What changes tomorrow

- **Stop:** designing subsystems, extending abstractions, writing ADRs about
  things no client has hit.
- **Start:** Phase 0 and Phase 1 as written, against one real ad account.
- **Keep:** recording observations, predictions, overrides and provenance —
  three days of work, permanently unrecoverable if skipped.
- **File:** every gap into `DEFICIENCIES.md`, with a client's name on it.

The next architecture document should be written by customers.
