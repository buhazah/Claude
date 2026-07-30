# Architecture decision records

One file per decision that would otherwise be re-argued. Each says what the
alternative was and why it lost, because a decision recorded without its
rejected alternative is a preference with a date on it.

| # | Decision | The thing it prevents |
|---|---|---|
| [0001](0001-offline-first-determinism.md) | Offline determinism is a product requirement | A system that cannot be explored, demonstrated or tested without a key |
| [0002](0002-agents-are-data.md) | Agents are data, not subclasses | Thirty execution paths, twenty-nine of them undertested |
| [0003](0003-two-stage-routing.md) | Routing is two-stage | A model call on every message to answer what a keyword already answered |
| [0004](0004-one-ranker-many-backends.md) | One ranker, many backends | "Why did Jarvis recall that?" having a different answer per deployment |
| [0005](0005-tool-permissions-and-approvals.md) | Permissions are data, checked at call time | An agent widening its own reach by reasoning about it |
| [0006](0006-citations-are-structural.md) | Citations are structural | A passage attributed to a file rather than checkable against it |
| [0007](0007-durable-suspension.md) | Suspension is a database row | A decision that has to arrive before the process restarts |
| [0008](0008-interruption-is-the-product.md) | Interruption is the product | Voice that keeps talking over you, and history that records what was generated rather than heard |
| [0009](0009-computer-control-names-things.md) | Computer control names things | An approval prompt showing coordinates instead of "click «Place order — £2,480»" |
| [0010](0010-a-mode-only-subtracts.md) | A mode only ever subtracts | Picking a mode widening what Jarvis is allowed to do |
| [0011](0011-secrets-leak-everywhere-else.md) | Secrets leak everywhere else | An encrypted vault whose contents are in the logs |
| [0012](0012-evidence-is-exclusivity.md) | Routing evidence is exclusivity, not frequency | A threshold with nowhere useful to sit: low enough for precise matches means low enough for homonyms |
| [0013](0013-the-files-are-the-memory.md) | The files are the memory | A markdown export that overwrites the user's correction on the next sync |
| [0014](0014-recommendations-are-arithmetic.md) | Recommendations are arithmetic; delegation is opt-in | A proactive assistant that is wrong in a way nobody can correct, and a recursion whose base case is the budget |
| [0015](0015-an-evaluation-that-refuses-to-flatter.md) | An evaluation that refuses to flatter | A green number that means nothing, which stops the search |

## Amendments

Decisions that a later milestone changed rather than replaced. Recorded here
rather than by editing history, so the reasoning that was current at the time
stays readable.

- **0003** is superseded in part by **0012**. The two-stage funnel stands; the
  scoring function inside stage one does not. The threshold was never the
  problem.
- **0010** gained a second enforcement point in Phase 11. Modes narrowed the
  memory *scope*, and `AgentRuntime._build_context` honoured it — but the
  `memory_search` tool called the store with no scope at all, so an agent had
  one path to memory that respected the narrowing and another, reachable by the
  model, that did not. Tools now declare `scoped`, and the runtime supplies the
  namespace from `spec.scope`; the model's own `scope` argument is stripped
  before authorisation, because a namespace the model can name is one it can
  pick. Same shape as the M9 routing-fallback hole: a narrowing enforced in one
  place and ignored in another is the recurring failure mode of this
  architecture.
