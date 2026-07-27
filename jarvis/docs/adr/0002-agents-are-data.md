# ADR 0002 — Agents are data, not subclasses

**Status:** accepted · M1

## Context

The catalog needs ~30 specialists and will keep growing. The conventional
approach is a `BaseAgent` class with one subclass per agent. With thirty
subclasses, streaming, retries, memory recall, metrics and cost accounting get
re-implemented — or subtly diverge — thirty times, and each new agent is a code
change with its own tests.

## Decision

An agent is an `AgentSpec`: id, prompt, responsibilities, capability tags,
routing keywords, tool allowlist, memory scopes, model policy, privacy floor.
A single `AgentRuntime` executes any spec.

## Consequences

- One well-tested execution path. A new agent inherits streaming, memory,
  metrics, permissions and observability without writing any of it.
- Adding an agent is adding a catalog entry — and, later, a user-authored spec
  stored in the database, with no deploy.
- Specs are introspectable: the routing preview endpoint can show *why* an
  agent was chosen because the routing signals are data, not control flow.
- Genuinely bespoke behaviour (a research loop, a coding agent driving Claude
  Code) does not fit a pure spec. Those become **tools** the spec is allowed to
  call, not runtime subclasses — which keeps the special case out of the core.
