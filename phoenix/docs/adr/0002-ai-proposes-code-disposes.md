# 2. AI proposes, deterministic code disposes

Status: proposed

## Context

The brief's philosophy — deterministic software where deterministic logic
suffices, AI only where intelligence creates measurable value — is right, and
it is stated as a preference. A preference degrades under deadline. It needs to
be an invariant with a shape that code enforces.

Phoenix spends other people's money. The consequence of a hallucination is not
a bad paragraph.

## Decision

**No model output ever mutates external state.**

A model produces a **proposal**: a typed object with a schema, a rationale, and
the evidence it was reasoning over. Deterministic code then accepts it, clamps
it, or rejects it.

```
model → Proposal(typed) → validator(code) → Decision → Action(code)
```

Corollaries, all testable:

- Budgets, limits, schedules, retries, reconciliation and money arithmetic are
  code. Always.
- Every AI output has a schema. An unparseable output is a rejected proposal,
  not an error and not a guess.
- Prose that reports numbers is handed the numbers. Any figure in the output
  that was not passed in is a hard failure of the `report` evaluation suite.
- The mandate check is code. It cannot be prompted, argued with, or persuaded.

## Alternatives rejected

**Trust the model with guardrails in the prompt.** Prompts are advisory. Jarvis
Phase 11 found four separate cases of instructions that never reached the model
or contradicted another instruction, in prompts that read perfectly well.

**Let AI call the API directly with a permission tier.** Permission tiers bound
*what kind* of action, not *what magnitude*. `update_budget` is one permission
whether the number is £10 or £10,000.

## Consequences

- The blast radius of a hallucination is a rejected proposal.
- Every AI output becomes an audit row with a rationale and evidence.
- Testing gets easy: validators are pure functions with exhaustive tests.
- **Cost:** more types, more plumbing, and occasionally a correct proposal
  rejected on a schema technicality. Accepted.
