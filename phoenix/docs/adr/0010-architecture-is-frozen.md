# 10. Architecture is frozen until a customer exposes a deficiency

Status: **accepted**

The first ADR here that is a decision rather than a proposal. It is also the one
that governs whether any of the other nine ever get tested.

## Context

Nine documents and nine ADRs describe a coherent system. None of it has met a
customer.

The marginal value of design has gone negative. The last two documents are the
evidence: `08-MOAT.md` specifies a publication gate requiring five supporting
tenants, which cannot clear a single claim until roughly the fiftieth client.
`09-CREATIVE.md` specifies a learned review filter requiring hundreds of operator
rejections to train. Both are, as far as I can tell, correct. Both are also
speculation with a schema attached, and both were written before anyone had run
a single campaign.

The failure mode this ADR exists to stop is specific and common: an architecture
that keeps getting better at answering questions nobody has asked, while the
question that decides the company — *why would someone pay again next month?* —
goes untested because it cannot be answered from a repository.

## Decision

**Foundational architecture is frozen. It unfreezes only when a named client
exposes a named deficiency.**

The boundary is drawn by a rule chosen to survive a busy week:

> **Build freely inside the tenant boundary. Freeze everything that crosses it.**

Inside a tenant, one client makes a feature worth building — onboarding,
reconciliation, the report, diagnosis, recommendations, creative generations,
fatigue detection. Across tenants, nothing pays off below roughly fifty clients —
the publication gate, claim store, fleet calibration, contradiction resolution,
cross-client priors, the learned filter. Structural decisions (the spine,
mandates, the channel port, tenant isolation, the entity graph) do not change at
all.

**One carve-out: keep recording, stop building consumers.** Observations,
predictions, override reason codes and contribution provenance are written from
the first campaign. Nothing reads them. Four append-only tables and a dropdown —
perhaps three days — and the alternative is that the first two years of history
exist in a shape nothing can ever learn from.

**Unfreezing requires five things**, filed in `DEFICIENCIES.md`: a named client,
a dated incident, a quantified cost, the workaround that was tried first, and the
smallest fix. **Three different clients logging the same gap unfreezes it
automatically.** A client *asking* for something does not qualify; the bar is
that its absence cost something measurable.

## Alternatives rejected

**Finish the architecture, then sell.** The version that feels responsible. It
optimises for a system that is complete against guesses, and every week spent on
it is a week the guesses go unchecked. `00-STRATEGY.md §4` made this exact
argument about the creative assumption and it applies to the architecture itself.

**Freeze by convention rather than by process.** A stated intention with no
exception path is ignored within a month, because the first genuinely necessary
change has nowhere to go and sets the precedent that the freeze is advisory.

**Freeze everything, including in-tenant work.** Over-corrects into a system that
cannot respond to the clients it just acquired. The in-tenant half is precisely
what a client experiences, and it is cheap because n=1 justifies it.

**Skip the recording carve-out for a cleaner freeze.** Tempting and wrong. It is
three days of work against a permanent, unrecoverable loss — the same argument
that put the channel port in Phase 0.

## Consequences

- **The next architecture document is written by customers.** The deficiency
  register turns the next design phase from an exercise into a backlog with
  names on it.
- **Some of the design will be shown to be wrong**, and the register is where
  that becomes visible rather than embarrassing. It is expected to fill up. An
  empty register after six months means nobody is filing.
- **Special cases will accumulate.** Accepted, and bounded by the invariants in
  `07-RISKS.md §5`, which do not bend under shipping pressure — that condition is
  what they were written for. Per-client hacks are recorded as debt with a
  trigger. Manual effort is the preferred workaround and is tracked in the effort
  ledger, which converts each gap into data.
- **Cost:** work will be done twice. Something built for client three will be
  rebuilt properly at client thirty. That is cheaper than building it correctly
  at client zero for a requirement that turns out not to exist.
- **This ADR is itself frozen until client twenty.** Reopening the freeze is a
  decision for after the cohorts in `10-VALIDATION.md §5`, not during them.
