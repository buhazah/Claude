# Phoenix — The moat

How the system is materially better at campaign 10,000 than at campaign 100,
and why a competitor who copies everything visible does not get there.

> **⛔ Frozen and almost entirely unbuilt (ADR 0010).** The gate here requires
> five supporting tenants to clear a single claim; at twenty clients it clears
> none. Everything in §7–§14 waits.
>
> **What survives the freeze is §17's recording carve-out only:** observations
> emitted into an outbox, the contribution ledger, override reason codes. Nothing
> reads them. Three days of work against a permanent loss.
>
> This document is a hypothesis about what will compound, written before anyone
> had run a campaign. `10-VALIDATION.md` is what happens instead.

---

## 1. The premise

Assume the worst case, because it is the likely case:

> Within two years a competent competitor has copied every workflow, every
> screen, every agent prompt, every department boundary, and every channel
> adapter. They read this repository. They hired someone who worked here.

Everything in `02-ARCHITECTURE.md` is copyable. The spine is seven tables and a
rule. The mandate checker is a week of work once you know it should exist. The
departments are a configuration file. Foundation models are a commodity that
improves for us and for them on the same schedule — and every capability we get
from a better base model, they get in the same release.

**Nothing in the feature set is a moat.** A blueprint that claims otherwise is
selling something.

What does not copy is a **stock of outcome-labelled judgment**, accumulated by
operating, that cannot be bought, scraped, or hired. This document designs the
machinery that produces it — and, more importantly, the measurements that prove
whether it is actually being produced, because "we learn from every campaign" is
a claim every agency in the category already makes and none of them can
substantiate.

## 2. What "better judgment" means, operationally

Vague goals produce vague architectures. Judgment decomposes into four
measurable capacities, and each gets a different mechanism:

| Capacity | The question it answers | Mechanism | Measured by |
|---|---|---|---|
| **Priors** | What should we try *first*, for a client we met on Tuesday? | Knowledge cards, scoped | Prior-lift holdout (§14) |
| **Calibration** | How sure should we be, given we have been wrong before? | Reliability curves per action type | Expected calibration error |
| **Negative knowledge** | What should we *not* do, and what will the reviewer kill? | Failure cards, override model | Internal filter precision |
| **Boundary awareness** | When does a rule stop applying? | Scope, decay class, contradiction | Card kill rate, stale-recall rate |

A system with better features answers none of these. A system with 10,000
labelled outcomes answers all four, and answers them *narrowly* — which is the
part that matters, and the part §4 is about.

## 3. The five assets that do not copy

**1. Outcome-labelled decision history.** Every proposal, its expected effect,
and what actually happened 7/14/28 days later. This is a supervised dataset
generated as a by-product of operating, in a domain where no public equivalent
exists. A competitor starting in 2028 has zero rows and cannot buy any, because
nobody else records the counterfactual alongside the action.

**2. Calibration.** Not *what works* but *how often we are right, and by how
much we are typically off*. After 10,000 decisions the system knows its own
error distribution per action type, per vertical, per spend band, per channel.
This is the deepest asset because it is **meta-knowledge**: it survives
environment change far better than object-level claims do. When the platform
changes and every prior degrades, a system that knows its priors have degraded —
because its calibration curve moved — is in a different business from one that
does not notice.

**3. The negative space.** Roughly 60–85% of creative tests lose. Nobody
publishes those. Ad libraries show what ran, case studies show what won, and the
entire public record is survivorship bias with a search interface. Phoenix's
record is the full distribution, and the losses cost the same to store as the
wins while carrying more information per row.

**4. Human override labels.** Every rejection at internal review, every client
veto, every mandate narrowed at a monthly review is a label on the one failure
mode `03-AUTONOMY.md §9` admits code cannot catch — *technically valid,
commercially stupid*. Ten thousand of those is a model of judgment that has no
public training set, and §13 is about why this loop has the clearest financial
return of any of them.

**5. The evaluation corpus, built from resolved history.** The quiet one. A
corpus of real cases with known-correct answers means a new foundation model can
be adopted in a week *with evidence*, while a competitor adopts it on vibes and
finds out in production. The ruler improves alongside the thing it measures, and
the compounding advantage is **speed of safe change**.

Note what is absent from this list: proprietary algorithms, model weights, and
data volume for its own sake. None of those is defensible here.

## 4. The compounding law

The naive claim is "more data is better." That is false in this domain, and the
reason it is false is also the reason scale genuinely wins.

**Advertising knowledge decays.** A claim about how the auction responds is worth
little in six months. A claim about which hook framing converts a category is
worth something for perhaps two quarters. A claim about offer economics lasts
years. So the archive is not the asset — a pile of 2026 claims is a liability
that gets recalled where it no longer applies.

What matters is the ratio:

```
        evidence accrual rate in a scope
  ρ  =  ───────────────────────────────────
        decay rate of knowledge in that scope
```

Below ρ = 1, a scope never accumulates enough evidence to make a confident claim
before the claim rots. Above it, the scope compounds. **Scale is what moves ρ,
and it moves it in the one dimension that matters: how *narrow* a claim you can
afford to make.**

Concretely. Suppose scope is `vertical × AOV band × audience stage` — call it 8 ×
3 × 3 = 72 cells. Creative throughput is ~40 tested variants per client per
month.

| Clients | Tests/month | Per cell/month | Time to ~200 tests in a cell | Verdict |
|---|---|---|---|---|
| 10 | 400 | ~5.5 | ~36 months | Never. The claim rots first. |
| 100 | 4,000 | ~55 | ~4 months | Inside the half-life. Compounds. |
| 500 | 20,000 | ~275 | ~3 weeks | Can split cells further and still resolve. |

At 10 clients you can only make broad claims with wide intervals — *"video
performs"* — which change no decisions because everyone already believes them.
At 500 you can make claims narrow enough to be surprising and specific enough to
be actionable, and you can *keep* making them as the environment moves.

**That is the moat, stated precisely: not the archive, but the ability to
resolve a narrow claim faster than it decays.** It is a rate advantage, it is
superlinear in clients, and a competitor with 10 clients cannot buy their way
past it because the constraint is labelled tests per scope per month, which only
operating produces.

It also sets an honest ceiling. Below roughly 50 clients this machinery is
overhead — real, but not yet earning. `06-ROADMAP.md` puts it in Phase 6 for
that reason, and §16 states what to build before then.

## 5. Two moats, and only one of them is shared

They compound differently and must not be confused.

**The client moat — vertical, per tenant, protects revenue.** Everything Phoenix
knows about *this* client: brand rules learned from 200 review decisions, offer
economics, what has been tried and failed, which angles their audience rejects,
their buyer's taste, twelve months of reconciled truth. Switching to a competitor
means restarting all of it. This is retention, and it is honest lock-in — the
client can export the lot on request, and the reason they stay is that rebuilding
the *learning*, not the data, takes a year.

**The fleet moat — horizontal, across tenants, protects quality.** Everything
Phoenix knows about advertising in general, learned from every client at once.
This is what makes client #10,000's first week better than client #100's first
week, and it is the only asset that grows with the number of clients rather than
with the age of one.

**The publication gate (§8) is the only connection between them, and it is
one-way.** Client data flows up as gated claims; claims flow down as priors. Raw
data never moves sideways, and no tenant instance can read another. Everything
in §7 exists to make that sentence mechanically true rather than a policy
promise.

## 6. The loops, by clock speed

Learning is not one process. It is seven, at different frequencies, and the fast
ones are local and cheap while the slow ones are global and valuable.

| Loop | Period | Learns | Scope | Crosses tenants? |
|---|---|---|---|---|
| Guardrail | seconds | nothing — it *enforces* | tenant | no, by design |
| Internal creative filter | minutes | reviewer preference | tenant → fleet | as override labels |
| Diagnosis → outcome | 7–28 days | causal accuracy, calibration | tenant → fleet | as claims |
| Proposal → outcome | 7–28 days | action-type reliability | tenant → fleet | as calibration |
| Hypothesis resolution | 4–8 weeks | strategy priors | tenant → fleet | as claims |
| Corpus regeneration | continuous | the ruler itself | fleet | already anonymous |
| Cohort comparison | quarters | *whether any of this works* | fleet only | aggregate only |

Two observations that shape the architecture.

**The guardrail loop deliberately does not learn.** The mandate checker, the hard
floor, the brand validator and the compliance rules are code and stay code. A
safety boundary that adapts is a safety boundary that can be trained out of
position, and `07-RISKS.md §5` already lists shortcuts in the mandate checker as
a non-negotiable. Learning happens *around* the guardrails, never inside them.

**The last loop is the only one that measures whether the rest are worth their
cost.** It is in §14, and it is the section that would justify deleting all of
this if the numbers came back flat.

## 7. Architecture: observation → claim → prior → outcome

The full circuit. Tenant-side on the left of the gate, control plane on the
right.

```
  TENANT INSTANCE                    │        CONTROL PLANE
                                     │
  Outcome measured (7/14/28d)        │
        │                            │
        ▼                            │
  Observation extractor              │
    structured, controlled           │
    vocabulary, no free text         │
        │                            │
        ▼                            │
  Publication outbox  ───────────────┼──▶  PUBLICATION GATE      §8
    (append-only, tenant-owned)      │       deterministic
                                     │       k-anonymity, suppression
                                     │       vocabulary check
                                     │           │
                                     │           ▼
                                     │     Contribution ledger    §9
                                     │       who fed what
                                     │           │
                                     │           ▼
                                     │     Claim store  ◀── statistics (code)
                                     │       cards: scope, effect,
                                     │       CI, decay class, as_of
                                     │           │
                                     │           ▼
                                     │     Calibration service    §12
                                     │       reliability per
                                     │       (action, vertical, band)
                                     │           │
  Prior applier  ◀───────────────────┼───────────┘
    retrieval by scope match         │      priors flow down
        │                            │
        ▼                            │
  Brief / proposal / filter          │
        │                            │
        ▼                            │
  Campaign runs → Outcome ───────────┘   loop closes
```

**Direction matters.** The control plane **pulls** from a tenant outbox; no
control-plane service holds a credential to a tenant database, and no tenant can
reach another. The blast radius of a fully compromised control plane is the set
of outboxes — which contain only observations already shaped for publication.
That is a much better property than "we filter on the way out."

**Every arrow is logged.** In particular, *which cards were applied to which
brief* is persisted, because §14's utilisation metric is impossible otherwise
and unmeasured learning is indistinguishable from a folder of insights.

### The observation schema

The crux of the whole design, because this is where confidentiality is either
mechanical or a judgment call:

```
Observation
  kind          creative_test | proposal_outcome | hypothesis_resolution
                | reviewer_verdict | drift_event
  scope         vertical, aov_band, spend_band, channel, audience_stage,
                geo_band, seasonality_bucket      ← all from a fixed vocabulary
  features      controlled-vocabulary tags only   ← never free text, never copy
  treatment     the one variable that changed
  control       what it was compared against
  effect        delta, confidence interval, n
  measurement   reconciliation confidence at the time
  as_of         when it was true
  contribution  opaque id — resolvable to a tenant only inside the ledger
```

**Features come from a controlled vocabulary, and that is the entire anonymity
mechanism.** Free text is where identity leaks — a product name, a founder's
phrasing, a niche claim that identifies the brand to anyone in the category. A
fixed vocabulary makes leakage structurally impossible rather than
prompt-dependent, and it is checkable by a test.

**The vocabulary is itself accumulated intelligence.** At 100 campaigns you do
not know which features of an ad are worth recording. At 10,000 you do, because
you have seen which tags ever correlate with anything. The taxonomy sharpens over
time, is versioned, and observations record which version tagged them — so a
vocabulary revision does not silently invalidate history. A competitor copying
the schema copies an empty vocabulary, which is a form the answers do not come
in.

## 8. The publication gate

**The second safety boundary in Phoenix, and it gets the same treatment as the
first.** Like the mandate checker: deterministic, pure, synchronous, one place,
exhaustively tested, and never a prompt. A model may *propose* an observation. A
model never decides what crosses a tenant boundary.

An observation is publishable only if **all** of these hold:

```
k-anonymity      ≥ 5 distinct tenants support the claim's scope
independence     ≥ 3 independent tests, not 3 measurements of one test
vocabulary       every feature and scope value is in the versioned vocabulary
no verbatim      no copy, no image hash, no URL, no product or brand token
no rare scope    every scope value has ≥ 5 tenants in the fleet, else it
                 generalises upward (a vertical with 2 clients becomes its parent)
measurement      reconciliation confidence ≥ 0.8 at observation time
consent          the contributing tenant's contract permits publication, now
```

Failures do not raise errors. They **generalise or suppress**: a claim too narrow
to be anonymous is retried at the parent scope, and if it fails there it is
retained tenant-locally, where it still serves the client moat. Nothing is lost;
it just does not travel.

**Why k-anonymity and suppression rather than formal differential privacy.**
Honest answer: DP with a meaningful ε destroys signal at our n. Our claims are
already aggregates over ≥5 tenants and ≥3 tests, effects are reported in buckets
rather than as point estimates, and the adversary model — a competitor reading a
published card — is far weaker than the one DP is designed for. **Revisit at 500+
tenants**, where cell sizes make DP affordable; the trigger belongs in the debt
table, not in a footnote. Federated learning is the same answer: real, heavy, and
not yet earning its complexity.

**What this costs, stated plainly.** The first ~50 clients contribute far more
than they receive, because k=5 blocks most claims until the fleet is wide. That
is not a bug to engineer around; it is the shape of the asset, and it is why §16
puts the machinery late and the *plumbing* early.

## 9. The contribution ledger, and unlearning

A client leaves and says *"stop using anything you learned from us."* Most
systems cannot honour that, and say so quietly in a terms-of-service clause.

Phoenix can, because of one decision: **cards are derived, never authored.**

The contribution ledger is append-only and records which observations fed which
card version. A card is a *function* of its contributions plus a versioned
statistical routine, so revoking a tenant means marking their contributions
withdrawn and recomputing every card that touched them. Cards whose support drops
below k are suppressed automatically. The whole operation is a batch job with a
deterministic result, testable by asserting that a recomputed fleet is bit-identical
to one built without the tenant from the start.

This is the strongest argument for §15's rejection of fine-tuning, and it is
worth being explicit: **learning that lives in weights cannot be unlearned.** A
fine-tuned model that saw a departing client's data is permanently contaminated,
the only honest remedy is retraining from scratch, and no amount of contractual
language makes that not true. Learning that lives in data can be recomputed on a
Tuesday. See ADR 0008.

It also makes the commercial promise cleanly sayable, which matters more than it
sounds when selling to a brand's counsel: *"your data improves the system while
you are a client, and leaves with you."*

## 10. Decay, contradiction, and scope splitting

### Decay is a property of the claim, not a cleanup job

Every card carries a **decay class**, assigned deterministically by kind:

| Class | Half-life | Examples | Stored? |
|---|---|---|---|
| **Structural** | ~3 years | Offer economics, price-anchoring, guarantee framing, review-density effects | yes, high value |
| **Behavioural** | ~2 quarters | Which hook framings convert a category, format preferences by audience stage | yes, the bulk |
| **Platform-mechanical** | ~6 weeks | How the auction responds to a budget step, delivery quirks | **no — this is a signal detector's threshold, not knowledge** |

Confidence decays with age automatically and arithmetically. A card that is not
re-confirmed falls below the retrieval threshold and stops being recalled — it is
not deleted, because a card that comes back to life when the environment cycles
is evidence too, and seasonality does exactly that.

Re-confirmation is free: every new observation whose scope matches an existing
card re-scores it. The fleet's ordinary operation is also its maintenance, which
is the only maintenance regime that survives contact with a busy quarter.

**Refusing to store platform-mechanical claims is a deliberate and unpopular
choice.** It is the most seductive category — it feels like the secret sauce —
and it is exactly what Meta changes without telling anyone. Encoding it as
knowledge produces a system confidently applying 2026's auction folklore in 2028.
Where it matters it belongs in a threshold that is re-derived from recent data,
not in a card that is recalled from memory.

### Contradiction is a finding, not an error

Two cards disagreeing almost always means **one of them has the wrong scope**.
The resolver's default action is therefore to **split the scope** and re-test
both halves rather than to pick a winner.

```
card A:  hook framing "question" beats control        apparel, £20–60 AOV, n=180
card B:  hook framing "question" loses to control     apparel, £20–60 AOV, n=140
         ↓ contradiction detected
         ↓ candidate splits proposed by feature analysis
resolve: audience_stage — question hooks win on cold, lose on retargeting
         → two cards, both narrower, both more useful than either original
```

**This is the mechanism by which the taxonomy gets finer over time, and it is
driven by data rather than by someone's theory of advertising.** It is also
superlinear in fleet size for the reason in §4: splitting a scope halves the
evidence per cell, so only a large fleet can afford to split and still resolve.
At 10 clients every contradiction is unresolvable and the honest response is to
widen the card and lower its confidence.

**Card kill rate is a health metric, not a failure metric.** A fleet that never
contradicts itself is not learning; it is confirming.

## 11. What the client moat accumulates

Distinct from the fleet, never published, and the reason retention holds.

| Asset | Built from | Why it does not transfer |
|---|---|---|
| Brand rule set | ~200 review decisions, learned then frozen as a deterministic validator | It is *their* taste, encoded |
| Offer economics | Margins, LTV, returns, seasonality, reconciled monthly | Requires their store data |
| Tried-and-failed register | Every hypothesis with a kill condition that fired | The most valuable and least glamorous artefact in the system |
| Audience rejection map | Angles their buyers demonstrably ignore | Negative, specific, expensive to rediscover |
| Reviewer taste model | Their approvals and vetoes | Personal to their team |
| Reconciled history | 12+ months of truth, not platform-reported | Cannot be reconstructed after the fact |

The tried-and-failed register deserves the emphasis. A new agency pitching this
client will propose things Phoenix tested and killed in month four, and will
propose them confidently, because losing tests are invisible from outside. That
is the client moat doing its job — and it is why the register is a *product
surface* in the monthly review, not an internal table.

## 12. Calibration

The asset in §3 that most people skip, and the one that ages best.

For each `(action_type, vertical, spend_band, channel)` the system maintains a
reliability curve: when Phoenix says it is 80% confident, how often is it right?
Built from the resolved outcomes the spine already produces — no new data
collection, only arithmetic over rows that exist.

```
budget_shift  ·  apparel  ·  £10–30k  ·  meta
  stated 0.9  →  observed 0.86   (n=340)   slight overconfidence
  stated 0.7  →  observed 0.71   (n=910)   well calibrated
  stated 0.5  →  observed 0.38   (n=420)   ← systematically overconfident when unsure
```

Three things this buys that nothing else does:

**Confidence becomes an honest number.** A stated 0.7 that means 0.71 is usable
in a decision rule. A stated 0.7 that means 0.4 makes every downstream threshold
— tier promotion, escalation, mandate widening — quietly wrong.

**It gates autonomy correctly.** `03-AUTONOMY.md`'s tier entry criteria are
stated in accuracy. Calibration is what makes "≥80% correct" mean the same thing
in year three as in year one, and it is what catches the failure where accuracy
holds but confidence has drifted.

**It survives the environment moving, which priors do not.** When a platform
change degrades every object-level card at once, calibration curves move first
and visibly. A fleet-wide calibration break is the earliest available signal that
the world has changed — earlier than any individual client's performance, because
it aggregates. Wiring that to an alert is the highest-leverage thing in this
document.

## 13. The override model, and the cost line it attacks

The loop with the clearest financial return, and the one that answers an open
problem the blueprint previously left standing.

`03-AUTONOMY.md §9` ends with an admission: *a proposal can be inside every limit
and still commercially stupid, and code cannot catch it.* True at campaign 100.
Less true at campaign 10,000, for a specific reason: **every human override is a
label on exactly that class.**

Three override streams, and they are not interchangeable:

| Stream | Signal | Scope | Publishable? |
|---|---|---|---|
| **Operator** rejects at internal review | House standard | Fleet | **Yes** — same reviewers across clients, so it generalises cleanly |
| **Client** vetoes a variant | Their taste | Tenant | No — feeds brand rules |
| **Client** declines a recommendation | Commercial judgment we lacked | Both — reason code publishes, content does not | Partially |

The operator stream is the cleanest learning signal in the entire system,
because we control both sides of it and the same small set of reviewers judges
every client. It trains the internal filter in `04-DEPARTMENTS.md`, and the
filter's job is throughput of human attention:

```
campaign 100     200 candidates → filter → 20 reviewed → 8 shipped
campaign 10,000  200 candidates → filter →  5 reviewed → 8 shipped
```

Same output, a quarter of the review time. That lands directly on the line
`07-RISKS.md §3` identifies as the one that decides the business — human minutes
per client per week — and it is the mechanism by which that number stays **flat
as accounts get larger**, which R6 names as the actual kill criterion.

**The safeguard, because this one is genuinely dangerous.** A filter trained on
reviewer rejections converges on what reviewers like, which is not what buyers
buy. Left alone it produces a confident house style and a falling win rate. Two
deterministic counterweights:

- **A mandatory exploration quota.** A fixed share of shipped variants — 15% —
  bypasses the filter entirely. Non-negotiable, and it is what keeps the training
  distribution from collapsing onto the filter's own output.
- **The filter is scored against live outcomes, not against reviewer agreement.**
  A filter that agrees with reviewers 95% of the time and kills eventual winners
  is a failure and must be measurable as one.

Predicting the client-decline stream is more valuable still and much harder,
because the reasons are commercial and often unstated. The design keeps it
modest: capture a **reason code** at decline time, publish the code and the
proposal's features, never the client's words. Even a coarse "this class of
proposal gets declined 40% of the time in this vertical" changes what gets
proposed.

## 14. Proving it exists

Everything above is a hypothesis until measured. Every agency claims to learn.
The difference is a number, and these are the numbers.

### The prior-lift holdout — a holdout on the moat itself

The strongest experiment in this document, and it is nearly free.

For each new client, in the first creative cycle, run **two brief sets**: one
with fleet priors retrieved and applied, one **cold** — identical pipeline,
identical models, no cards. Ship both. Compare.

```
arms       primed (cards applied)  vs  cold (no cards)
n          ≥ 20 variants per arm, per client
metric     win rate against control, and CPA of the top quartile
duration   the first cycle, then every fourth cycle thereafter
cost       zero incremental — these are variants we were shipping anyway
```

The result is the moat's value in a percentage. If primed briefs do not beat cold
briefs, **the fleet moat does not exist yet**, and the honest response is to say
so and stop spending on the machinery rather than to write it up as an
investment. Re-running it every fourth cycle turns it into a permanent control,
so the answer tracks whether the moat is still real rather than whether it was
real once.

I would rather have this one experiment than the rest of the metrics combined.

### Cohort curves — the headline

Clients grouped by onboarding quarter, compared at equal tenure:

| Measure | Q1 cohort | Q5 cohort | What it means if flat |
|---|---|---|---|
| Time to first winning variant | | | Priors are not transferring |
| Week-4 CAC vs their own baseline | | | The system is not starting smarter |
| Creative win rate, first 30 days | | | §4's engine is not turning |
| Human minutes/week at day 60 | | | The override model is not working |
| Proposals auto-approved at day 90 | | | Calibration is not improving |

**Cohort curves are the only honest headline metric**, because aggregate win rate
improves when good clients are retained and says nothing about learning. Equal
tenure, different cohorts, or it is not evidence.

### The supporting instruments

| Metric | Reads on | Target direction |
|---|---|---|
| Card utilisation | fraction of cards that ever change a brief | ↑ — an unused card is noise |
| Card kill rate | contradicted or decayed per quarter | **non-zero** — zero means we are confirming, not learning |
| Scope resolution | mean cells per claim family | ↑ — narrower claims are the §4 payoff |
| Expected calibration error | per action type | ↓ |
| Filter precision @ reviewer | and win rate of filtered-out variants | ↑ / ↓ respectively |
| Time-to-safe-adoption | days from model release to baselined deploy | ↓ — §3's fifth asset, made visible |
| Publication yield | observations that clear the gate | ↑ with fleet size, by construction |

Two of these are deliberately counterintuitive. **Card kill rate should never be
zero** — a knowledge base that only grows is a knowledge base nobody is checking
against reality. And **publication yield rising is mostly a fleet-size effect**,
not a quality improvement, so it is a diagnostic rather than a goal.

## 15. What is deliberately not the moat

Stated because the alternatives are tempting and mostly wrong.

**Fine-tuning on client data.** Rejected on four grounds, any one sufficient:
unlearning is impossible (§9); it invites the leakage argument we have otherwise
engineered away; base models improve faster than a fine-tune would; and it
converts an auditable asset into an opaque one, which forfeits the explainability
that `01-PRD.md §10` sells. ADR 0008.

**A creative asset library.** Winning ads are the client's IP, and a library of
them is a confidentiality incident with a search box. Lineage and structured
features carry the transferable part.

**Proprietary metrics.** "Phoenix Score" is marketing. Blended CAC from store
data, computed correctly, is worth more and is checkable by the client.

**Volume of data.** Ten million rows of unlabelled platform metrics is a storage
bill. The asset is labelled outcomes in resolvable scopes — see §4.

**The prompts.** They leak, they are copyable in an afternoon, and the audit in
Phase 11 showed that measurable prompt quality comes from the evaluation harness
around them, not from the wording.

**Exclusive data partnerships.** Available to whoever pays more next year.

## 16. Threats to the moat

| Threat | Assessment |
|---|---|
| Competitor acquires an agency with 10 years of history | They get campaigns, not **labels**. No counterfactuals, no calibration, no controlled vocabulary, no reconciliation. It is an archive, not a dataset — and this is the most likely attack. |
| Foundation models arrive with better ad priors than ours | **The real one.** If a 2029 base model has stronger priors than 10,000 campaigns of ours, the priors moat is gone. What survives: measurement against the client's own revenue, calibration of *this* system, governance, and the client moat. Those are not in anyone's pretraining set. The plan is not to bet the company on the priors layer. |
| Platform ships benchmarks | Helps everyone equally, and touches nothing client-specific. |
| Key people leave | Cards are the company's and are derived, not authored. A departing person takes intuition; the register stays. |
| We fool ourselves | The most probable failure by a distance. §14's prior-lift holdout is the specific defence, and its value is that it can return "no." |
| Regulation restricts cross-client learning | The gate is already conservative — aggregated, anonymised, consented, revocable. Tightening k or dropping to structural-only claims degrades the fleet moat without touching the client moat. |

## 17. Where this lands

The machinery is Phase 6 in `06-ROADMAP.md`, and that is correct — below ~50
clients it is overhead. But three pieces must be built **early**, because they
are cheap now and unrecoverable later:

**In Phase 1, with the spine:** the controlled vocabulary and the observation
extractor. Observations must be emitted from day one even though nothing consumes
them, because an outcome not recorded in a resolvable shape is gone. The first
two years of history are the seed corpus, and there is no retroactive way to
create them.

**In Phase 3, with the decision loop:** the contribution ledger and the outbox.
Retrofitting provenance onto a knowledge base is the same class of refactor as
retrofitting the channel abstraction — it touches everything and arrives after
the data does.

**In Phase 4, with the first human review at volume:** override capture with
reason codes. It costs a dropdown and it is the input to §13.

Everything else — the gate, the claim store, calibration curves, contradiction
resolution, prior application — waits for Phase 6, by which point the seed corpus
exists and k=5 is achievable.

**The order is deliberate: build the plumbing before the fleet is large enough to
fill it, and build the intelligence only when it is.** The cost of the plumbing
is a few weeks. The cost of not having it is two years of history that was never
recorded in a shape anything can learn from — which is the same mistake as
Meta-shaped rows in ADR 0006, made in a different dimension.
