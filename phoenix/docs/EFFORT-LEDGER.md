# Effort ledger

Every human minute spent on a client. The most valuable artefact of the first
ninety days, and it is a table.

Process in [`11-FIRST-TEN.md §7`](11-FIRST-TEN.md).

---

## Why this exists

After 90 days, sort **category B** by total hours descending. That list is the
automation backlog — derived from where time actually went rather than from where
anyone expected it to go.

Category A is not on the backlog at all until the learning is banked. Category C
waits for measured evidence.

## The three categories

| | Meaning | Automate? |
|---|---|---|
| **A** | **Manual because it is the instrument.** Doing it by hand is how we learn what the system should do | **No.** Automating it early destroys the reason for this phase |
| **B** | **Manual because it is cheap at ten clients.** Ordinary work with no learning value | **Yes, eventually** — in hours-descending order |
| **C** | **Manual because automating it now would be reckless.** Touches a client's account, or sends without review | **Only on evidence**, per ADR 0005 |

## Recording

One row per session of work. Round to five minutes; precision beyond that is
false and slows recording down, which is how ledgers die.

| Date | Client | Minutes | Category | Activity | Note |
|---|---|---|---|---|---|
| | | | | | |

**Activity vocabulary** — keep it short, or it gets used carelessly:

```
onboarding · access_setup · reconciliation_fix · discovery
diagnosis_review · creative_review · recommendation_ranking
report_edit · client_call · client_email · firefighting
provisioning · admin · unplanned
```

`firefighting` and `unplanned` are the two worth watching. A rising share of
either means the system is generating work rather than absorbing it, and that
shows up here weeks before it shows up in a margin.

## Weekly roll-up

| Week | Client | Total min | A | B | C |
|---|---|---|---|---|---|
| | | | | | |

## The two questions it answers

**Is human time per client falling?** Compare week 4 for client 1 against week 4
for client 8. Falling means the process is learning; flat means we are hiring
rather than building.

**Is it flat against account size?** Plot minutes against the client's monthly
spend. Time that scales with account size caps the company at whatever the
founder can personally watch — `07-RISKS.md` R6, and the metric that fires it.
