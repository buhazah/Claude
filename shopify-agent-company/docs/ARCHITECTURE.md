# Architecture

## One sentence
A **master agent** receives a task, delegates to **specialized subagents** that
each hold one job and one tool-set, reviews their output against per-store rules,
and returns a single decision — for **any** Shopify store, configured by YAML.

## Components

| File | Role |
|------|------|
| `run.py` | CLI. Loads config, builds the company, sends a task to the master. |
| `src/company/settings.py` | Loads `.env` + `config/store.yaml`. Renders prompt blocks. |
| `src/company/agents.py` | The agent **registry** — add an agent here, nothing else. |
| `src/company/master.py` | Assembles `ClaudeAgentOptions` (master + subagents + MCP). |
| `src/company/mcp_servers.py` | Wires each store's Shopify / research / ad MCP endpoints. |
| `src/company/prompts/*.md` | Each agent's behavior. Edit without touching code. |
| `config/store.yaml` | The only place a specific store is described. |

## Request flow

```
owner task ──> run.py ──> master agent
                              │  (reads store profile + rules from config)
                              ├── Task: store    ──> Shopify read tools ──┐
                              ├── Task: creative ──> brand-voice copy   ──┤
                              ├── Task: scout    ──> research tools      ─┤
                              └── Task: finance  ──> margin math         ─┘
                              │
                       reviews vs rules, synthesizes
                              │
                         decision ──> owner   (stops before anything irreversible)
```

## Why it generalizes
- **No store data in code.** Brand voice, margins, and rules live in YAML. Run
  against ten stores with ten config files and the same package.
- **Agents are declarative.** An `AgentSpec` (name, prompt, tools, model) plus a
  Markdown prompt = a new department. The master discovers it via the roster it's
  given at build time.
- **Tools are per-store and per-agent.** MCP endpoints come from `.env`; each
  agent only receives the tools its `AgentSpec` lists.

## Safety
- Mutation tools (`update-product`, etc.) are stripped from any agent whose
  `AgentSpec.can_mutate` is `False` (the default today).
- The master prompt forbids spending money or publishing changes without owner
  approval, and forbids fabricating data.

## Extending
- **New agent:** add an `AgentSpec` + a prompt file. (e.g. Support, Ads Buyer.)
- **New tool backend:** add an MCP server in `mcp_servers.py` keyed by name, and
  reference its tools as `mcp__<key>__<tool>` in an `AgentSpec`.
- **Always-on:** wrap `run.py` in cron or a queue worker to run scheduled tasks
  (daily conversion audit, weekly scout) without a human present.
