# ADR 0005 — Dangerous tools suspend for a human; they do not fail or proceed

**Status:** accepted · M4

## Context

M1 built a permission wall with three blast-radius tiers, but nothing behind
it: tools were advertised to models and never executed. M4 makes them real,
which turns an abstract policy question into a concrete one — what happens the
moment a model asks to run `rm -rf build/`?

Three obvious answers are all wrong:

* **Refuse.** The agent cannot do the job it was asked to do, and the user has
  no way to say yes.
* **Proceed.** Jarvis takes irreversible action on the say-so of a model that
  may be reasoning over a web page an attacker wrote.
* **Ask, then restart.** Failing the run and asking the user to re-issue it
  discards a half-finished answer they are already reading.

## Decision

A `DANGEROUS` tool **suspends**. The run parks on an `asyncio.Event`, an
`approval.requested` event goes onto the bus, the UI raises a gate showing the
*exact call*, and the tool resumes the instant a human decides. The streaming
connection stays open throughout.

Supporting rules:

* **Timeout is denial.** An unanswered approval expires into refusal, so an
  unattended run fails closed rather than open.
* **Denial is data, not an exception.** The model is told the tool was refused
  and continues with that knowledge — it can apologise, try another route, or
  ask the user. The same applies to a tool that simply broke.
* **Grants separate "may be requested" from "may happen unasked".**
  `max_permission` is the ceiling; `auto_approve` is whether a human is
  consulted. Conflating them is what made the gate unreachable in the first
  draft — a `SENSITIVE` ceiling denied dangerous tools outright instead of
  gating them, so the entire approval path was dead code until a test caught it.
* **No path bypasses the wall.** Direct invocation over HTTP goes through the
  same `authorise` call as an agent's.

## Consequences

- The approval gate is global UI, not a page: a suspended run blocks on a
  person, so it must find them wherever they are.
- Long-running approvals hold a connection. Acceptable now (one user, one
  machine); when workflows land in M6, a suspended step will need to persist
  and resume across processes rather than park in memory.
- Every `SENSITIVE`-or-higher call is written to the hash-chained audit log
  *before* execution, so the log cannot contain an action whose authorisation
  is missing.
