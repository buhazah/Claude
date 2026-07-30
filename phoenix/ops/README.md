# Phoenix Ops

The tool we use to run the first ten clients. Not a product, not a portal —
nobody outside the team ever sees it.

```bash
make install
make run          # http://127.0.0.1:8900
make check        # lint, format, 58 tests
```

## What it does

| Page | For |
|---|---|
| **Today** | What needs attention, findings that cleared the rule of three, where the time went |
| **Clients** | The pipeline. One table, `prospect → conversation → audit → active` |
| **Client** | Log a conversation verbatim, capture evidence, set the next action, see the whole timeline |
| **Evidence** | Everything customers said, grouped. Findings first, then two-client clusters, then the raw list |
| **Tasks** | Open work. Completing a task records the minutes — there is no separate time log |
| **Search** | One box across clients, conversations, evidence and tasks |

Read-only JSON at `/api/attention`, `/api/findings`, `/api/health` for scripts.

## Three decisions worth knowing

**A completed task is the effort-ledger entry.** They were separate in the plan.
Collapsing them means the ledger fills itself while you work instead of being a
second admin job — the only version of a time log that survives a busy fortnight.
Minutes and an A/B/C category are recorded at completion, and only category B is
ever sorted by hours for automation.

**Evidence is stored verbatim and categorised only coarsely.** Paraphrasing at
capture destroys the language, and the language is what goes on the website.
Grouping happens later, over the raw text.

**The attention list is rules, not judgement.** An overdue next action, a
conversation with no next step, a paying client gone quiet, an audit past day
five with no reconciliation recorded. The same list until something actually
changes, which is the only kind of list anyone keeps reading.

## What it deliberately is not

No customer portal. No authentication — it runs on a laptop or behind a VPN, and
adding auth for two users would be the first thing to maintain and the last thing
to need. No migrations: `create_all` on startup, SQLite on disk. No async, no
build step, no JavaScript.

All of that is reversible in an afternoon when a real deficiency says so.

## Where the design comes from

`docs/11-FIRST-TEN.md` (delivery), `docs/12-FOUNDER-LED-ACQUISITION.md`
(acquisition and the learning system), `CHARTER.md` (what the company is).

Those documents are frozen — [ADR 0010](../docs/adr/0010-architecture-is-frozen.md).
When this tool needs something they did not anticipate, that goes in
`docs/DEFICIENCIES.md` with a client's name on it, not into a new design.
