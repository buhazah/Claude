# Jarvis — Interface Design

## Language

Dark-first, near-black canvas (`#08090B`) with layered elevation instead of
borders. One accent (electric cyan `#5EE7FF`) used sparingly for live state
and focus. Glass is used **only** for floating surfaces (command palette,
chat dock, toasts) — never for static panels, where it reads as noise.

- **Type** — Inter Variable for UI (tight tracking on headings, `-0.02em`),
  JetBrains Mono for code, tokens, and metrics.
- **Space** — 8px base. Page gutters 32/48px. Cards breathe: 20–24px padding.
- **Motion** — spring (`stiffness 260, damping 30`) for anything positional;
  120–180ms opacity fades. Streaming text never re-layouts; it grows into
  reserved space.
- **Radius** — 14px cards, 10px controls, 20px floating surfaces.
- **Zero chrome** — no page titles that repeat the nav, no breadcrumbs, no
  admin-panel tables. Density comes from typography, not lines.

## Frames

```
┌──────────┬──────────────────────────────────────────────┬───────────┐
│          │  Good evening.                          ⌘K   │           │
│  ◈ Jarvis│  ─────────────────────────────────────────   │  Live     │
│          │  ┌──────── Today's focus ────────┐ ┌───────┐ │  activity │
│  Home    │  │ 3 things that matter          │ │Goals  │ │  ────────  │
│  Chat    │  │ ● Ship M2  ● Call R.  ● Draft │ │ ▓▓▓░  │ │  ▸ research│
│  Agents  │  └───────────────────────────────┘ └───────┘ │    agent   │
│  Memory  │  ┌ Projects ─────┐ ┌ Automations ───────────┐│    ● 12s   │
│  Runs    │  │ ● healthy     │ │ inbox-triage  running  ││  ▸ memory  │
│  Tools   │  │ ▲ at risk     │ │ weekly-report queued   ││    wrote 4 │
│  Docs    │  └───────────────┘ └───────────────────────┘│           │
│          │                                              │           │
│  ⏺ voice │              ┌─ floating chat dock ─┐        │           │
└──────────┴──────────────└──────────────────────┘────────┴───────────┘
```

**Command palette (⌘K)** — the primary interface. Typing a natural-language
intent shows the agents Jarvis would activate, with confidence, *before* you
commit. `⏎` executes, `⇧⏎` plans first.

```
        ╭──────────────────────────────────────────────────╮
        │ ⌘  research competitors for my supplement brand  │
        ├──────────────────────────────────────────────────┤
        │ ⚡ Execute                                        │
        │    Research Agent  0.91  ▸ Data Analyst  0.44    │
        │ ◷ Plan first                             ⇧⏎      │
        ├──────────────────────────────────────────────────┤
        │ Recent · Memory · Projects · Agents · Automations│
        ╰──────────────────────────────────────────────────╯
```

**Run timeline** — each run is a vertical stream of steps: agent thought
summaries collapsed by default, tool calls with argument diffs, approvals
inline, cost and token counters ticking live. Reads like a transcript, not a
log table.

**Agent grid** — one card per agent: sparkline of recent confidence, success
rate, p95 latency, cost-to-date, and its tool allowlist as chips.

## Keyboard

`⌘K` palette · `⌘J` chat dock · `⌘⇧V` voice · `⌘1..7` sections ·
`⌘⏎` send · `Esc` dismiss/interrupt · `/` focus filter · `G then H/A/M/R`
jump.

## States

Every surface defines four: loading (skeletons that match final geometry, no
spinners), empty (a sentence and one action), streaming (accent pulse), and
error (plain language, one retry). Nothing renders a bare `null`.
