# 9. Creative is a portfolio with fixed allocation, not a ranked queue

Status: proposed

## Context

The creative engine must decide which variants to ship each cycle. The obvious
design is a single score — expected lift × confidence — and ship the top N.

That design fails in a way that is invisible while it happens.

Exploratory variants have lower expected lift and lower confidence **by
definition**: they test angles with little or no prior support. A global ranking
therefore places them last, every cycle, correctly by its own arithmetic. Within
three generations exploration reaches zero, and every individual decision along
the way was defensible.

What follows is a rising win rate and a stationary frontier. The account
converges on a local maximum, each variant a slightly safer copy of the last good
one, until it dies of creative fatigue with an excellent win rate. This is the
same failure as an agency "finding what works and doubling down," reached by
arithmetic instead of by habit — which makes it harder to notice and easier to
defend.

The objective in `09-CREATIVE.md §1` is not win rate. It is the rate at which the
frontier moves, subject to a floor on win rate.

## Decision

**Allocation across tiers is fixed by policy. Ranking happens only within a
tier.**

```
55%  ITERATE     one variable off the frontier        P(win) high, ceiling low
25%  RECOMBINE   proven elements, new combination     P(win) mid,  ceiling mid
15%  EXPLORE     genuinely new angle or format        P(win) low,  ceiling high
 5%  WILDCARD    no prior support                     P(win) tiny, tail
```

Exploration becomes a **budget line rather than a preference**, which is the only
form of exploration that survives a quarter under CAC pressure.

Three rules make the allocation real rather than nominal:

**A hard floor of 10% explore, under all conditions.** The mix moves for cause —
a new client with no frontier explores far more; a stale frontier shifts fifteen
points from iterate to explore; an account under CAC pressure shifts toward
iterate — but never to zero. Zero exploration is how next quarter's problem is
created while solving this quarter's.

**The learned review filter never sees the explore or wildcard tiers.** The
filter is trained on operator rejections of past work, so it reliably kills
exactly the variants whose value is that they look unlike past winners. Applying
it to explore destroys the exploration budget while appearing to raise quality.
Iterate and recombine pass through it; explore and wildcard go straight to human
review.

**Diversity constraints apply after ranking.** ≤3 variants per hypothesis, ≤5 per
hook family, ≤8 per format, within one generation. Twenty variants testing three
hypotheses is three experiments with wide error bars; twenty testing eight is
eight experiments.

## Alternatives rejected

**A single global score with a novelty bonus.** The tempting fix: add a term that
rewards distance from the frontier. It fails because the bonus must be tuned, the
tuning is unfalsifiable, and any value that actually protects exploration is
large enough to promote bad variants for being weird. A quantity is being traded
that should not be traded.

**Multi-armed bandit allocation.** Formally the right family of answer, and it
assumes stationary arms and fast feedback. Creative arms are non-stationary
(fatigue), feedback takes 7–14 days, arms are created rather than drawn, and the
reward is confounded by platform delivery. Revisit if the volume ever supports
it; the fixed allocation is a coarse, robust, explainable approximation and it is
legible to a client, which a bandit is not.

**Let the human decide the mix each cycle.** It becomes conservative under
pressure — precisely when exploration matters most and feels least affordable.
Policy defended by data beats judgment applied under stress.

**Ship everything that passes the gates.** Defensible at low volume and it
abandons the portfolio decision, so the mix is whatever the generator happened to
produce.

## Consequences

- **Exploration survives bad quarters.** It is defended as a line item with a
  floor rather than as a preference someone has to argue for while CPA is rising.
- **Win rate falls as the engine improves**, because the control is the frontier
  and the frontier is rising. This must be explained to clients before it
  happens, and `09-CREATIVE.md §16` makes frontier lift the headline instead.
- **The explore tier is auditable.** Its share of frontier jumps is a tracked
  diagnostic: 15% of spend producing 0% of the jumps means the exploration is
  cosmetic and the hypothesis generator is at fault, not the policy.
- **Cost:** roughly 20% of creative spend goes to variants expected to lose. That
  is the price of a moving frontier, it appears in `07-RISKS.md §3` as a real
  line, and it is bounded by the share-of-spend-on-losers constraint.
- **Cost:** the allocation is a coarse instrument. It cannot express "this
  particular exploratory idea is unusually promising" — such an idea competes
  within the explore tier, and sometimes a good one waits a cycle.
