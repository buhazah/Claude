# Phoenix — Evaluation

How we know it works, and the reasons that is harder here than in Jarvis.

---

## 1. The problem Jarvis did not have

Jarvis's corpus scores prompts against a fixed set of cases with known-good
answers. Phoenix cannot work that way, for three reasons:

**There is no ground truth.** Nobody knows what the best ad was. You know what
happened, not what would have happened otherwise.

**The environment moves.** A creative angle that won in March loses in June.
Meta changes the algorithm. Competitors enter. A regression in the score may be
the world changing rather than the system getting worse — and telling those
apart is the entire problem.

**Feedback is slow and expensive.** A creative test costs real money and takes
a week. You cannot run two hundred of them in CI.

So Phoenix needs four evaluation layers, each answering a different question at
a different cost.

## 2. The four layers

| Layer | Question | Cost | Cadence |
|---|---|---|---|
| **Unit** | Is the deterministic logic correct? | free | every commit |
| **Corpus** | Do the AI components behave? | cents | every commit / nightly |
| **Shadow** | Would the decisions have been right? | free | continuous, per client |
| **Live** | Did it actually work? | real money | per campaign |

Only the fourth measures the business. The first three exist so the fourth is
rarely a surprise.

## 3. Layer 1 — unit

Everything in `02-ARCHITECTURE.md §5` marked *no AI* is ordinary software with
ordinary tests. It is also the majority of what can hurt a client.

Non-negotiable coverage:

- **Mandate checks.** Exhaustive. Every limit, boundary, off-by-one, clamp,
  expiry, revocation mid-flight. This is the code between a hallucination and
  someone's money.
- **Money arithmetic.** Currency, rounding, VAT, margin, blended CAC. Decimals
  not floats, with a test that would fail on floats.
- **Idempotency.** Every external write replayed twice must produce one effect.
- **Reconciliation.** Including the awkward ones: refunds, partial refunds,
  currency changes mid-period, Meta restating history inside the attribution
  window.
- **Drift detection.** Human edits in Ads Manager, Meta auto-pauses,
  externally deleted entities.

**Target: 100% branch coverage on the mandate checker.** Not aspirational.

## 4. Layer 2 — the corpus

Direct reuse of Phase 11's harness (ADR 0015), with the same discipline: a
check answers yes, no, or **not applicable**; skipped checks carry no weight;
confidence weights the score; fatal is counted separately; and a run is
compared against a committed baseline rather than reported in isolation.

New suites, roughly:

| Suite | ~n | Checks |
|---|---|---|
| `diagnosis` | 60 | Given a fixed metric snapshot, is the diagnosis right? Answers are known because the cases are historical with hindsight. |
| `proposal` | 60 | Does the proposal follow from the diagnosis? Is it typed, bounded, and does the magnitude have a stated reason? |
| `brief` | 40 | Does the brief test one variable? Name a hypothesis? Carry a kill condition? |
| `copy` | 60 | Brand rules, banned claims, format constraints, variant distinctness |
| `compliance` | 80 | **Recall** on known-violating ads. Precision second. |
| `research` | 40 | Citation validity — does the cited source say what the brief claims? |
| `report` | 40 | Does every number in the prose match the number it was passed? |
| `client_comms` | 30 | Does the answer trace to the ledger? Does it avoid promising? |

Two of these are load-bearing in a way the others are not:

**`report` is deterministic and mandatory.** The model is handed numbers and
writes prose. Any figure in the prose that is not a figure it was passed is a
hard failure. This catches the whole class of "the model rounded 34.2% to 'over
a third'" and the worse class of the model inventing a number that sounds
right.

**`compliance` is scored on recall.** A false positive delays an ad. A false
negative can end an ad account. The corpus is weighted accordingly and the
threshold is asymmetric.

**Building the corpus:** the honest way is from history. Every diagnosis,
proposal and outcome Phoenix produces becomes a candidate case once the outcome
is known. The corpus grows by operating, which is the same property that makes
shadow mode work — and it means the ruler improves alongside the thing it
measures.

## 5. Layer 3 — shadow

Described in `03-AUTONOMY.md §5`. As evaluation, its properties are unusual and
good:

- **Free.** No money moves.
- **Real.** Real accounts, real fatigue, real seasonality.
- **Labelled by time.** The outcome arrives whether or not anyone looks.
- **Continuous.** Never switched off; live actions run alongside shadow
  proposals as a permanent control.

The metric:

```
proposal accuracy   = correct verdicts ÷ scored proposals
counterfactual lift = what the shadow set implies vs what happened
```

Both are reported per action type, because "80% accurate overall" hides
"budget shifts 95%, pausing 45%" — and those need different tiers.

**The honest limitation:** a shadow proposal that was never executed has a
counterfactual outcome, and counterfactuals are estimates. When Phoenix says a
pause would have improved CPA, it is inferring from what the ad set did while
running. That is directionally useful and not proof. Where the stakes justify
it, resolve with a real holdout (§6). Where they do not, state the estimate as
an estimate.

## 6. Layer 4 — live, and the hardest problem in the document

**In-platform ROAS is not a measurement.** Post-ATT it is a modelled estimate
with a view-through window, and it systematically flatters. An agency reporting
7× while the client's bank account disagrees is the industry's normal failure,
and it is the thing `01-PRD.md §4` says customers complain about first.

Phoenix's answer is three-tiered, by what the account's volume can support.

**Tier 1 — reconciliation (always).** Platform-reported conversions against
store-recorded orders for the same period. Produces blended CAC from the
store's numbers and a reconciliation confidence. Deterministic, cheap, and
already better than most agencies deliver.

**Tier 2 — holdout (where volume allows).** A geographic or audience holdout
receiving no ads. The difference is incrementality. Requires enough volume for
power; below roughly 100 conversions a month it will not resolve, and the
honest thing is to say so rather than report a number with no statistical
basis.

**Tier 3 — creative A/B (routinely).** Within-platform, same audience, same
budget, one variable. This is what the creative engine runs continuously, and
it is how §7's central question gets answered.

**What is deliberately not built:** multi-touch attribution modelling.
Expensive, contested, and answers a worse version of the question a holdout
answers directly.

**The rule:** every number reported to a client carries how it was measured and
its confidence. *"Blended CAC £34 (store-reconciled, confidence 0.94)"* and
*"iROAS 2.1× ±0.6 (geo holdout, 14 days, n=~430)"*. A number without a method
is a number that will eventually be wrong in front of the customer.

## 7. The question everything depends on

> **Does AI-generated creative perform at or above human-produced creative?**

Phoenix is a reporting tool with a large bill if the answer is no. It is
tested in Phase 2 (`06-ROADMAP.md`), not assumed:

```
design      same offer, same audience, same budget, same period
arms        AI-generated variants  vs  human control set
n           ≥20 variants per arm, ≥30 conversions per arm
metric      cost per purchase, and win rate against control
duration    3 weeks
cost        ~£3–5k of real spend
```

Three outcomes, three responses:

- **AI wins or ties** → the wedge in `00-STRATEGY.md` is real; build the company
- **AI loses on quality, wins on volume** → the likeliest outcome. Reposition to
  volume-plus-human-finishing, which changes the cost model and the price
- **AI loses on both** → Phoenix is a measurement and operations product.
  Smaller business, still a real one. Better to know in week three.

## 8. What Phoenix measures about itself

| Metric | Why | Target |
|---|---|---|
| Mandate breaches | The safety invariant | **0** |
| Reported-figure errors | The trust invariant | **0** |
| Policy strikes | The existential one | **0** |
| Proposal accuracy | Whether autonomy is earned | >80% per action type |
| Creative win rate | Whether §7 is true | >15% |
| Human minutes/client/week | Whether it scales | <60 by Phase 5 |
| AI cost/client/month | Whether it is software | <£250 |
| Reconciliation confidence | Whether anything downstream means anything | >0.9 |

The first three are zero-tolerance. They are not averaged, not trended, and not
traded off against anything.

## 9. Where evaluation cannot reach

Stated plainly, because a framework that claims to cover everything is one
nobody checks:

- **Commercially stupid but technically valid proposals.** Inside every limit,
  correct by every rule, and wrong. Only a human catches these, which is why
  tier 3 autonomy still reports weekly.
- **Brand damage.** No corpus scores "this ad made the brand look cheap."
- **Client relationship health.** Retention is a lagging indicator by months.
- **Whether the strategy was right.** Even a resolved hypothesis only tells you
  about the version tested.
- **Long-horizon effects.** Aggressive prospecting can win on CAC this quarter
  and cost LTV next year. Nothing in this framework sees that.

The framework's job is to make the *measurable* failures rare enough that human
attention is available for the ones that are not.
