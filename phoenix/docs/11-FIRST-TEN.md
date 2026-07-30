# Phoenix — The first ten paying customers

The operating plan. Not a design document — the thing you run a Monday from.

Governed by [`../CHARTER.md`](../CHARTER.md). Operates inside the freeze in
[`10-VALIDATION.md`](10-VALIDATION.md), and refines two things that document got
slightly wrong (§2, §9).

**The objective is not automation. It is ten paying customers and a clear answer
to what they repeatedly value.** Optimise for learning speed and trust; ignore
scale entirely.

---

## 1. The first-customer profile

The charter defines who we serve permanently. The *first ten* need three extra
properties that a good long-term customer does not:

**They tolerate roughness. They talk to us. We can actually reach them.**

The third is the one that gets skipped. An ideal customer we cannot find is not a
customer, and we have no marketing machine.

### Hard requirements

| | Why, for the first ten specifically |
|---|---|
| **Physical product, direct to consumer** | Purchases are discrete, returns are visible, revenue truth exists in one place |
| **One market, one currency** | Multi-currency reconciliation is a two-week rabbit hole. Not in month one |
| **Tight catalogue** — under ~200 lines | Measurement complexity scales with catalogue, and complexity here is time we do not have |
| **£15k–60k/month acquisition spend** | Narrower than the permanent ICP. Below £15k a real fee is an uncomfortable share of spend; above £60k the account is complex enough to eat a month |
| **6+ months of history on one main channel** | Something to baseline against and something to diagnose |
| **Founder-led, under ~50 people** | One person decides, and that person feels the money |
| **They answer the phone** | A customer who will not take a 30-minute call weekly teaches us nothing, whatever they pay |
| **Already disappointed by an agency** | The single best qualifier. They believe the problem exists and can describe it in their own words |

### Turn away, for now

Beyond the charter's permanent refusals, five that are specific to being early:

- **Multi-region or multi-currency.** Later.
- **Mixed subscription and one-time revenue.** LTV modelling on day one is how a
  simple engagement becomes a research project.
- **Marketplace-dependent sellers.** No independent revenue truth, so §2's gate
  cannot pass.
- **Anyone with an in-house acquisition team.** Political risk kills the
  engagement for reasons that teach us nothing about the product.
- **Agencies wanting a white-label arrangement.** Looks like fast revenue,
  destroys the learning loop entirely — we would never meet the customer whose
  behaviour is the entire point of this phase.

### Where the first ten come from

**Fully specified in [`12-FOUNDER-LED-ACQUISITION.md §2`](12-FOUNDER-LED-ACQUISITION.md)**,
along with buying triggers, outreach, the sales conversation and objection
handling. In short: referral partners who serve the same customer without
competing — fractional CFOs and ecommerce accountants first — then warm network,
then referrals from clients 1–3, then communities, then narrow trigger-scraped
outbound.

**Not paid acquisition.** We would be spending on a channel we have not yet
proven we are good at, with no results to point to. When we can show three
clients' verified numbers, that changes.

## 2. The offer

One offer. One price. Two steps. Complexity in an offer is a tax paid by a buyer
who has not yet decided to trust you.

### The pitch, in one sentence

> **We run your paid acquisition and measure it against your own revenue rather
> than the platform's. Fixed monthly fee, thirty days' notice, and your ad
> accounts stay yours.**

Three differentiators, each a charter clause rather than a marketing claim:
independent measurement, a fee that does not rise when we spend more, and no
transfer of accounts or lock-in.

### Step one — the Acquisition Audit

```
£1,500 · fixed scope · two weeks · credited in full against the first month
```

- Reconcile the last 90 days of platform-reported performance against their own
  revenue records, and state the difference
- Diagnose what actually drove the last quarter
- A written 90-day plan with named hypotheses

**The audit is doing four jobs at once**, which is why it is the whole top of the
funnel: it is the lead magnet, the qualifier, the demonstration, and the first
half of onboarding. Nothing else in this plan is that efficient.

It also protects both sides. **If we cannot reconcile their revenue, we say so,
refund the fee, and decline the engagement** — before anyone has promised
anything monthly. That is the charter's *"we will not take work whose success we
cannot measure"* made operational, and doing it once in front of a prospect
teaches them more about us than any case study.

### Step two — Phoenix Monthly

```
£4,000/month · 30 days' notice · no minimum term · audit fee credited
```

Measurement and reconciliation, the weekly report, creative generations,
diagnosis, ranked recommendations. Execution on their accounts where and when
they grant permission — never as a condition of starting.

**Why one price and not the three tiers in `07-RISKS.md §3`:** tiers are for when
you know what people want. We do not, and asking a buyer to choose between three
things they cannot yet evaluate transfers our uncertainty onto them. Tiering is a
month-six decision informed by §7's convergence data.

**Why £4,000:** high enough to attract a buyer who is serious and to fund a real
service; low enough to sit below most procurement thresholds and be decided by
one person in one conversation.

**Why thirty days' notice:** charter clause 8. It is also the strongest
competitive line available against twelve-month agency retainers, and it forces
the discipline this entire phase exists to test.

### Clients 1–3 — design partners

**£2,000/month, in exchange for obligations, not as a discount.** Written into
the agreement:

- A 30-minute call every week, for six months
- Permission to use their results, anonymised, in selling to others
- Tolerance for a service that is visibly rough at the edges

> **This supersedes `10-VALIDATION.md §5`, which said "heavily discounted or
> free."** Free was wrong. A client who pays nothing does not behave like a
> customer, does not complain like one, and does not renew like one — and their
> retention signal, which is the only thing this phase is buying, is worthless.
> Everyone pays. The first three pay less and give more.

## 3. Onboarding

Fourteen days from signature to first report. One hard gate on day five.

| Day | What happens | Who |
|---|---|---|
| **0** | Agreement signed. Access request sent — a single checklist, read-only only | ops |
| **1–2** | Access granted and each connection verified end to end. **Never billing permissions** | ops |
| **3–4** | Ingest 12 months of platform data and store revenue. Snapshot everything with its as-of date | system |
| **5** | **Reconciliation attempt — the gate** | system + human |
| **5** | **Reconciliation review call.** The trust moment (below) | founder |
| **6–8** | Discovery: margins, returns, offer economics, brand rules, constraints, what has already been tried | founder |
| **8** | 90-day baseline agreed **in writing**, including what we will not claim credit for | founder |
| **9–10** | Strategy: 6–8 named hypotheses, each with a test and a kill condition. Authority conversation | founder |
| **11–13** | First creative generation built and reviewed | ops |
| **14** | **First weekly report and first ranked recommendations delivered** | founder |

### The day-five gate

**If reconciliation confidence does not reach 0.9, onboarding stops.** Three
outcomes, decided that day:

- **Fixable tracking problem** → we fix it, billed separately, and it is
  genuinely valuable work. Restart the clock.
- **Not fixable inside two weeks** → refund and decline, with a written
  explanation of what would need to be true.
- **Reconciles** → proceed.

No exceptions and no "we'll sort it as we go." Optimising against numbers that
are wrong is the failure mode this entire company is positioned against, and the
first time we are tempted to waive it will be with a client we want.

### The reconciliation review call

Forty-five minutes, and probably the highest-leverage meeting in the whole
relationship. It is where the client sees, usually for the first time, that the
platform's reported revenue and their own bank records disagree — and by how
much.

Structure it deliberately:

1. *"Here is what the platform reported for the last 90 days."*
2. *"Here is what your own records show."*
3. *"Here is the gap, and here is what explains it."*
4. *"Here is what we can measure with confidence, and here is what we cannot."*
5. *"Everything we report from now on comes from column two."*

Do not soften the number and do not use it to attack their previous agency. The
gap is a property of the medium, not evidence of anyone's dishonesty, and saying
so is what makes the rest of the meeting credible.

**Record what they say when they see it.** That reaction is the first and
cleanest datapoint on §7's convergence question.

## 4. The operating process

The human is **the instrument, not the fallback**. Every edit a person makes to
what the system produced is a logged requirement — so the process is built to
make overriding easy and to record it, rather than to make it exceptional.

### The weekly rhythm, per client

| When | What | Human time |
|---|---|---|
| Mon overnight | Ingest, reconcile, snapshot | 0 |
| Mon am | Review the exception list — connection health, reconciliation drift, anything stale | 15 min |
| Mon pm | Read the draft diagnosis. Correct it. **Log every correction** | 20 min |
| Tue | Creative review: approve, reject or send back. Reason code on every rejection | 30 min |
| Wed | Rank and finalise recommendations. Deliver them | 15 min |
| Thu | Client contact if anything needs a conversation | as needed |
| Fri | Read the report end to end. Edit. Send | 20 min |

**Target ~100 minutes per client per week at steady state. Expect 4–6 hours for
the first month of each client, and do not fight it** — that early time is where
the requirements come from.

### The fortnightly and monthly beats

- **Fortnightly:** close the creative generation. Score every prediction. Publish
  what was learned to the client. Open the next generation with a new control.
- **Monthly:** business review. What we said we would do, what we did, what
  happened, what it cost. Renew or revise the authority. Ask the value question
  in §7.

### The four things a human owns

Everything else is either automated or does not happen:

1. **Every number that leaves the building.** Read before sending, always.
2. **Every creative that ships.** The taste call is not delegated for the first
   ten — it is being observed.
3. **Every recommendation.** Ranked by a person, so we find out what the ranking
   rules should be.
4. **The relationship.** No queue, no ticketing system. A name and a phone.

**Nothing reaches a client unread by a human. Zero exceptions through client
ten.** This is not caution about quality; it is the mechanism by which we learn
what the system gets wrong.

### Every override is logged

A rejection without a reason code is a lost lesson. The categories are
deliberately few, because a long list gets used carelessly:

```
wrong_number · wrong_diagnosis · off_brand · commercially_naive
· badly_written · right_but_untimely · client_specific_context
```

`commercially_naive` is the one to watch. It is the failure class that
`03-AUTONOMY.md §9` admits code cannot catch, and a hundred labelled instances
of it is worth more than anything else we collect in this phase.

## 5. Minimum product capabilities

Ruthless. Ten clients with humans doing everything else needs seven things.

### Build

1. **Ingest** — channel entities and metrics, store revenue and orders, with
   append-only `as_of` snapshots
2. **Reconciliation** — platform-reported against store-recorded, producing a
   confidence figure. *The gate in §3 and the differentiator in §2*
3. **Metric store** — normalised, queryable, with provenance on every figure
4. **Report generator** — every number passed in, prose generated, human edits
   before sending
5. **Creative pipeline** — brief → concept → asset → variant, with the brand and
   claim-provenance gates. Generations and tier allocation from ADR 0009
6. **The record** — hypotheses, predictions, outcomes, overrides with reason
   codes, and an audit log. *Cheap now, unrecoverable later*
7. **One isolated instance per client**, provisioned by hand

### Do not build

| Not building | Because |
|---|---|
| Control plane, fleet scheduler, automated provisioning | Ten instances are provisioned by hand in an afternoon each |
| Automated actuation | Recommendations are delivered; the client's team or ours executes manually |
| The mandate checker in code | **Nothing can act automatically, so the surface does not exist.** This looks like a violation of the `07-RISKS.md §5` invariant and is not — the invariant binds the moment code can act, and that moment is not in this phase |
| Signal detectors | A person reading ten accounts weekly is faster to build and better at it |
| Recommendation ranking engine | A person ranks five items. We are learning what the rules should be |
| Client portal or dashboard | The report is a document. The decision ledger is a shared document. A portal built now would encode guesses |
| Chat interface | The escape hatch is a phone number |
| Everything above the tenant boundary | Frozen (ADR 0010). Cannot clear its own anonymity gate at n=10 anyway |

The product for the first ten is **ingest, reconcile, report, generate, record.**
Five verbs.

## 6. Success metrics for the first 90 days

Ninety days from the *first paying customer*, not from today.

### The four that decide continue-or-stop

| Metric | Target | If missed |
|---|---|---|
| **Paying customers** | 10 | Below 6 — the offer or the ICP is wrong, not the execution. Stop selling and go and find out which |
| **Still paying at day 90** | ≥7 of those who reached month three | Below half — we are not delivering what they bought |
| **Convergence of stated value** | **≥5 of 10 name the same thing** as what they would most hate to lose | No convergence — we have ten bespoke engagements, not a product |
| **Reconciliation succeeded** | ≥8 of 10 accounts at ≥0.9 | Below 6 — the central promise is not deliverable and `07-RISKS.md`'s fastest kill criterion has fired |

**Convergence is the real objective of this phase.** Not satisfaction, not
performance — *agreement*. Ten happy clients who each value a different thing
means we have not found the product, and the honest read on that is worse than
five clients who all say the same sentence.

### The five that inform what comes next

- Human hours per client per week, and the trend across clients 1→10
- Time from access granted to first verified insight — target under 7 days
- Recommendation adoption rate within 7 days
- **Entries in `DEFICIENCIES.md`** — should be non-zero. An empty register means
  nobody is filing
- Gross margin per client at *actually delivered* cost, not modelled cost

### The three that must be zero

Charter §6, unchanged: actions taken outside a granted authority; reported
figures that could not be reconciled; client account losses we caused.

### Deliberately not judged in 90 days

- **Acquisition cost improvement as a headline.** Measure it, report it, do not
  conclude from it. Ninety days is one or two creative cycles and mostly noise on
  most accounts.
- **Creative win rate across clients.** n is far too small.
- Anything about the fleet, cross-client patterns, or calibration by scope.

Drawing fleet conclusions from ten clients is how a company convinces itself of
things.

## 7. What stays manual, and why

Three different reasons, and confusing them is how the wrong thing gets
automated first.

### A · Manual because it is the instrument

Automating any of these before client ten destroys the reason for doing this
phase at all.

| Stays manual | What it is teaching us |
|---|---|
| Every client conversation | What they actually value, in their words |
| Creative selection | What "good" means here, before a filter is trained on it |
| The final read of every report | Where the generated prose is wrong, subtly |
| Discovery interviews | What questions actually matter — the script is being written by doing it |
| Interpreting the diagnosis | Which explanations a client accepts and which they dismiss |
| Ranking recommendations | The ranking rules, which we do not yet know |

### B · Manual because it is cheap at n=10

Automate later, when the ledger says the hours justify it — not before.

Provisioning · scheduling · signal detection · report distribution · invoicing ·
connection health checks · onboarding coordination

### C · Manual because automating it now would be reckless

Anything that touches the client's account. Anything that sends without a human
read. Both stay manual until there is measured evidence, per ADR 0005.

### The effort ledger decides what gets automated

Every manual action gets a line: client, date, minutes, category, and whether it
was **A** (instrument), **B** (cheap for now) or **C** (unsafe to automate).

After 90 days, sort category B by total hours descending. **That list is the
automation backlog** — derived from where time actually went, not from where we
expected it to go. Category A is not on the backlog at all until the learning is
banked, and category C waits for evidence.

Template in [`EFFORT-LEDGER.md`](EFFORT-LEDGER.md).

### The founder trap

If the founder is the only person who can run a client, we have learned about the
founder rather than about the process.

**By client seven, someone else runs at least two clients end to end, from a
written runbook.** The runbook is written *as the founder works*, not
afterwards — the gap between what the runbook says and what actually has to
happen is the most honest map of the product we will ever get.

---

## The single question this phase answers

Everything above is instrumentation for one sentence:

> **What is the thing our clients would be most upset to lose?**

Ask it directly at every monthly review, in these words, and write down the
answer verbatim rather than paraphrasing it into a category —
[`DISCOVERY-LOG.md §4`](DISCOVERY-LOG.md).

If five of ten give the same answer, that is the product, and the next twelve
months build around it. If the answers scatter, we have ten consulting
engagements wearing a product's clothes — and finding that out in ninety days for
the price of ten clients is the cheapest possible way to learn it.
