# Evaluation

Everything in `apps/api/tests/` runs against a deterministic offline provider.
That proves the machinery and says nothing at all about whether the prompts are
any good — a router that confidently sends every request to the wrong agent
passes 600 tests.

`apps/api/eval/` closes that gap. It is not a test suite, and the difference
matters: tests assert, and "is this prompt any good" has no boolean answer.

```bash
make eval-plan          # what a run would do and cost — spends nothing
make eval-free          # the free two-thirds — no key, no network
make eval budget=5      # the whole corpus against a real model
make eval-sample n=8    # a cheap representative pass
```

## The corpus

288 cases across the ten dimensions Phase 11 named. Each one carries the five
things that phase asked for:

| asked for | how it is expressed |
|---|---|
| expected behaviour | `behaviour`, prose — and the checks that approximate it |
| expected agent | `accept` and `avoid` |
| expected tools | `called()` / `never_called()` / `called_nothing()` |
| success criteria | `must` (all required) and `should` (partial credit) |
| confidence score | `confidence`, the author's estimate of the verdict's worth |

```
routing    198     planning    10     tools        12     memory      10
research    10     execution    7     workflows     4     documents    4
coding      10     business    23
```

One `Case` type covers all ten rather than a class per suite. The fields a
routing case ignores are dead weight in its declaration, but every case scores,
samples, reports and *diffs against a baseline* through one path — and with ten
suites, a type per suite would mean ten scoring functions that have to be kept
honest with each other.

## Three ideas the corpus depends on

**`accept` is a set of defensible answers, not the one right one.** Several
requests genuinely span two specialists. A corpus that demands one exact id
measures conformity to its author's guesses rather than quality.

**`avoid` is the sharper instrument.** These are the agents that would be
actively wrong. A hit there is a real failure rather than a matter of taste,
and it is the number the report leads with.

**A check answers yes, no, or *not applicable*.** That third answer is what
keeps the harness honest. A turn that errored, or a tool the agent was never
offered, must not count as a prompt failure — and must not count as a pass
either. Skipped checks contribute no weight, so a provider outage produces a
smaller sample rather than a perfect score.

## Scoring

Three levels, and they are not interchangeable.

**Fatal** — the case landed on an `avoid`, or failed a `must`. Counted
separately and never averaged away, because one confident mis-route matters
more than ten soft misses and an average will happily hide it.

**Must** — all have to hold for the case to pass.

**Should** — partial credit, for the checks where a miss is a matter of degree.

Every suite reports a **raw** score and a **weighted** one. Weighted discounts
each case by its `confidence`: checking that a financial answer contains two
numbers is a genuine proxy for "quantified", while checking that a strategy
answer contains the word "stop" is a much weaker proxy for "said what to stop
doing", and the report refuses to treat them as equal evidence. Where weighted
sits well below raw, the suite is leaning on proxies and should be read rather
than trusted.

## What is deliberately not scored

Whether an answer *reasons well* is not a keyword question, and a check that
claimed to measure it would be believed. So eight agent probes and two mode
probes run with no verdict at all and their transcripts are printed in full.

Reading eight transcripts carefully beats skimming fifty.

## Cost tiers

Most of the corpus never touches a model. That is the property that makes it
something anyone actually runs.

| tier | what it does | cost |
|---|---|---|
| `lexical` | the registry or the store, nothing else | free |
| `routed` | full `plan()`, may call the arbiter | one cheap call, sometimes |
| `turn` | run the agent, tools included | one call, more with tools |
| `document` | outline plus a call per section | seven-ish calls |

`--free` runs everything up to `routed` *without* the arbiter, so routing is
scored on stage one alone. That is the half that can regress silently — M10
raised escalation to 78% and no accuracy number moved (audit F1) — and it is
what CI runs on every push.

Sampling is by stride, not by prefix. Taking the first N per suite would mean
the everyday cases never ran and the curated traps ran every time, which is the
opposite of what a sample is for.

## Measuring instead of guessing

The point of all of it.

```bash
make eval-free                                   # scored against the committed floor
make eval budget=5 baseline=before.json note="tool-aware house rule"
```

A run writes a **scorecard**: per-suite metrics and a score per case, small
enough to commit. Transcripts are deliberately absent — a diff of two hundred
model outputs is unreadable; a diff of two hundred scores is exactly the
question "did the change help".

Given a baseline, the report says what moved:

```
| suite    | before | after |    Δ | fatal before → after |
| routing  |   0.72 |  0.78 | ▲ +0.06 | 7 → 5 |

### 2 case(s) broke
- `route-042` — 1.00 → 0.00, now fatal
```

So a prompt edit is answerable with "eleven cases improved and two broke"
rather than with an overall average that hides both.

`eval/baseline.json` is the committed floor for the free suites. Regenerate it
with `make eval-baseline note="..."` — but only after reading what moved and
agreeing with it, because a baseline rewritten to match the current behaviour
is not a baseline.

The exit code answers *did this change make things worse*, not *is the corpus
perfect*. With a baseline, a regression fails; without one, any fatal fails. A
corpus with no failures left in it has stopped being an evaluation.

## The harness is code, and it is tested

`tests/test_eval.py` grades the grader. The failure it exists to prevent is the
worst one an evaluation can have: **scoring that flatters**. A check returning
True when it could not decide, a suite average counting an outage as a pass, a
baseline diff reporting "nothing moved" because it compared nothing — each
produces a green number that means nothing, and a green number that means
nothing is worse than a red one, because it stops the search.

It also asserts properties of the corpus itself: every case names agents that
exist, no case both accepts and avoids the same agent, every case that spends
money carries a rubric and a statement of what good looks like, and more than
60% of the corpus stays free.

## What this has already found

The corpus is not hypothetical. On its first run, before any model was
involved:

- **Recall ranking scored a stopword hit exactly like a real one.** "what are
  the margins like" ranked a memory about consulting work above the one stating
  the gross margin, because both contain "the" and the lexical score was the
  share of query terms matched. The memory that answered the question scored
  zero and did not appear at all.
- **The same system held two opinions about what a word is.** The router has
  matched by prefix since M1; recall matched by equality, so "margins" never
  found "margin". The weaker rule governed what the user could remember.
- **The Financial Analyst never claimed `audit`**, so "audit what my
  subscriptions are costing me" routed to the Security Agent uncontested — the
  same omission as `deposit` in M11.1, and the same fix.

None of those needed a model, a key, or a network. They needed somebody to
write down what the answer should have been.
