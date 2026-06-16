# Shopify Agent Company

A reusable, **store-agnostic** AI agent company for Shopify dropshipping stores.
A **master agent** orchestrates specialized subagents, each wired to live tools
(Shopify, ad research, ad platforms). Point it at *any* store with a single
config file — nothing is hardcoded to one shop.

```
                    ┌─────────────────────┐
                    │   MASTER AGENT       │  routes tasks, holds shared
                    │  (orchestrator)      │  memory, reviews, reports
                    └──────────┬──────────┘
        ┌──────────┬───────────┼───────────┬──────────┐
        ▼          ▼           ▼           ▼          ▼
   ┌────────┐ ┌────────┐  ┌────────┐  ┌────────┐ ┌────────┐
   │ STORE  │ │CREATIVE│  │PRODUCT │  │FINANCE │ │  ...   │
   │ AGENT  │ │ STUDIO │  │ SCOUT  │  │ AGENT  │ │ (add)  │
   └────────┘ └────────┘  └────────┘  └────────┘ └────────┘
```

## Why config-driven

Every store differs in brand voice, margins, and rules. Those live in
`config/store.yaml` (one per store) — the **code never changes**. Run the same
company against ten different stores by swapping the config.

## Quick start

```bash
cd shopify-agent-company
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                     # add your ANTHROPIC_API_KEY + MCP creds
cp config/store.example.yaml config/store.yaml   # describe the store

# Run a single task through the master agent:
python run.py "Audit conversion and tell me the top 3 fixes"

# Or an interactive session:
python run.py
```

## How it works

- `run.py` — CLI entry point. Loads the store config, builds the company, sends
  your task to the **master agent**.
- The master agent has the specialized agents registered as **subagents**. It
  decides which to delegate to, reviews their output, and reports back. It never
  spends money or publishes changes without surfacing it to you first.
- Each agent's behavior is a Markdown prompt in `src/company/prompts/`, with
  the per-store profile injected at runtime. Edit prompts without touching code.

## Adding a new agent (the "general" part)

1. Drop a prompt file in `src/company/prompts/<name>.md`.
2. Register it in `src/company/agents.py` (one `AgentSpec` entry: description,
   prompt file, allowed tools, model).
3. The master can now delegate to it. No orchestration code to rewrite.

## Tools / MCP

Agents reach the outside world through MCP servers configured in
`src/company/mcp_servers.py`, populated from `.env`. Defaults wire up Shopify;
ad-research and ad-platform servers are included as commented templates so any
store can enable what it has.

## Safety model

- **Read-by-default.** Agents that can mutate (publish copy, change price, spend)
  require explicit allow-listing per agent in `agents.py`.
- **Human-in-the-loop on money and brand.** The master is instructed to propose,
  not execute, anything irreversible — and to ask before acting on ambiguity.

See `docs/ARCHITECTURE.md` for the full design.
