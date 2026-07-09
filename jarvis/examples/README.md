# Examples

Curated sample data and automations for JARVIS.

## Seed everything at once
```bash
cd jarvis
python scripts/seed_examples.py
```
Creates a demo user (`demo@jarvis.local` / `demopassword123`) with:
- **10 example memories** — profile, business, goals, preferences, a
  relationship, a past decision, and a lesson learned.
- **1 project** ("JARVIS Launch") with **5 tasks** across the Kanban columns,
  each assigned to a specialist agent.
- **3 automations** — a morning briefing, a weekly business review, and a
  competitor watch.

Log in with the demo credentials to explore a populated system.

## Files
- `sample_workflows.json` — six ready-to-use automation definitions with cron
  schedules. Post any of them to `POST /api/workflows`.

## Example agents
All 23 specialized agents ship built-in and are listed at `GET /api/agents`:
CEO, Executive Assistant, Research, Coding, Marketing, Sales, Legal, Finance,
Writing, Social Media, Customer Support, Data Analyst, Automation, Travel,
Health, Fitness, Learning, Project Manager, Meeting Assistant, Creative
Designer, Image Prompt Engineer, Video Script Writer, and Prompt Engineer.

## Example prompts to try
- "Research the top 3 AI note-taking apps and draft a positioning statement
  that differentiates mine." *(orchestrator → research + marketing)*
- "Write a Python script that renames every file in a folder to snake_case,
  then run it on a test folder." *(coding agent, uses tools)*
- "Plan a 3-day trip to Lisbon on a $1,200 budget." *(travel planner)*
- "Remember that I ship product updates every other Friday." *(stored as a
  memory and recalled later)*
