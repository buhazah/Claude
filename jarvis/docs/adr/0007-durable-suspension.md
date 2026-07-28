# ADR 0007 — A workflow's program counter lives in the database, not the stack

**Status:** accepted · M6 · supersedes part of ADR 0005

## Context

M4 made a dangerous tool suspend for a human decision by parking on an
`asyncio.Event`. That is right for a chat turn — somebody is watching a stream,
and the wait is measured in seconds. ADR 0005 already flagged the limit: a
workflow can wait overnight, and a coroutine's stack is not a place to keep
something that has to outlive the process. Restart the API and every parked
workflow is gone, with no error and no record of what was lost.

The tempting fix is to keep the connection alive harder — longer timeouts, a
reconnecting client. That treats a durability problem as a networking problem.

## Decision

Workflow execution is a **loop over persisted state**, not recursion:

```
load run → execute step at `cursor` → write result into `context`
         → advance `cursor` → persist → repeat
```

`cursor` and `context` together are the program counter, and both live in a
row. An approval step sets `state = AWAITING_APPROVAL` and *returns*; nothing
is held open. `resume(run_id)` loads the same row and continues — seconds
later or tomorrow, in this process or a different one.

Supporting decisions:

* **The scheduler recovers on boot.** Durable suspension is only durable if
  something picks the runs back up; a row nobody ever reads again is
  indistinguishable from a lost one.
* **A denial routes, it does not only fail.** `if_false` lets the graph handle
  refusal as a normal path.
* **Causality is tracked.** A `ContextVar` set while driving stamps every event
  a workflow causes, because an event-triggered workflow whose agents write
  memories would otherwise re-trigger itself forever. This was a real loop, not
  a hypothetical one — the test suite hung on it.
* **Conditions are structured data, never expressions.** A workflow definition
  is user input, and this process owns a shell tool.

## Consequences

- The engine cannot hold anything interesting in local variables between
  steps; everything a later step needs must be written into `context`. That is
  a real constraint on the code, and the price of surviving a restart.
- In-memory and SQL stores must behave identically, which forced the in-memory
  store to copy on read and write — it was handing out live references, and a
  caller could observe engine mutations without re-reading.
- M4's interactive approval path is unchanged and still correct for chat. The
  two now coexist deliberately: `create` registers and returns, `request`
  registers and waits.
- Approvals themselves are still in memory (M10 makes them durable), so a
  restart currently loses the *decision record* even though the run survives.
  The recovery path is written against the store, so that is a swap, not a
  redesign.
