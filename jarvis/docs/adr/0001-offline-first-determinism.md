# ADR 0001 — Offline determinism is a product requirement, not a test convenience

**Status:** accepted · M1

## Context

Jarvis depends on hosted LLM providers. The obvious approach is to mock HTTP
responses in tests and require API keys to run anything. That produces a system
that cannot be demoed without keys, cannot run in CI without secrets, has no
answer when every provider is down, and whose tests drift from real behaviour
as mocks age.

## Decision

Ship a real provider adapter, `EchoProvider`, that produces deterministic output
with no network. It is registered last in every provider chain and is always
present. Memory, runs and the bus have in-process implementations behind the
same ports, and the clock is injectable.

Consequences that follow deliberately:

- The full test suite runs with no keys, no network, no database, in under two
  seconds.
- `ModelRouter`'s fallback chain always terminates in something that works, so
  a total provider outage degrades quality instead of erroring.
- Any contributor can run the whole system on first clone.
- Local-first mode (M3) is not a special path; it is the default path with
  different adapters.

## Consequences

Echo output is not useful text, so end-to-end tests assert on *structure* —
routing decisions, run states, event sequences, cost accounting — rather than
on model quality. Prompt quality is evaluated separately against real models,
which is the correct place for it anyway.
