# Operator AI — Product Direction

> The AI Chief of Staff for ecommerce.
> "Most tools give you data. Operator AI gives you decisions."

This supersedes the earlier "Storepilot / autopilot for dropshippers" framing.
The engine and platform we built are reused unchanged — only the positioning,
target customer, and surface framing change.

## Target customer
Established Shopify brands doing **$500k–$20M/year**. Busy operators/founders
with real data and acute pain from software sprawl — not beginners.

## What V1 is
A **daily executive briefing + AI Chief of Staff**:
- Connect store + ad accounts.
- Operator AI analyzes daily and reports: what happened, why, what to do next.
- Prioritized recommendations (expected impact, confidence, required action).
- Approve / Reject / Schedule from a dashboard. Read-only analysis first;
  execution comes later.

## Scope decisions (from the PRD critique)
- **V1 integrations: Shopify + Meta only.** The original PRD's five integrations
  (Shopify, Meta, Google Ads, GA, Klaviyo) is 6+ months of plumbing before a
  single insight. Shopify + Meta answers "why did revenue move" for most cases.
  Add Google/Klaviyo after paying users.
- **Insights before execution.** V1 recommends; V2 executes approved actions;
  V3 autonomous departments. Matches the 3-level decision engine
  (auto / approval / mandatory-manual) already implemented as agent autonomy.
- **Defensibility is outcome data, not features.** "Business memory" and a
  "decision engine" are features anyone can build. The moat is the proprietary
  loop of which recommendations were approved and what happened next, compounding
  over time. Build for that from day one (log recommendation → decision → result).
- **Pricing: $499 / $1,499 / $4,999.** Justified only if recommendations are tied
  to provable revenue/profit impact. V1 must surface things the owner didn't know
  and that made/saved money — not just summaries.

## How the existing build maps onto Operator AI
| PRD concept | What we already built |
|---|---|
| Chief of Staff agent | master orchestrator (`src/company/master.py`) |
| Executive agents (Analytics/Marketing/Ecommerce/Customer) | store, ads, creative, support, finance agents |
| Decision engine risk levels | per-agent autonomy: advise / approve / auto |
| Approval workflow | action_queue + dashboard Approve/Reject/Schedule |
| Multi-tenant SaaS | `platform/` runner + Lovable web app |

## Stack note
Keep the Claude Agent SDK engine we built; it already implements the
Chief-of-Staff → executive-agents → tools hierarchy. The PRD's LangGraph + n8n is
redundant with each other and with what exists — adopt only if a real limit is hit.
