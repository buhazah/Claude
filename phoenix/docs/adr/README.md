# Phoenix — architecture decision records

Proposed, not accepted. Nothing is built yet, and each of these is a decision
the blueprint depends on. Reject any of them and say so — the affected
documents get rewritten before code, not after.

| # | Decision | What it prevents |
|---|---|---|
| [0001](0001-control-plane-and-isolated-tenants.md) | Control plane above isolated per-tenant instances | Fifteen clients' data in one memory namespace |
| [0002](0002-ai-proposes-code-disposes.md) | AI proposes, deterministic code disposes | A hallucination reaching someone's budget |
| [0003](0003-mandates-not-approvals.md) | Mandates, not per-action approvals | Approval fatigue that transfers liability without judgement |
| [0004](0004-departments-are-a-metaphor.md) | Departments are a namespace; workflows are the spine | An undebuggable conversation between 21 agents |
| [0005](0005-autonomy-is-earned-in-shadow.md) | Autonomy is earned in shadow, per action type | Granting spend authority on a feeling |
| [0006](0006-channels-are-adapters.md) | Channels are adapters with declared capabilities; the acquisition workflow is the platform | A Meta-shaped data model, and a read-only mode that is a waiting room |

They build on Jarvis Core's ADRs 0001–0015, particularly 0001 (offline
determinism), 0002 (agents are data), 0005 (permissions are data), 0007
(durable suspension), 0010 (a mode only subtracts), 0014 (recommendations are
arithmetic) and 0015 (an evaluation that refuses to flatter).
