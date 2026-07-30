# 15. An evaluation that refuses to flatter

Date: Phase 11, M11.2
Status: accepted

## Context

Six hundred tests proved the machinery and said nothing about whether the
prompts were any good. A router that confidently sends every request to the
wrong agent passes all of them.

M10 added a 23-case corpus and it did its job — it found the arbiter gate that
blocked arbitration on every failure it had been built for. But 23 cases across
one dimension is not a ruler, and Phase 11 needed one, because the whole point
of the phase was to stop guessing at prompt changes.

The dangerous failure mode of an evaluation harness is not being wrong. It is
**flattering**: producing a green number that means nothing, which is worse
than a red one because it stops the search. Three specific ways that happens:

1. A check returns `True` when it could not actually decide.
2. A suite average counts an outage as a pass.
3. A baseline diff reports "nothing moved" because it silently compared
   nothing.

Every decision below is aimed at one of those.

## Decision

**A check answers yes, no, or *not applicable*.**

That third answer is the load-bearing one. A turn that errored, or a tool the
agent was never offered, must not count as a prompt failure — a provider outage
is not a quality regression — and must not count as a pass either. Skipped
checks contribute **zero weight**, so an outage produces a smaller sample
rather than a perfect score.

**Every case carries a confidence, and reports are weighted by it.**

`confidence` is the corpus author's estimate of how much the verdict is worth,
not the model's confidence in its answer. Checking that a financial answer
contains two numbers is a genuine proxy for "quantified"; checking that a
strategy answer contains the word "stop" is a much weaker proxy for "said what
to stop doing". Reporting both as 1.0 would let the weak ones accumulate into
a number nobody should trust.

So every suite reports **raw** and **weighted** side by side. Where weighted
sits well below raw, the suite is leaning on proxies and should be read rather
than trusted. A corpus that hides how much of its signal is proxy is a corpus
that will eventually be believed too much.

**Fatal is counted separately and never averaged.**

One confident mis-route matters more than ten soft misses, and an average will
happily hide it. `avoid` — the set of agents that would be *actively wrong* —
is the sharper instrument, and it is the number the report leads with.

**`accept` is a set of defensible answers, not the one right one.**

Several requests genuinely span two specialists. A corpus demanding one exact
id measures conformity to its author's guesses. Landing outside `accept` is a
miss; landing inside `avoid` is a failure.

**Most of the corpus is free, and CI runs it.**

Cases are tiered by what they cost to judge. `lexical` touches nothing;
`routed` may call the arbiter; `turn` runs an agent; `document` fans out per
section. `--free` runs everything up to `routed` *without* the arbiter, so
routing is scored on stage one alone — the half that can regress silently, as
it did in M10 when escalation hit 78% and no accuracy number moved.

Sampling is by stride, not prefix: taking the first N per suite would mean the
everyday cases never ran and the curated traps ran every time.

**Runs are compared, not just reported.**

A run writes a scorecard: per-suite metrics and one score per case, small
enough to commit. Transcripts are deliberately absent — a diff of two hundred
model outputs is unreadable; a diff of two hundred scores is exactly the
question "did the change help". A new case with no baseline is *not* counted as
an improvement, because a corpus that counts its own additions as wins is one
that talks itself into believing every change helped.

The exit code answers **"did this change make things worse"**, not "is the
corpus perfect". With a baseline, a regression fails the build. A corpus with
no failures left in it has stopped being an evaluation.

**Some things are deliberately not scored.**

Whether an answer *reasons well* is not a keyword question, and a check
claiming to measure it would be believed. Ten probes run with no verdict and
their transcripts are printed in full. Reading eight transcripts carefully
beats skimming fifty.

## Consequences

**One `Case` type covers all ten dimensions.** The fields a routing case
ignores are dead weight in its declaration, but every case scores, samples,
reports and diffs through one path — and with ten suites, a type per suite
would mean ten scoring functions to keep honest with each other.

**The harness is tested.** `tests/test_eval.py` grades the grader, and asserts
properties of the corpus itself: every case names agents that exist, no case
both accepts and avoids the same agent, every case that spends money carries a
rubric, and more than 60% stays free.

**It found real bugs before any model was involved.** On its first run: recall
ranking scored a stopword hit exactly like a real one, so "what are the margins
like" ranked a memory about consulting above the one stating the gross margin —
which scored zero and never appeared. Underneath was the same system holding
two opinions about what a word is: the router had matched by prefix since M1
while recall matched by equality, and the weaker rule governed what the user
could remember.

**The corpus is now a maintenance surface.** 288 cases have to stay true as
prompts change, and a case that is wrong is worse than no case — it either
blocks a good change or normalises a bad one. That is the cost, and it is
accepted because the alternative is what Phase 11 exists to stop: editing
prompts and hoping.
