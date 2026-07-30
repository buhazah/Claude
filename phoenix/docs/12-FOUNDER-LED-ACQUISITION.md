# Phase 12 — Founder-Led Acquisition

Ten paying customers, served by hand, and a written answer to what Phoenix
should become.

Governed by [`../CHARTER.md`](../CHARTER.md) and the freeze in
[ADR 0010](adr/0010-architecture-is-frozen.md). Delivery mechanics live in
[`11-FIRST-TEN.md`](11-FIRST-TEN.md) and are not repeated here — this document
adds the two things that were missing: **how customers are acquired**, and **how
what they tell us is captured.**

> **This phase ships no new product capability.** The build list in
> `11-FIRST-TEN.md §5` is closed for the duration. Every hour of engineering goes
> to keeping five verbs working for ten clients: ingest, reconcile, report,
> generate, record.

---

## 1. Ideal customer profile

### The shape

| | |
|---|---|
| **Industry** | Direct-to-consumer physical products. Apparel, home, beauty, accessories, food and drink. One market, one currency, catalogue under ~200 lines |
| **Revenue** | **£1m–5m/year.** Below that, a £4k fee is an unreasonable share of everything; above it, an in-house hire becomes the obvious alternative |
| **Ad spend** | **£15k–60k/month**, roughly 15–25% of revenue. At least six months of history on one main channel |
| **Shape** | Founder-led, under ~50 people, one person decides |
| **Truth source** | Their own store and payment records — a measure of revenue we do not control |

### The problems they already have, in their words

Not our framing. Theirs, because these are the sentences outreach has to echo:

- *"I don't actually know what's working."*
- *"The platform says 4× and my bank account says otherwise."*
- *"We tried to scale and CAC just fell apart."*
- *"I pay them £5k a month and I genuinely don't know what they do all week."*
- *"Our creative is stale and we can't produce fast enough."*
- *"Every time I ask for a straight answer I get a dashboard."*
- *"Since the tracking changed I've been flying blind."*

The first two are the wedge. The rest are symptoms of them.

### Buying triggers — who is in market *now*

The most-skipped part of an ICP, and the one that decides whether outreach works.
Ranked by conversion and by how findable the trigger is:

| Trigger | Why it converts | How we spot it |
|---|---|---|
| **A finance hire is asking questions marketing cannot answer** | Someone senior now demands provable numbers. Our exact pitch, asked internally | New CFO/FD/fractional-CFO announcements; referral partners |
| **Agency contract ending, or just ended** | Active decision, budget already allocated | Referrals; job postings; direct ask |
| **A scaling attempt failed** | Doubled spend, CAC blew up, nobody can explain why | They talk about it publicly and in communities |
| **Tracking broke and they know it** | They have just discovered their numbers are wrong | Platform/analytics migrations, replatforming |
| **The person who ran ads left** | Sudden capability gap with money still flowing | Job postings — the cheapest signal available |
| **They just raised, or profitability pressure arrived** | The acquisition line is suddenly under scrutiny | Funding announcements |
| **8–12 weeks before their peak season** | Urgency with a deadline attached | Their category calendar |

**A prospect with no trigger is a prospect with no deadline.** They will have a
pleasant conversation, agree with everything, and not buy. Log them and move on;
triggers arrive on their own schedule and the log is what makes the follow-up
easy when one does.

### Disqualifiers

**Permanent** (charter): unmeasurable outcomes, price shoppers, anyone needing a
flattering story, anyone wanting us to hold accounts or billing.

**For this phase specifically:**

- Multi-region or multi-currency
- Mixed subscription and one-off revenue
- Marketplace-dependent — no independent revenue truth
- An in-house acquisition team — political risk that teaches us nothing
- **White-label arrangements with other agencies.** Looks like fast revenue and
  destroys the entire phase: we would never meet the customer whose behaviour is
  the only thing we are buying
- Mid-replatform
- Anyone who will not commit to a monthly call

## 2. Acquisition strategy

Founder-led means **low volume, high signal.** Ten real conversations a week, not
five hundred emails. The constraint is deliberate — a sequence that converts at
1% teaches nothing about why the 99% said no.

### Where these customers are found

Ranked by expected yield per hour:

**1 · Referral partners who serve the same customer and do not compete.**
The highest-yield channel and the least obvious.

> **Fractional CFOs and ecommerce accountants are the sharpest of these.** They
> are the people already being asked *"is this ad spend actually working?"* by
> exactly our ICP, and they have no answer, because the only numbers available
> come from the party being paid. We are the answer to a question they are
> already fielding.

Also: 3PLs, retention and email agencies, Shopify development shops, brand
studios. Each sees the ICP monthly and none competes with us. Approach them with
the audit, not with a commission scheme — an accountant who has watched one
client's reconciliation call will refer without being paid to.

**2 · Warm network, mapped explicitly.** Write down fifty names before sending
anything. Most founders have twenty they have not thought about.

**3 · Referrals from clients 1–3.** The reason design partners are chosen partly
for who they know, and the reason the weekly call is contractual.

**4 · Communities where this ICP actually spends time.** Ecommerce founder
groups, category-specific forums, local meetups. Participate for a month before
mentioning what you do. Publishing one genuinely useful reconciliation
teardown — anonymised, with real numbers — outperforms a hundred outbound emails.

**5 · Trigger-scraped outbound**, narrow. Job postings for paid-media roles are
the cheapest trigger signal in existence and nobody works them.

**Not paid acquisition.** We would be spending on a channel we have not yet
proven we are good at, with no verified results to point to. That changes when
three clients' numbers can be shown.

### Outreach approach

**One message, personal, with a specific observation about them.** No sequences,
no templates that survive contact unchanged, no automation. This is expensive per
prospect and correct at this volume.

Before contact, spend fifteen minutes on their public surface — ads currently
running, landing pages, pricing, offer structure — and find **one specific,
checkable observation.** Not a compliment and not a criticism: an observation.

```
Subject: your [specific thing] — one observation

[Name] — I look at acquisition for DTC brands doing £1–5m,
specifically whether the numbers they're given match what
their bank actually shows.

Watching your ads this week: [one specific, checkable
observation — a creative running 90+ days, a landing page
that doesn't match the ad's claim, three variants all
testing the same thing].

Not pitching. One question, and I'm curious rather than
selling: when you look at last month, where does your
cost-per-customer number come from?

Most founders I ask say "the platform." Most of the time
it disagrees with their accountant by 20-40%.

Worth twenty minutes?

[Founder]
```

Why this shape: the observation proves the work was done, the question is the
diagnostic that opens the gap, the statistic is falsifiable and about *them*
rather than about us, and the ask is twenty minutes rather than a demo.

**Volume target: 25 contacts and 5–8 real conversations per week.** Anything more
and the personalisation is fake, which is the only thing making this work.

### First conversation — thirty minutes

The goal is **not** to sell. It is to find out whether a trigger exists and to
hear the problem in their language. A conversation that ends in a clean
disqualification is a success and takes fifteen minutes.

| Minutes | Purpose |
|---|---|
| **0–5** | Context. What are you spending, on what, who runs it, since when |
| **5–18** | **The seven diagnostics** (below). Ask, then be quiet |
| **18–22** | Reflect the problem back **in their exact words**. If they correct you, you had it wrong — write down the correction |
| **22–27** | The audit, or the disqualification. Both said plainly |
| **27–30** | Next step with a date on it |

#### The seven diagnostic questions

Ordered so each opens the next. Question 3 does most of the work.

1. *"When you look at last month, how do you know it worked?"*
2. *"If I asked what a customer costs you to acquire, where would that number come from?"*
3. **"Does that number match what your accountant or your bank sees?"**
4. *"What happened the last time you tried to scale?"*
5. *"Who tells you what happened each week — and do you read it?"*
6. *"What would you need to see to be comfortable spending twice as much?"*
7. *"What's the last thing your agency or your tools did that annoyed you?"*

**Question 3 is the pivot of the entire sale.** The honest answers are *"no,"*
*"I don't know,"* or a long pause. Any of the three opens the gap we are
positioned on, and none of them requires us to criticise anyone.

Question 7 is the cheapest churn research available — the incumbent's failure
mode is our onboarding checklist.

**Write down verbatim answers to 1, 3 and 7 during the call.** They go to
`DISCOVERY-LOG.md` the same day, unparaphrased.

### Positioning the audit

```
£1,500 · two weeks · credited in full against the first month
· refunded if we cannot reconcile your revenue
```

Four framing decisions, each of which matters more than the price:

**It is paid, deliberately.** A free audit is a sales artefact, gets read for
four minutes, and creates an obligation the prospect resents. A paid audit is a
small commercial relationship in which we are accountable and they are engaged.
It also filters — anyone unwilling to spend £1,500 to find out whether their £30k
a month is working has told us something useful.

**It is diagnosis before treatment.** *"I don't yet know whether we can help you.
This is how we both find out."* This is the most credible sentence available to a
company with no case studies, and it happens to be true.

**It can conclude that they do not need us**, and that outcome is named up front.
An audit that can only recommend buying is a brochure.

**The deliverable is three numbers they do not currently have:**

1. What the platform reported for the last 90 days
2. What their own records show for the same period
3. The gap, decomposed into what explains it

Plus what we can measure with confidence, what we cannot, and a 90-day plan with
named hypotheses.

### Objection handling

Answers are short, honest, and never defensive. Every objection heard goes into
the register in §4 verbatim — **including the ones we answered badly.**

| Objection | Answer |
|---|---|
| *"We already have an agency."* | "Good — I'm not asking you to fire anyone. The audit tells you whether what they're doing is working, measured against your own revenue. If it is, that's worth £1,500 to know." |
| *"£4k is more than we pay now."* | "What are you paying as a percentage of spend? Most arrangements here are 10–15%, so at your spend that's £3–9k — and it rises every time you scale. Ours doesn't. When the right answer is *spend less*, nothing in how I'm paid argues with it." |
| *"You have no case studies."* | "Correct. That's exactly why the audit is £1,500 and refundable, and why there's no minimum term. You can fire me with thirty days' notice from month one. I have to earn it every month, which is the arrangement I'd want if I were you." |
| *"Can't I just use AI tools myself?"* | "You can, and they're getting good. The tools aren't the bottleneck — the measurement is. Who reconciles the output against your bank?" |
| *"Is this all done by AI?"* | "Software does the volume. A person reads everything before it reaches you, and every number traces to a source you can check yourself. You'll always know which is which." |
| *"We're too busy right now."* | "The audit costs you about ninety minutes total: one call for access, one call for the findings." |
| *"What if it doesn't work?"* | "Thirty days' notice, no minimum term, and I'll tell you before you tell me. The reconciliation either works in the first two weeks or I refund you and say so." |
| *"Is my data safe? Do you use it for other clients?"* | "Your accounts stay yours, we never take billing permissions, and nothing about your business — no creative, no copy, no numbers — ever reaches another client. What we learn in general is aggregated across at least five businesses with no content attached, and if you leave, we remove your contribution." |
| *"Send me some information."* | Usually a soft no. "Happy to — but so I send the right thing: which of the two matters more, not knowing what's working, or not being able to produce creative fast enough?" One more question buys a real answer. |

**The AI question deserves the honest answer**, not a deflection. A defensive
response to *"is this just AI?"* loses the deal outright; the audit trail is a
better answer than any reassurance.

### The funnel, working backwards

Ten customers in twelve weeks, at rates worth checking against reality weekly:

```
275 targeted contacts        ~23/week
 →  55 conversations          20%      ~5/week
 →  17 audits sold            30%
 →  10 monthly clients        60%      (a paid, qualified step should convert high)
```

**Track each rate weekly and treat a miss as information about the stage, not
about the effort.** Contacts-to-conversations failing means the observation in
the message is not landing. Conversations-to-audits failing means the trigger
qualification is wrong. Audits-to-monthly failing is the serious one — it means
the audit is not producing something they want more of, and that is a finding
about the product, not about the sales process.

## 3. Customer operating process

Onboarding, the day-five gate, the reconciliation review call and the weekly
rhythm are specified in [`11-FIRST-TEN.md §3–4`](11-FIRST-TEN.md) and are not
repeated. What follows is only the audit itself, done by hand.

### Delivering the audit manually

Two weeks, roughly 8–10 hours of founder time. Deliberately manual — this is
where the requirements for everything downstream come from.

| Day | Work | Hours |
|---|---|---|
| **0** | Access call. Read-only, least privilege, **never billing**. Verify each connection end to end while on the call | 0.5 |
| **1–2** | Export 12 months: platform performance by day and entity; store orders with dates, values, discount codes, refund status, new-vs-returning; payment-processor settlements | 1.5 |
| **3–5** | **Reconciliation** (below). The real work | 3 |
| **6–7** | Diagnosis: what actually moved the last quarter, with evidence | 2 |
| **8–9** | Write-up. Short | 1.5 |
| **10** | **Presentation call**, structured per `11-FIRST-TEN.md §3` | 0.75 |

A spreadsheet is an acceptable tool for the first three audits. The point is to
learn what the reconciliation actually has to handle before encoding it, and
every awkward case found by hand becomes a test later.

### How reconciliation is performed

Six steps, in order. Stop and report at whichever step fails.

**1 · Headline comparison.** Platform-reported conversions and revenue for 90
days against store-recorded orders and revenue for the same window. Note the gap
before explaining it — the raw number is the one that lands on the call.

**2 · Daily alignment.** Compare by day, not just in total. Correlation and lag
distinguish an attribution-window artefact from a tracking failure. Matching
totals with mismatched daily shapes is a worse finding than a clean gap, and it
is invisible in a monthly view.

**3 · Decompose the gap.** In this order, because it is the order of size:

```
attribution window     platform credits a sale outside our comparison period
view-through           counted by the platform, invisible in the store
refunds and returns    store net, platform gross
cancelled orders       counted at checkout, never shipped
offline and phone      real revenue the platform never sees
discount stacking      revenue recorded at a different value
subscription renewals  recurring revenue misread as acquisition
currency and tax       gross vs net of VAT
```

**4 · Blended CAC from their records.** Total acquisition spend ÷ net new
customers identified in the store. This is the number the whole engagement turns
on, and it usually differs materially from anything they have been shown.

**5 · Confidence.** What proportion of the gap is explained by steps 3 and 4.
**Below 0.9, we do not proceed to a monthly engagement** — we fix the tracking
(billed separately, and genuinely valuable) or we refund and decline.

**6 · Write down what cannot be measured**, explicitly, and carry it into every
report thereafter. This single habit is most of the difference between us and the
incumbent.

### How the report is created

The client receives four pages. Not a dashboard, not a deck.

```
Page 1   THE THREE NUMBERS
         platform said · your records say · the gap, decomposed

Page 2   WHAT WE CAN AND CANNOT MEASURE
         with confidence figures, and the unmeasurable named plainly

Page 3   WHAT ACTUALLY DROVE LAST QUARTER
         two or three findings, each with the evidence attached

Page 4   THE NEXT 90 DAYS
         6–8 named hypotheses, each with a test, a threshold and a kill condition
```

**Every number is computed before any prose is written.** Where software
generates a sentence, a person reads it before it leaves. No exceptions in this
phase.

Two disciplines that decide whether this reads as credible or as a sales
document: **name what we cannot measure** on page 2, and **do not use the gap to
attack their previous agency.** The gap is a property of the medium. Saying so
is what makes the rest believable.

## 4. The learning system

The actual deliverable of Phase 12. Ten customers is the *method*; this is the
output.

### The capture principle

> **Capture verbatim. Categorise weekly. Never both at once.**

Categorising at the moment of capture destroys the language, and the language is
the product. *"I'm flying blind"* and *"we lack visibility into performance"*
mean the same thing and only one of them is a sentence a customer would say out
loud. The second is what happens when a founder paraphrases into a CRM field.

Everything below lives in [`DISCOVERY-LOG.md`](DISCOVERY-LOG.md). One file, five
sections — five separate files would not survive a busy fortnight.

### What every interaction captures

| Capture | From | Why it matters |
|---|---|---|
| **Pain points** | Diagnostics 1, 4, 5, 7 | The repeatable pattern in §5 |
| **Objections** | Every sales conversation, including lost ones | What the offer has to answer |
| **Requested features** | Any call, unprompted | Only counts with *"would you pay more for it?"* attached |
| **Manual work performed** | [`EFFORT-LEDGER.md`](EFFORT-LEDGER.md) | The automation backlog, derived |
| **Client language** | Everywhere. Verbatim | Becomes the website, the outreach, the offer |
| **Renewal and churn reasons** | Monthly review, exit interview | The only question this phase is really asking |

### The rule of three

Consistent with the deficiency register: **a thing said by three different
customers stops being an anecdote.**

- Three clients name the same pain → it is the pain
- Three prospects raise the same objection → the offer is wrong, not the pitch
- Three clients request the same thing → it is a candidate capability, after the freeze
- Three clients use the same phrase → that phrase becomes our copy

One client saying something interesting is a conversation. Three is a finding.

### The weekly synthesis

Thirty minutes, Friday, non-negotiable and calendared.

Read the week's captures and answer four questions in writing:

1. What did I hear more than once this week?
2. What did I hear that contradicts what I believed last week?
3. Which manual work took longest, and is it category A, B or C?
4. What would I change about the offer if I had to sell it again on Monday?

Thirty minutes a week for twelve weeks is six hours, and it is the difference
between running ten engagements and learning from them. Skipping it under
pressure is the single most likely way this phase fails while appearing to
succeed.

### The exit interview

Every churn, without exception, within a week. Ask the questions that hurt:

1. *"When did you first think about stopping?"* — the real churn moment is
   almost always weeks before the notice
2. *"What did you expect that didn't happen?"*
3. *"What did we do that you'd want a replacement to also do?"*
4. *"What were you comparing us to?"*
5. *"What would we have had to do to keep you?"*

**A churn interview is worth more than a renewal.** Renewals tell you something
worked; churn tells you which thing did not, and the customer is finally free to
be blunt.

## 5. Success criteria

The phase succeeds only if **all four** hold. Three of four is a phase that felt
productive and answered nothing.

### 1 · Ten paying customers

Not ten trials, not ten audits. Ten paying the monthly fee, with at least one
having renewed a second month.

### 2 · A repeatable pain pattern

> **At least 6 of 10 name the same top-two problem, unprompted, in their own
> words.**

Measured from the verbatim log, not from a category count — categorising first
manufactures the agreement we are trying to detect.

**If pain scatters across ten different problems, we have found ten businesses
with ten problems, not a market.** That is a real finding and it is better to
have it in twelve weeks than in two years.

### 3 · Customers describe the value consistently

> **At least 5 of 10 give the same answer to: "what would you most hate to
> lose?"**

Asked at every monthly review, in those words, recorded verbatim.

This is the sharpest question in the phase because it separates what people
*enjoy* from what they would *pay again* for. The two are routinely different,
and the gap between them is where a product either exists or does not.

### 4 · We know which parts deserve automation

> **The top three category-B activities in the effort ledger account for ≥50% of
> automatable hours, and all three are unambiguous.**

Category A stays manual regardless of hours — it is the instrument. Category C
waits for evidence. Only B is sorted by cost, and if B has no clear head, we have
not yet done enough by hand to know what to build.

### Stop rules

Decided in advance, because the time to write them is before anyone is
emotionally invested:

| Signal | By | Response |
|---|---|---|
| Fewer than 3 audits sold | week 6 | The offer or the ICP is wrong. Stop outreach, run ten disqualification interviews, and change one variable |
| Audits selling, monthly not converting | any | **The most serious signal available.** The audit is not producing something they want more of — a finding about the product, not the sales process |
| Reconciliation failing on >3 of 10 | any | The central promise is not deliverable at this ICP. Narrow the ICP before selling further |
| Human time per client rising across clients 1→10 | week 10 | We are hiring rather than building. Stop selling and automate the head of category B |
| No pain convergence | week 12 | Do not extend the phase hoping for it. Report it, and reopen the question the charter's §1 answers |

---

## What this phase is actually for

Ten customers is not the point. Ten customers is the **cheapest available
instrument** for answering a question no amount of architecture could:

> **What do people repeatedly, verifiably pay for — and in what words do they
> describe it?**

The architecture assumed an answer. This phase finds out. If the answer matches
the assumption, `docs/00` through `docs/09` become the build plan and the freeze
lifts with evidence behind it.

If it does not, we will have discovered that for the price of ten engagements and
twelve weeks — and the documents that need rewriting will be rewritten by
customers, which was the point of freezing them.

**The goal is not to prove Phoenix can scale. It is to discover what Phoenix
should become.**
