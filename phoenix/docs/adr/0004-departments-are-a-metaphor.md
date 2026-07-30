# 4. Departments are a metaphor; the workflow is the spine

Status: proposed

## Context

The brief specifies ~21 departments. An org chart describes who talks to whom,
and a system where 21 agents talk freely is expensive (every hop is a model
call), non-deterministic (different path each day), undebuggable (no component
owns a wrong output), and error-compounding (each step adds confidence, none
adds a check).

Jarvis learned a version of this. Phase 11 found the Chief of Staff's prompt
had promised delegation for ten milestones while the runtime executed one
agent — and when delegation was finally built it was deliberately capped at one
level, because "without a depth limit this is a recursion whose base case is
the user's budget."

## Decision

**A department is a namespace, not a process:**

```
department = a Jarvis mode + AgentSpecs + a memory scope
           + tools + an evaluation suite + a decision boundary
```

The **unit of execution** is a durable workflow. The client lifecycle and the
campaign lifecycle are state machines; Jarvis's engine already survives a
restart mid-flight (ADR 0007). Departments supply capability to the workflow.
They do not converse.

Where two departments need to interact, it is a workflow transition with a
persisted state change — inspectable, resumable, and attributable.

## Alternatives rejected

**Departments as autonomous agents with a message bus.** The compelling
version, and the one that produces a £400 token bill for one campaign brief and
no way to find out which hop was wrong.

**One agent with all the tools.** Simple, cheap, and it loses the specialisation
that makes prompts good — plus the memory scoping that keeps a client's
strategy out of a creative brief.

## Consequences

- The org-chart narrative survives for sales. It is real: departments have
  missions, KPIs and boundaries.
- Cost and latency are bounded and predictable.
- Debugging is a workflow trace, not a transcript archaeology exercise.
- **Four of nineteen departments turn out to need no model at all** —
  Operations, Campaign Operations, Creative Analytics, Finance. Discovering
  that is the main value of doing this exercise.
- **Cost:** less emergent, less impressive in a demo. Accepted willingly.
