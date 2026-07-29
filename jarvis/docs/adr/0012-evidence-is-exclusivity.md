# 12. Routing evidence is exclusivity, not frequency

Date: Phase 11, M11.1
Status: accepted
Supersedes part of [ADR 0003](0003-two-stage-routing.md)

## Context

ADR 0003 established a two-stage router: a free lexical pass decides, and an
LLM arbiter is consulted only when that pass is ambiguous. The claim that makes
the design worth having is that most requests never reach stage two.

M10's evaluation against real models found the lexical pass routing confidently
and wrongly on homonyms — "our **security** deposit is due" went to the
Security Agent at 0.50 confidence. The fix at the time was to raise
`AMBIGUITY_THRESHOLD` from 0.35 to 0.55, so those matches would escalate.

That fixed the homonyms and quietly broke the design. The scoring function
awards `1.0` per keyword hit and squashes with `hits / (hits + 1.5)`, so one
keyword scores 0.40 — below the new bar. Measured on the routing corpus, 78% of
requests escalated. The two-stage router had become a one-stage router with an
expensive first stage, and nothing said so, because escalation is not an error:
it is latency and spend.

## The mistake underneath

The threshold was not wrong. The score was measuring the wrong thing.

`hits` counts **how much text matched**. What routing needs is **how much the
match distinguishes this agent from the others** — and those are different
quantities:

- "calendar" is strong evidence for the Calendar Agent because no other agent
  claims the word.
- "post" is weak evidence for anyone, because the Copywriter and the Social
  Media Manager both claim it.

Both scored exactly 1.0. A scoring function that cannot tell those apart leaves
the threshold nowhere useful to sit: low enough to let precise matches decide
means low enough to let homonyms decide, and high enough to catch homonyms
means high enough to escalate everything.

## Decision

**A keyword's weight is divided by the number of agents in the registry that
claim it.**

An exclusive keyword is worth as much as a phrase, because it is as diagnostic
as one. A keyword two agents share is worth half, which puts it under the
threshold and escalates — the correct outcome, since two agents claiming a word
is what an ambiguous word *is*.

Two keywords are the same claim when either is a prefix of the other, because
that is what the matcher matches on. Research's `market` and Marketing's
`marketing` were one contested word pretending to be two.

Counted **per registry, not per catalog**. A mode narrows by handing over a
smaller registry (ADR 0010), and a word three agents contest in the full
catalog may be uncontested among the six that survive. It should score as the
evidence it has become. This falls out of computing the index from
`self._specs` rather than from `CATALOG`, and it is the same reasoning that put
`_fallback()` on the registry in M9.

The capability bonus is removed in the same change. Fifteen of thirty agents
had a capability whose value was also one of their keywords, so a single word
scored twice — and only for the agents whose remit happens to be one English
noun. Capabilities are the vocabulary modes and permissions filter on; users
do not type "analysis".

## Consequences

Measured on the 23-case routing corpus, lexical stage only:

```
                       before      after
escalation rate        78%         48%
accepted (of 23)       13          18
actively wrong          3           1
```

Escalations fall by a third while accuracy rises, because the cases that stop
escalating are the ones stage one already had right.

**The catalog now has a cost it did not have.** Adding a keyword to one agent
weakens it for every agent that already claims it. That is the intended
behaviour — it is the same fact stated twice — but it means keyword lists can
no longer be extended without thought, and a spec that keyword-stuffs now makes
its neighbours worse rather than only making itself louder.

**Exclusivity is necessary, not sufficient.** A word can be unique in the
catalog and still be a homonym in English. "security deposit" is exactly that,
and the fix was not a rule but a missing keyword: the Financial Analyst never
claimed `deposit`, so nothing contested the Security Agent's reading. The
general lesson is that contested requests are only detectable when both
readings are represented in the catalog, which makes coverage of the *second*
plausible agent part of what a keyword list is for.

**The threshold stays at 0.55.** It is now reachable: one exclusive keyword
scores 0.57. The number was never the problem.
