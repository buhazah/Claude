# 8. Learning lives in data, not in weights

Status: proposed

## Context

The default assumption about an AI company that accumulates proprietary data is
that it will eventually fine-tune on it. It is the reflex answer to "what is your
moat," and it is wrong for Phoenix specifically.

`08-MOAT.md` argues the durable assets are priors, calibration, negative
knowledge and boundary awareness. The question this ADR settles is *where those
live* — in model weights we train, or in data structures we compute.

The forcing case is mundane and certain to arrive: a client leaves and asks us to
stop using what we learned from them.

## Decision

**No fine-tuning on client data, ever, in any tier. All accumulated intelligence
is stored as data and computed by deterministic routines.**

Cards are **derived, not authored**. A claim is a pure function of its
contributions and a versioned statistical routine. The contribution ledger is
append-only and records which observations fed which card version.

This makes unlearning a batch job with a testable result:

```
tenant withdraws
  → mark their contributions withdrawn in the ledger
  → recompute every card whose support included them
  → cards falling below k=5 suppress automatically
  → assert: recomputed fleet is identical to one built without the tenant
```

The invariant, stated so it can be tested: **for any tenant T, the fleet
recomputed after T withdraws must be bit-identical to a fleet built from scratch
having never seen T.** Anything that cannot satisfy that assertion is not allowed
to hold learned state.

Models are used, heavily — to extract observations, to phrase claims, to apply
priors into a brief. They are never *trained*. What improves over time is what we
hand them, not what they are.

## Alternatives rejected

**Fine-tune a house model on outcomes.** The version with a real chance of
working, rejected on four independent grounds:

- **Unlearning is impossible.** A model that saw a departing client's data is
  permanently contaminated and the only honest remedy is retraining from scratch.
  No contractual language makes that not true.
- **It reopens the leakage argument** we spent ADR 0007 engineering away. "Their
  data is aggregated over five businesses and revocable" is a defensible sentence.
  "Their data is in the weights" is not.
- **Base models improve faster than our fine-tune would.** Each release resets
  the comparison, and a fine-tune is a fork that must be re-earned every time.
- **It converts an auditable asset into an opaque one.** A card carries its
  claim, evidence, scope and confidence and can be shown to a client. A weight
  cannot, which forfeits the explainability `01-PRD.md §10` sells.

**Fine-tune only on published (already anonymised) cards.** Cleaner, and it buys
little: a few thousand cards is not a fine-tuning corpus, and retrieval puts the
same cards in context with their evidence, scope and confidence intact — which is
strictly more useful than compressing them into weights that cannot say how sure
they are.

**Train small task-specific models** for the internal creative filter or the
override model. Genuinely reasonable, and deferred rather than refused. If it
happens, the same invariant applies: trained on published cards only, with a
retrain-from-ledger path, and never on tenant-local data. Trigger recorded in
`07-RISKS.md §5`.

## Consequences

- **The commercial promise is cleanly sayable:** *your data improves the system
  while you are a client, and leaves with you.* This matters more than it sounds
  when selling to a brand's counsel.
- **Every improvement is inspectable.** When judgment changes, a card changed,
  and the card has evidence and a version. Debugging a regression is a query, not
  an ablation study.
- **The moat rides base-model improvements instead of competing with them.** A
  better model plus our cards beats a better model alone, and the gap does not
  need re-earning on each release.
- **Cost:** we forgo whatever a fine-tune would have bought. Unmeasured, possibly
  real, and the price of an unlearning guarantee we can actually honour.
- **Cost:** retrieval quality becomes load-bearing. If the right card is not
  recalled at the right moment it may as well not exist — which is why card
  utilisation is a tracked metric in `08-MOAT.md §14` rather than an assumption.
