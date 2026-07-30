# 14. Recommendations are arithmetic, and delegation is opt-in

Date: Phase 11, M11.5
Status: accepted

## Context

Two gaps, closed together because they are the same gap seen from either side:
Jarvis was **reactive** and **single-threaded**. It did what it was asked, by
one agent, and noticed nothing in between.

The prompts had been claiming otherwise since M1. The Chief of Staff's said
"you decide whether to answer it, decompose it, or hand it to specialists"; the
Planner's said each step "names an owner (agent or human)". Audit finding F4
established that neither was possible: `AgentSpec.collaborators` was read by
nothing, and `Orchestrator.handle` routed to exactly one agent and discarded
the rest of the candidates. So every multi-specialist request produced a
*description* of the delegation, because describing it was the only thing
available.

## Decision 1: recommendations are ranked by arithmetic, not by a model

The obvious implementation is to hand a model everything Jarvis knows and ask
"what should they do today". It is one call, it reads beautifully, and it is
the wrong answer.

It is **unauditable** — you cannot ask why something ranked third.
It is **non-deterministic** — the same state yields a different list each time.
It is **unavailable offline**, which is when a personal assistant matters most.
And it is **unfalsifiable**: when it tells you the wrong thing, there is nothing
to fix, because there is no rule to correct.

So: detection is nine small deterministic detectors over a snapshot of state
Jarvis already has, and ranking is

```
score = impact × urgency × confidence
```

Multiplicative, not additive, so nothing important-but-distant outranks
something blocking, and a low-confidence guess cannot climb the list by
claiming to be critical. Every recommendation carries the evidence that
produced it. If one is wrong, either the evidence is wrong — fix the data — or
the weighting is wrong — fix the number. Both are things a person can do.

A model is used later, in the briefing, and only to *phrase* what the
arithmetic already decided.

### Three axes, deliberately coarse

**Impact** — how much worse things get if this is ignored. A blocked launch is
not the same size of problem as an unlinked note, and a ranking that cannot
tell them apart is a to-do list.

**Urgency** — how much the answer changes by waiting. This is where the
interesting case lives: **a cold project is important and almost never urgent,
which is exactly why it stayed cold.** Encoding that means the ranking will not
let urgency carry it to the top, and the user is not nagged daily about
something they have already decided to leave.

**Confidence** — how sure the *detector* is. A pending approval is certain;
"this project looks stalled because nobody edited a file" is a guess, and the
number says so rather than pretending otherwise.

### The hard part is not noticing. It is shutting up.

The failure mode of every proactive assistant is noticing everything,
prioritising nothing, and being muted inside a week — after which it notices
nothing at all. So:

- Each detector caps its own output. One that could produce fifty rows produces
  its worst four or five.
- A sweep surfaces at most ten, and at most two per signal type, so one noisy
  detector cannot bury the approval that is blocking a run.
- The report says how many it **held back**, because a short list that hides
  its own truncation is a different kind of dishonest.
- No news is a valid answer. An empty system recommends nothing rather than
  inventing something to say.

Recommendation ids are stable across sweeps — derived from what was observed,
not minted per run — because otherwise "not now" would be meaningless: the next
sweep would produce a fresh id and the same thing would come straight back
wearing a new name. Dismissals expire after a week, because a recommendation
worth detecting is worth raising again eventually, and a permanent dismissal is
how a system quietly stops mentioning the thing that later goes wrong.

## Decision 2: delegation is opt-in per agent, via `collaborators`

`collaborators` finally means something. An agent with no collaborators never
delegates, so twenty-odd specialists behave exactly as they did and only the
agents whose prompts promise coordination pay for it.

Four constraints, each a failure this would otherwise have:

**One level. A delegate never delegates.** Without a depth limit this is a
recursion whose base case is the user's budget.

**Only agents in *this* registry.** A mode narrows by handing over a smaller
one (ADR 0010), and a delegator reaching for the full catalog would be a hole
straight through the narrowing — the same defect as the hardcoded routing
fallback in M9. Two rules compose here: the mode removes an agent, which can
leave a single assignment, and a single assignment is not a delegation, so the
request quietly falls back to one agent rather than to a one-item fan-out.

**One assignment is discarded.** It is the same work with an extra model call
in front of it.

**It degrades to ordinary routing.** The decomposition is a model call; with no
model it returns nothing parseable and the request runs as one agent. Offline
determinism is a product requirement (ADR 0001), and a feature that turns the
echo provider into an error is a feature that breaks the demo.

Specialists run **sequentially and silently**: sequentially because their
tokens would interleave into an unreadable stream, silently because the user
asked one question and wants one answer, not four drafts and a summary. What
*is* streamed is the delegation itself — who was asked what — so the work is
visible while it happens. Tool activity stays visible too; only prose is held
back.

A specialist that fails does not fail the request. Its report becomes "could
not finish, because…", which the synthesis is instructed to pass on: a partial
answer that says what is missing beats no answer. And if the *synthesis* call
fails, the specialists' reports are handed over raw rather than discarded —
their work is done and paid for, and losing it because the last call failed
would be the worst available outcome.

## Consequences

**Cost is bounded and explainable.** A delegated request is one route, one
decomposition, N specialists and one synthesis. Two free gates run before any
spend: the agent must declare collaborators, and the request must be long
enough to plausibly contain more than one thing. Both are crude; both cost
nothing, which is the right trade against a model call on every message.

**The recommendation engine is free.** No key, no network, no model. It works
on a first run with nothing configured, which is when a user is least likely to
have set anything up and most likely to be evaluating whether this is useful.

**Building it found two bugs in M11.4.** Exercising the engine against a real
vault showed the same lease renewal reported as two separate deadlines: an
episodic memory lands in two files, and the journal *pointer* was being counted
as a second memory — so every episodic fact was recalled twice, ranked twice
and recommended twice. Pointers are now marked in the frontmatter and skipped
by recall. The same run showed journal lines linking to `[[global]]`, which is
a filing detail rather than a topic, so area notes are no longer linked from
the journal.

Neither was visible from the Obsidian tests, which asserted that the journal
line existed. It took a subsystem *consuming* memory to notice that there were
two of everything — which is an argument for building the consumer.

**`collaborators` is load-bearing now.** Adding an agent to another's
collaborator list is a behavioural change, not documentation. That is the point,
but it means the field can no longer be filled in casually.
