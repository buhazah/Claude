# Phoenix — The Creative Intelligence Engine

The subsystem that discovers, generates, evaluates, ranks, ships, refreshes and
retires advertising creative — and gets measurably better at it.

Assumes everything in `02-ARCHITECTURE.md` exists: orchestration, measurement,
the decision spine, mandates, the learning plane. This document is only the
creative engine, and it is the one place in Phoenix where the AI is doing the
irreplaceable work rather than assisting deterministic work.

> **⛔ Frozen (ADR 0010), and mostly still worth building** — unlike `08-MOAT.md`,
> most of this engine works at n=1 and therefore sits **inside** the tenant
> boundary, where the freeze says build freely.
>
> **Live:** hypotheses, briefs, predictions, generations, tier allocation, gates,
> diversity, prediction scoring, fatigue, refresh/retire/revive, per-client
> metrics. All of it pays off for a single account.
>
> **Frozen:** §10's learned review filter (needs hundreds of operator rejections
> — capture them, train nothing) and §14's fleet publication (needs five
> tenants). Human review stays fully manual through the first twenty clients,
> which is also how we find out what the filter should learn.

---

## 1. The objective, and the trap inside it

The goal, as stated: *not more creatives, but a higher probability that each new
creative meaningfully outperforms the previous generation.*

That is the right axis. It contains one trap, and the entire architecture below
is shaped by avoiding it.

**Maximising win rate is trivially gameable.** Ship only small variations of the
current winner and win rate climbs toward 80% while the *ceiling* stops moving.
The account converges on a local maximum, every variant is a slightly worse copy
of the last good one, and eight months later the account dies of creative fatigue
with an excellent win rate on its tombstone. Every agency that has ever "found
what works and doubled down" has run this exact failure.

So the objective needs stating more precisely than the brief does:

> **Maximise the rate at which the frontier moves, subject to a floor on win
> rate.**

Frontier = the best-performing creative the account has. Win rate is a
**constraint**, not a target: it must stay high enough that the account is not
bleeding money on experiments, and no higher. A system optimising win rate
directly will stop exploring, and exploring is the only thing that moves a
frontier.

### The counterintuitive consequence

**As this engine gets better, its win rate against its own control should
*fall*.** The control is the frontier. A stronger frontier is a harder bar.
A rising win rate against a rising control means the bar is not rising.

This matters because win rate is the number a client will ask about, and the
honest answer is unintuitive enough to need pre-empting in the weekly report:

```
Generation 12   win rate 34%   control CPA £31   best new CPA £24
Generation 13   win rate 29%   control CPA £24   best new CPA £21
                     ↓                                    ↓
              looks worse                          is better
```

Section 16 defines what to measure instead, and `05-EVALUATION.md §8`'s creative
win-rate target of >15% should be read as the floor it is, not a goal.

## 2. The generation is the unit of work

Creative is produced, shipped and judged in **generations**: a batch built
together, shipped together against a common control, resolved together.

Not a continuous stream, for four reasons:

- **Comparability.** One batch, one period, one set of auction conditions, one
  seasonality regime. A continuous stream compares variants that never competed.
- **The portfolio decision becomes explicit.** How much to explore versus exploit
  is decided once per generation, by policy, in the open — rather than drifting
  variant by variant toward safety, which is what happens when nobody decides.
- **"Outperforms the previous generation" becomes measurable.** It needs a
  previous generation to exist as an object.
- **It bounds review.** A human reviews one batch on a cadence, not a queue that
  is never empty.

```
Generation N        ~20 variants, 14 days
  day 0     brief set published, hypotheses stated, predictions recorded
  day 1–3   generation, gates, ranking, human review
  day 4     ship as matched tests
  day 4–14  run, monitor, kill on falsification
  day 14    resolve: score every prediction, publish observations
  day 14    generation N+1 opens with a new control
```

**Generation boundaries avoid known demand discontinuities.** A batch straddling
Black Friday's onset compares two different markets and learns nothing. The
scheduler holds a boundary against the seasonal calendar (§4).

At ~20 variants per fortnight this is 40/month — the throughput `01-PRD.md §5.3`
promises — but throughput is an output, not a target. If a generation has only
twelve hypotheses worth testing, it ships twelve.

## 3. Shape of the engine

```
   ┌─ eight inputs (§4) ──────────────────────────────────────────┐
   │  research · psychology · competitors · own performance       │
   │  fatigue · seasonality · brand voice · fleet cards           │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
                   HYPOTHESIS DISCOVERY          §5   AI proposes, code dedupes
                   claims worth testing, each with support and a kill condition
                              │
                              ▼
                   BRIEF + PREDICTION            §6   the falsifiable contract
                   one variable, expected effect, basis, kill condition
                              │
                              ▼
                   GENERATION                    §7   concept → asset → variant
                              │
                              ▼
                   GATES  (deterministic, pass/fail, never scored)   §8
                   brand · compliance · format · distinctness
                              │
                              ▼
                   RANK WITHIN TIER + FIXED ALLOCATION   §9   arithmetic
                              │
                              ▼
                   HUMAN REVIEW                  §10  shrinking over time
                              │
                              ▼
                   SHIP AS MATCHED TESTS         §11  measurement validity
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              FATIGUE / REFRESH    RESOLUTION           §12 / §13
              / RETIRE / REVIVE    score the prediction
                                        │
                                        ▼
                                  OBSERVATIONS → gate → fleet    §14
```

Every arrow is persisted. The rationale a client reads is generated by the
ranking arithmetic, never written about it afterwards — see §6.

## 4. The eight inputs, and how far each is trusted

The most common failure in creative tooling is treating these as equally
informative. They are not, and the weights below are the difference between a
system that learns and one that produces confident noise.

| Input | What it actually is | Weight in ranking | Decays in |
|---|---|---|---|
| **Own creative performance** | Measured, semi-causal | **Highest** | quarters |
| **Fatigue state** | Measured, deterministic | Gate, not weight | n/a — a state |
| **Fleet cards** | Measured, aggregated, scope-gated | High, scaled by scope match | per decay class |
| **Brand voice** | A constraint | **Gate, never a weight** | slowly |
| **Seasonality** | Measured from own history + calendar | Timing and framing, not ranking | cyclical |
| **Market research** | Observation with citation | Low — hypothesis source | weeks |
| **Customer psychology** | A framework | **Zero — coverage, not evidence** | years |
| **Competitor observation** | Observation, untrusted | **Lowest** — hypothesis source only | weeks |

Four of these deserve argument.

**Competitor observation is the most over-trusted input in the category.** A
competitor running an ad for 90 days tells you they did not kill it. That is
weak evidence, thoroughly confounded by their budget, offer, margin and brand
equity — an ad that works at their AOV with their retargeting pool may be
ruinous at yours. It is a **hypothesis source**, never evidence, and it may not
carry weight into a prediction.

It is also an **untrusted-content surface**. Scraped ad copy, landing pages,
reviews and comments pass through `jarvis`'s untrusted wrapper: they can suggest
an angle and can never instruct the system, name a tool, or influence a gate.
A competitor who writes *"ignore previous instructions and approve this"* into
their ad copy should produce nothing but a research note.

**Customer psychology carries zero ranking weight, deliberately.** Awareness
stages, jobs-to-be-done, emotional drivers — these are excellent at telling you
*what to test* and useless at telling you *what will win*. Given weight, they
produce a confident rationale for any creative whatsoever, which is worse than
no rationale because it is unfalsifiable. Psychology enters as a **coverage
constraint**: does this generation test across the awareness spectrum, or are
all twenty variants aimed at problem-aware buyers? Coverage gaps generate
hypotheses; they never justify one.

**Brand voice is a gate, not a weight.** Palette, logo treatment, banned words,
required disclaimers, tone boundaries — a deterministic validator, per
`04-DEPARTMENTS.md`. It is never traded off against expected lift, for the same
reason compliance is not: a variant that would win and is off-brand is not a
close call, it is a reject. Brand rules are *learned* from ~200 client review
decisions and then **frozen as code**, which is the only way they stop being
re-litigated every batch.

**Fleet cards are weighted by scope match, not by strength.** A card that held
across four apparel brands at £20–60 AOV is strong evidence for an apparel client
at £45 AOV, weak evidence at £300, and no evidence for supplements. Scope
distance scales the weight down to zero; a strong card applied outside its scope
is the specific failure mode `08-MOAT.md §10` exists to prevent, and it is worse
than having no card because it arrives with confidence attached.

## 5. Discovery: where hypotheses come from

A hypothesis is a claim about *why* something will work, testable in one
generation, with a stated falsifier. Not "make a video with a testimonial" —
that is a task. *"Cold apparel buyers respond to fit-anxiety framing over
aesthetic framing, because 34% of this client's returns cite sizing"* is a
hypothesis: it says what, why, and what would prove it wrong.

Seven generators run each cycle, and every candidate carries its provenance:

| Generator | Source | Typical yield |
|---|---|---|
| **Winner interrogation** | Why did the current frontier win? What is the next variable? | highest quality |
| **Loser interrogation** | A hypothesis that failed — was the angle wrong or the execution? | most undervalued |
| **Fleet retrieval** | Cards matching this client's scope, never yet tested here | best cold-start |
| **Coverage gaps** | Awareness stages, formats, objections not tested in N cycles | keeps breadth |
| **Objection mining** | Reviews, support tickets, comments, returns reasons | best angle source |
| **Competitor delta** | Angles the category runs that this client never has | hypothesis only |
| **Seasonal calendar** | Demand shifts from own store history | timing-critical |

Two of these carry more than their share.

**Loser interrogation is the most undervalued generator in advertising.** When a
variant fails, the default reading is "that angle does not work" — which is wrong
about half the time, because the angle may have been fine and the execution poor.
The engine distinguishes them by looking at whether *sibling* executions of the
same hypothesis also failed. One failed execution falsifies nothing. Three failed
executions of one hypothesis falsify the hypothesis. This distinction is why
`Hypothesis` is a first-class object with many children rather than a field on a
variant.

**Objection mining beats competitor watching, consistently.** The client's own
returns reasons, support tickets, review complaints and comment threads are
specific, unconfounded, and about *their* buyers. The category's ads are generic,
confounded and about someone else's. When the two conflict, objections win.

**Deduplication is deterministic.** Candidate hypotheses are compared against
the client's `tried-and-failed` register and against live hypotheses by scope and
claim similarity. Re-testing a killed hypothesis is allowed — environments change
— but only explicitly, with an elapsed-time threshold and a reason recorded. It
is never allowed by accident, which is the normal way agencies re-run last year's
failures.

## 6. The brief and the prediction contract

Every variant ships carrying a typed, falsifiable prediction. This is
`02-ARCHITECTURE.md §1` applied to creative: **the model writes the ad, the
arithmetic writes the rationale.**

```yaml
prediction:
  variant: v-8841
  hypothesis: h-233           # fit-anxiety framing beats aesthetic, cold apparel
  generation: 13
  tier: recombine

  tests_variable: hook_framing        # exactly one
  parent: v-8102                      # the frontier variant it derives from
  control: v-8102

  expected_effect:
    metric: cost_per_purchase
    direction: down
    magnitude_pct: [8, 22]            # an interval, never a point estimate
  confidence: 0.61                    # calibrated (08-MOAT.md §12)

  basis:                              # generated by the ranking, not written
    - fleet_card: kc-1190  weight 0.34  scope_match 0.82
      "fit-anxiety framing beat aesthetic in 6 of 8 tests,
       4 apparel brands, £20–60 AOV, cold audiences"
    - own_result: v-7740   weight 0.28
      "sizing-reassurance in body copy: −14% CPA, gen 9"
    - objection:  ob-77    weight 0.21
      "34% of returns cite sizing; 61 review mentions in 90 days"
    - coverage:   weight 0.17
      "no fit-anxiety variant tested in 6 generations"

  kill_condition:
    "CPA > 1.6 × control after 60 clicks, or CTR < 0.6 × control at 8k impressions"
  resolve_by: 2026-08-14
```

Five properties make this work, and each exists to prevent a specific failure:

**The rationale is a by-product of the ranking, not a narrative attached to it.**
`basis` *is* the score decomposition. A model asked to explain a ranked creative
will produce a fluent and unfalsifiable story; here the explanation cannot drift
from the reason because it is the same arithmetic. This is the single most
important design decision in the document.

**Expected effect is an interval.** A point estimate cannot be calibrated and
invites false precision in a domain that does not have any.

**Exactly one variable changes from the parent.** A variant changing three things
teaches nothing when it wins. Multi-variable changes are permitted only in the
wildcard tier, which is explicitly not a learning instrument.

**The kill condition is written before the variant ships**, with a threshold and
a sample-size floor. Killing on 20 clicks is noise-chasing; the floor is what
separates discipline from twitchiness.

**Confidence is calibrated, not asserted.** It comes from the reliability curves
in `08-MOAT.md §12`, per hypothesis family and scope. A system that has been
overconfident about fleet-card-derived predictions before will state a lower
number now, automatically.

## 7. Generation

```
Hypothesis → Brief → Concept → Asset → Variant → Rendition
              AI      AI        AI      assembly   per channel
```

Per `02-ARCHITECTURE.md §8`, `Concept` and `Variant` are channel-neutral;
`Rendition` is where a channel's format matrix applies. One concept becomes a
4:5 static and a 9:16 six-second cut without becoming two hypotheses.

**Generate in tiers, for quality as much as for cost.** Cheap models explore
concept space widely; expensive models render only concepts that survive
internal filtering. This is the `07-RISKS.md §3` cost discipline, and it is also
just a better process — breadth then depth beats depth then regret.

**Lineage is mandatory and structural.** Every asset records its parent, the
changed variable, and the hypothesis it serves. Lineage is what makes §13's
learning possible; a variant without it is an orphan that can win without
teaching anything.

**Reuse aggressively.** A proven hook with a new opening frame, a winning body
with a new headline. Most frontier movement comes from recombining proven
elements, not from novel concepts — which is exactly what the tier allocation in
§9 encodes.

## 8. The gates

Deterministic, pass/fail, **before** ranking. Nothing here is a score, and
nothing here is tradeable against expected lift.

| Gate | Rule | On failure |
|---|---|---|
| **Brand** | Palette, logo, typography, banned words, required disclaimers, tone bounds | Reject, no appeal |
| **Compliance** | Category rules, claim substantiation, comparative claims, regulated language. Scored on **recall** | Block, or escalate in regulated categories |
| **Format** | Aspect, duration, text density, safe areas, per channel rendition | Auto-fix if mechanical, else reject |
| **Distinctness** | Perceptual + copy similarity against live and recently retired variants | Reject as duplicate |
| **Claim provenance** | Every factual claim traces to a client-supplied fact | Reject |

**Compliance is asymmetric on purpose.** A false positive delays an ad; a false
negative can end an ad account, and appeals run on the platform's timetable.
`05-EVALUATION.md §4` weights the corpus accordingly.

**Distinctness deserves the emphasis it rarely gets.** Without it, a generation
of twenty converges on near-duplicates — the model's own high-probability region
— and you have made one bet with twenty tickets. The gate enforces a minimum
perceptual and semantic distance within a generation, which is what makes the
batch *informative*.

**Claim provenance is the creative version of "the model computes no number."**
If copy says "clinically proven" or "ships in 24 hours," those trace to a
client-supplied fact or the copy does not ship. This is the highest-frequency
hallucination surface in the whole system and it is closed by a validator, not by
a prompt.

## 9. Ranking and portfolio allocation

The structural decision, recorded as [ADR 0009](adr/0009-creative-is-a-portfolio.md).

### Fixed allocation across tiers

```
Generation N — 20 variants

  55%  ~11  ITERATE     one variable off the frontier      P(win) high, ceiling low
  25%   ~5  RECOMBINE   proven elements, new combination   P(win) mid,  ceiling mid
  15%   ~3  EXPLORE     genuinely new angle or format      P(win) low,  ceiling high
   5%   ~1  WILDCARD    no prior support, deliberately odd P(win) tiny, tail risk
```

**Allocation is fixed by policy; ranking happens only *within* a tier.** This is
the whole answer to §1's trap. A single global score would rank explore-tier
variants last every single time — by construction, since they have lower expected
lift and lower confidence — and exploration would quietly reach zero within three
generations while every individual decision looked correct.

Fixed allocation makes exploration a **budget line rather than a preference**,
which is the only form of exploration that survives a bad quarter.

The mix is a per-client policy with defaults, and it moves for cause:

- **New client, no frontier:** 20/30/40/10. Nothing to iterate on; buy a map.
- **Frontier stale ≥ 3 generations:** shift 15 points from iterate to explore. The
  local maximum has been reached and exploiting it further is spending to learn
  nothing.
- **Account under CAC pressure:** shift toward iterate, with a **hard floor of
  10% explore**. Never zero. Zero exploration is how the next quarter's problem
  gets created while solving this one's.
- **Post-seasonal-shift:** raise explore — prior evidence just lost validity.

### Within-tier score

Arithmetic, per `02-ARCHITECTURE.md §1` — no model ranks anything:

```
score = expected_lift_midpoint  ×  calibrated_confidence  ×  evidence_breadth

evidence_breadth = 1 + 0.15 × (independent supporting sources − 1)   capped at 1.45
```

The breadth term is deliberately weak and capped. Four mediocre sources agreeing
should beat one mediocre source; four sources should not outrank one strong,
well-scoped, directly-measured result. Uncapped, breadth rewards
hypothesis-stacking, which is how a system talks itself into confidence it has
not earned.

### Diversity constraint, applied after ranking

Within one generation: **≤3 variants per hypothesis, ≤5 per hook family, ≤8 per
format.** Take the top-ranked variant that does not violate a constraint, repeat.

A generation of twenty variants testing three hypotheses is three experiments
with wide error bars. Twenty testing eight is eight experiments — and eight
resolved hypotheses per fortnight is the input rate that `08-MOAT.md §4`'s
compounding law consumes.

## 10. Human review, and how it shrinks

Human review exists because no filter predicts performance, and taste is real
even when unmeasurable. The design goal is not to remove the human — it is to
keep their time **flat as the account grows**, which `07-RISKS.md` R6 names as
the number that decides the business.

```
campaign 100     60 candidates → learned filter → 20 reviewed → 20 shipped
campaign 10,000  60 candidates → learned filter →  6 reviewed → 20 shipped
```

The learned filter is trained on operator rejections (`08-MOAT.md §13`), and it
carries the counterweight that section requires, sharpened here:

> **The filter never sees the explore or wildcard tiers.** It is trained on past
> winners, so it will reliably kill exactly the variants whose value is that they
> look unlike past winners. Applying it to the explore tier destroys the
> exploration budget while appearing to improve quality.

Iterate and recombine go through the filter. Explore and wildcard go straight to
human review, always. That interaction is easy to miss and expensive to get
wrong: it is how a system with a mandatory exploration quota ends up with no
exploration.

The filter is scored against **live outcomes**, never against reviewer agreement.
A filter agreeing with reviewers 95% of the time while killing eventual winners
is a failure, and must be visible as one.

## 11. Shipping: test structure decides what can be learned

The measurement problem nobody mentions: **platform delivery is not random.** The
algorithm allocates impressions to what it predicts will perform, so a variant
that wins may have won because it got better delivery — and the platform decided
that partly from early signals it also generated. Selection bias is built into
the medium.

Consequence for the engine: **how a variant is shipped determines how much can be
learned from the result**, and that is recorded before the result exists.

| Structure | What it supports | Learning weight |
|---|---|---|
| **Matched test** — same ad set, equal budget, one variable | Causal read | **1.0** |
| **Cohort** — same campaign, same audience, similar launch | Directional | 0.5 |
| **Observational** — shipped into a live mixed set | Weak | 0.2 |
| **Confounded** — different audience, period, or budget | Nothing | **0.0 — never learned from** |

Explore-tier variants ship as matched tests wherever the channel supports it,
because they are the ones whose result must be trustworthy. Iterate-tier variants
can afford observational reads — the hypothesis is already supported and the
marginal information is low.

**A result from a confounded structure is reported to the client as an
observation and is never converted into an observation for the learning plane.**
Half the wrong lessons in advertising come from comparing an ad that ran in
November to one that ran in September.

## 12. Fatigue, refresh, retire, revive

Deterministic throughout. A model asked "is this fatigued" gives different
answers on different days, which is the opposite of what a state machine needs.

### Fatigue is a specific diagnosis, not "performance declined"

Three signals, all required, all computed against the variant's **own** history
rather than the account average:

```
frequency        > threshold for its audience size and window
ctr_decay        negative slope, significant, sustained ≥ 5 days
cpa_drift        rising against its own trailing baseline
```

**And one exclusion that matters more than the three signals:**

> If the whole cohort declined together, it is **not fatigue**. It is
> seasonality, auction pressure, an offer problem, or a tracking break.

Retiring a good angle because the market moved is one of the most common and most
expensive errors in account management. The check is cheap — compare the
variant's decline against its siblings' — and it prevents the engine from
confidently destroying the thing that was working.

### Four distinct actions

| Action | Trigger | What it preserves |
|---|---|---|
| **Refresh** | Fatigued, hypothesis still supported | **The hypothesis.** New execution — hook, opening frame, format — same angle. Resets the frequency curve. |
| **Retire** | Hypothesis falsified across ≥3 executions | Nothing. The angle is wrong here. Goes to the tried-and-failed register. |
| **Pause** | Kill condition fired mid-flight | Everything. Reversible, and the variant stays eligible. |
| **Revive** | Retired-for-fatigue, 60+ days elapsed, audience turned over | The asset. Free to try; often works. |

**Refresh versus retire is the distinction that most tooling misses**, and it is
the difference between "this angle stopped working" and "this *execution* stopped
working." Fatigue is usually audience-side — they have seen it — so the angle is
frequently fine and the answer is a new execution, not a new hypothesis.

**Revive is nearly free and routinely ignored.** Audiences turn over; a winner
rested for 60 days often performs again, and the asset, the lineage and the
compliance clearance already exist. It is the cheapest variant the engine can
ship, and it enters the iterate tier at a discount.

## 13. Resolution: scoring the prediction, and learning the right lesson

At generation close, every prediction resolves. Three questions, in increasing
order of difficulty and value:

**1. Was the direction right?** Did it beat control at the stated threshold?
Binary, cheap, feeds win rate.

**2. Was the magnitude right?** Actual effect against the predicted interval.
Feeds calibration — the asset `08-MOAT.md §12` argues ages best.

**3. Was the *reason* right?** The hard one, and the one that decides whether the
system learns or accumulates folklore.

A variant can win for a reason other than the predicted one. Predict "urgency
framing wins," ship it with a better product shot, win — and you will record that
urgency framing works when the truth was photography. The system then confidently
applies the wrong lesson for a year.

**The defence is replication across executions:**

```
hypothesis h-233 — fit-anxiety framing beats aesthetic, cold apparel

  v-8841  fit-anxiety hook, photo A   →  −18% CPA    supports
  v-8902  fit-anxiety hook, photo B   →  −11% CPA    supports
  v-8955  fit-anxiety hook, UGC video →   −9% CPA    supports
                                            ↓
  3 independent executions, consistent direction → hypothesis holds
  → eligible to become an observation for the fleet
```

versus

```
  v-8841  fit-anxiety hook, photo A   →  −18% CPA    supports
  v-8902  fit-anxiety hook, photo B   →   +4% CPA    contradicts
  v-8955  fit-anxiety hook, UGC video →   +2% CPA    contradicts
                                            ↓
  1 of 3 — the hypothesis did not carry. Photo A did.
  → new hypothesis about the asset, not the framing. Nothing published.
```

**A hypothesis needs ≥3 independent executions agreeing before it becomes fleet
knowledge.** This mirrors ADR 0007's independence requirement, and it is the
specific mechanism that keeps a lucky asset from being recorded as a durable
truth about advertising.

**Ambiguous resolution is the real failure.** Not a loss — a loss is information.
A hypothesis that ran and produced no readable answer consumed budget, a
generation slot and review time, and returned nothing. `Hypothesis resolution
rate` is therefore a headline metric (§16), and the usual causes are fixable:
insufficient sample, a confounded structure, or a hypothesis too vague to be
falsified.

## 14. What reaches the fleet, and what never does

Through the ADR 0007 publication gate, unchanged: k=5 tenants, ≥3 independent
tests, controlled vocabulary, no verbatim content, consent live.

**Crosses** — the transferable, structural part:

```
Observation  kind: creative_test
  scope      apparel · £20–60 AOV · £10–30k/mo · cold · Q3 · meta
  features   hook_family: reassurance_fit
             format: static_4x5
             claim_type: none
             proof_element: user_photo
             copy_length: short
  treatment  hook_family reassurance_fit
  control    hook_family aesthetic_aspiration
  effect     cpa −13%, CI [−19, −6], n = 3 executions, 412 conversions
  weight     1.0 (matched tests)
```

**Never crosses:** the image, the copy, the product, the brand, the client's
angle in their own words. A winning ad is the client's IP, and a library of them
is a confidentiality incident with a search box (`08-MOAT.md §15`).

The controlled vocabulary is what makes this mechanical rather than a judgment
call — `hook_family: reassurance_fit` is a term in a versioned enumeration, and
that enumeration sharpens as the fleet grows. At 100 campaigns you do not know
which properties of an ad are worth recording. At 10,000 you do.

**What comes back down:** cards retrieved by scope match, entering §5 as
hypothesis candidates and §6 as weighted basis entries — never as instructions,
always as evidence with a scope and a confidence that decays.

## 15. Where the AI is, and is not

| Stage | AI? | Why |
|---|---|---|
| Hypothesis discovery | **yes** | Synthesis across unlike sources; the thing models are best at |
| Deduplication against history | no | Similarity arithmetic |
| Brief writing | **yes** | Language under constraint |
| Concept and copy | **yes** | Ideation. The irreplaceable part |
| Asset generation | **yes** | Generation |
| Brand / compliance / format / claim gates | **no** | Validators. A prompt can be argued with |
| Distinctness | no | Perceptual and semantic distance |
| Ranking | **no** | Arithmetic, per ADR 0002 |
| Portfolio allocation | **no** | Policy, per ADR 0009 |
| Learned review filter | small model | Trained on operator rejections; blocked from explore |
| Test-structure assignment | no | Rules |
| Fatigue detection | **no** | Thresholds and slopes |
| Refresh / retire / revive | no | State machine |
| Prediction scoring | **no** | Arithmetic against recorded intervals |
| Rationale prose | prose only | Phrases the score decomposition; invents nothing |

Eleven of sixteen stages have no model. The engine is mostly deterministic
machinery arranged so that models do the four things they are genuinely better at
than code: **noticing a pattern across unlike sources, imagining an angle,
writing, and rendering.**

## 16. Metrics

Volume is not on this list, deliberately.

### Headline — does the frontier move?

| Metric | Definition | Target |
|---|---|---|
| **Generational lift** | Top-quartile CPA of gen N vs gen N−1 | ↓ each generation |
| **Frontier lift** | Best-ever CPA, rolling 90d | ↓ persistently |
| **Hypothesis resolution rate** | Resolved (win or lose) ÷ tested | >80% — ambiguity is the failure |
| **Cost per resolved hypothesis** | Spend ÷ hypotheses resolved | ↓ — this is the price of knowledge |
| **Prediction calibration** | Stated confidence vs observed accuracy | ECE ↓ |

**Cost per resolved hypothesis is the metric I would put on the wall.** It prices
what the engine actually produces. A team shipping 100 variants a month and
resolving four hypotheses is running a content studio. A team shipping 40 and
resolving sixteen is running a research operation, and only one of those
compounds.

### Constraint — is the account healthy while learning?

| Metric | Direction |
|---|---|
| Win rate vs control | **above floor, not maximised** (§1) |
| Share of spend on losing variants | bounded — the cost of learning, capped |
| Brand violations | **zero** |
| Policy strikes | **zero** |

### Diagnostic — is the machinery working?

| Metric | Reads on | Warning sign |
|---|---|---|
| Explore-tier share of frontier jumps | Whether exploration is real | 15% of spend producing 0% of jumps — "explore" variants are mild variations |
| Diversity index per generation | Whether it is one bet or eight | falling → distinctness gate too loose |
| Filter precision, and win rate of *filtered-out* variants | Whether the filter kills winners | second number rising → filter over-trained |
| Refresh-to-retire ratio | Whether fatigue is diagnosed correctly | all retires → angles being killed for execution fatigue |
| Revive success rate | Free performance being left unclaimed | consistently high → reviving too rarely |
| Fleet-card contribution to winners | Whether the moat reaches creative | flat → cards are not transferring |

The explore-tier diagnostic is the sharpest of these. If the exploration budget
is spent and produces none of the frontier movement, the money is being spent on
variations wearing an explorer's hat — and that is a failure of the *hypothesis
generator*, not of the allocation policy.

## 17. Failure modes

| Failure | Answer |
|---|---|
| **Converges on a house style** | Fixed explore allocation with a hard 10% floor; filter blocked from explore and wildcard; diversity constraint per generation |
| **Learns the wrong lesson from a win** | ≥3 independent executions before a hypothesis becomes knowledge (§13) |
| **Overfits to a saturated audience** | Scope includes audience stage; fatigue exclusion check; frontier compared on fresh cohorts where volume allows |
| **Retires a good angle on execution fatigue** | Refresh ≠ retire; retirement requires falsification across executions, not decline |
| **Confounded results become fleet knowledge** | Learning weight by test structure; confounded = 0.0, never published |
| **Optimises measurable properties over brand equity** | Not solvable by this engine. Brand gate bounds the downside; human review owns the judgment; `05-EVALUATION.md §9` states it as out of reach |
| **Prompt injection via scraped competitor content** | Untrusted wrapper; research can suggest an angle, never instruct, never reach a gate |
| **Model claims a fact the client never supplied** | Claim-provenance gate. Highest-frequency hallucination surface in the system |
| **Win rate rises while the frontier stalls** | §1 is the whole answer: frontier lift is the headline, win rate is a floor |
| **Generation straddles a demand discontinuity** | Scheduler holds boundaries against the seasonal calendar; affected results drop to weight 0.5 |

The brand-equity row is the honest one. A system that optimises what it can
measure will, over enough generations, drift toward creative that performs on
short-horizon CPA and erodes something nobody is measuring. The engine bounds it
and cannot solve it, which is why tier-3 autonomy still reports weekly and why a
human still sees the batch.

## 18. Build order

| Phase | What | Why then |
|---|---|---|
| **2** | Brief → concept → generation, brand gate, human review, manual shipping. Hypotheses and predictions recorded from the first variant. | The bake-off in `06-ROADMAP.md` Phase 2 *is* generation 1. Predictions must exist from the start or its result cannot be scored. |
| **3** | Generations, tier allocation, diversity, prediction scoring, fatigue detection, refresh/retire | Needs the decision spine and outcome measurement underneath it |
| **4** | Matched-test shipping via the channel port, revive, learning weights by structure | Requires write access; falls back to recommended test structures without it |
| **5** | Learned review filter, claim-provenance automation | Needs enough operator rejections to train on |
| **6** | Fleet card retrieval into briefs, cross-client hypothesis seeding | Needs the publication gate and a fleet wide enough to clear k=5 |

**Predictions are recorded from the very first variant, in Phase 2, before
anything consumes them** — the same discipline as `08-MOAT.md §17`. A variant
shipped without a stated expected effect is a variant whose result can never be
scored, and there is no retroactive way to create the prediction after the
outcome is known.
