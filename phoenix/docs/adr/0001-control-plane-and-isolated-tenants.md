# 1. A control plane above isolated per-tenant instances

Status: proposed (blocks all implementation)

## Context

Phoenix serves many clients. Jarvis Core does not.

`jarvis/docs/ARCHITECTURE.md §7`, written in M1 and still true, lists
multi-tenancy and RBAC beyond a single principal as deliberate non-goals. Every
store, memory scope, approval queue, audit log and cost ledger assumes one
principal.

Running fifteen clients on one instance would put fifteen clients' ad
performance in one memory namespace and one approval queue. That is not a gap
to work around; it is a confidentiality incident with a delay fuse.

## Decision

**A thin control plane above one isolated Jarvis instance per tenant.**

The control plane owns tenancy, billing, mandates, the human console, fleet
scheduling, and agency-level knowledge. It never holds client ad data.

Each tenant gets its own instance: own database, own vault, own memory, own
audit log, own cost ledger.

Cross-client learning flows **upward only**, as anonymised knowledge cards with
scope and evidence. Never sideways, never raw.

## Alternatives rejected

**Add tenancy to Jarvis Core.** Faster to write. Every store grows a
`tenant_id`, every query grows a filter, and one missing `WHERE` clause leaks a
client's data to another — silently, and discovered by the wrong person.
Isolation that depends on remembering a predicate is not isolation.

**One instance, memory scopes only.** Jarvis's scoping is real (ADR 0010) but
it was built to separate an agent's working notes from another's, not to hold a
legal boundary. Phase 11 found a case where the `memory_search` tool ignored
scope entirely, giving an agent one path to memory that honoured the narrowing
and another that did not. That class of bug is survivable between agents and
unsurvivable between customers.

## Consequences

- **Isolation is by database.** The only kind a customer's counsel believes.
- **The confidentiality story for learning is trivial.** Knowledge cannot flow
  sideways because there is no sideways.
- **Cost:** ~£30–60/client/month of infrastructure, plus a control plane to
  build, plus per-tenant migration orchestration.
- **Ceiling:** instance-per-tenant becomes uncomfortable somewhere past ~200
  clients. Design the stores so tenancy inside Core remains possible; do not
  build it now.
- **Jarvis Core stays unchanged.** Phoenix is an application on a platform, not
  a fork. Core's non-goal remains a non-goal.
