# Phoenix — Department design

A department is **a namespace, not a process**. Concretely, in Jarvis terms:

```
department = a Jarvis mode
           + a set of AgentSpecs
           + a memory scope
           + a set of tools
           + an evaluation suite
           + a decision boundary
```

It reuses machinery that already exists and is tested. Modes narrow (ADR 0010:
a mode can only ever subtract), memory scopes isolate, agent specs are data,
and every department gets its own slice of the evaluation corpus.

**What a department is not:** a running service, a message queue participant, or
something that talks to other departments. Work moves through the durable
workflow spine in `02-ARCHITECTURE.md §4`. Departments supply capability to it.

**Three of the brief's departments have no agent at all.** They are scheduled
deterministic functions, and saying so is the most useful thing this document
does.

**No department names a channel.** Departments operate on the neutral entity
graph and propose in neutral verbs (`02-ARCHITECTURE.md §5`); only the adapter
below the port knows what Meta calls things. A department that would need
rewriting for Google Ads is a department that has leaked.

---

## Reading the tables

Every department declares the same seven things. `Boundary` is the important
one: what it may decide alone, and what it must hand upward.

---

## Executive Office

| | |
|---|---|
| **Mission** | Own the client relationship's direction. Decide what matters this month. |
| **Responsibilities** | Monthly business review, mandate renewal, escalation triage, strategic recommendation |
| **KPIs** | Client retention, mandate renewal rate, escalation resolution time |
| **Inputs** | Reconciled performance, decision ledger, client goals, knowledge cards |
| **Outputs** | Monthly review, mandate proposal, one strategic recommendation |
| **Tools** | `memory_search`, `search_documents`, report composer |
| **Memory** | `tenant:executive` |
| **Boundary** | May recommend anything. May decide nothing that costs money. Mandate changes always go to the human. |
| **Escalates** | Client dissatisfaction, retention risk, anything requiring renegotiation |
| **Evaluation** | Does the review lead with the right thing? Human-scored, unscored corpus. |

Built on Jarvis's recommendation engine and briefing composer — arithmetic
ranks, a model phrases.

## Operations

| | |
|---|---|
| **Mission** | Keep the machine running. Nothing silently broken. |
| **Responsibilities** | Connection health, token refresh, ingest monitoring, drift reconciliation, SLA tracking |
| **KPIs** | Ingest freshness, connection uptime, unresolved drift count, time-to-detect |
| **Inputs** | Integration health, job outcomes, event bus |
| **Outputs** | Health state, incidents, escalations |
| **Tools** | Deterministic monitors |
| **Memory** | none — state, not memory |
| **Boundary** | May retry, back off, degrade. May not act on ads. |
| **Escalates** | Dead connection >2h, ingest stale >24h, any drift it cannot explain |
| **Evaluation** | Detection latency; false-negative rate on injected faults |

**No agent.** A monitor with thresholds. An LLM asked "is the ingest healthy"
gives a different answer on different days, which is the opposite of what
monitoring is for.

## Client Success

| | |
|---|---|
| **Mission** | The client always knows what is happening and never has to ask. |
| **Responsibilities** | Weekly report delivery, recommendation-queue delivery and follow-up, inbound questions, expectation setting, onboarding shepherding |
| **KPIs** | Response time, report open rate, satisfaction, questions-per-week (falling is good) |
| **Inputs** | Reports, decision ledger, client history |
| **Outputs** | Client comms, meeting notes, logged expectations |
| **Tools** | `memory_search`, email, report reader |
| **Memory** | `tenant:client_success` |
| **Boundary** | May explain anything already decided. May not promise, commit to a target, or change a mandate. |
| **Escalates** | Any dissatisfaction, any request outside the mandate, any question about money |
| **Evaluation** | Answer accuracy against ledger — is what it said what happened? |

The failure mode is an agent that reassures. Every claim must trace to the
ledger, and "I don't know, I'll find out" is a correct answer.

## Business Strategy

| | |
|---|---|
| **Mission** | Turn a business into a set of testable advertising hypotheses. |
| **Responsibilities** | Discovery, offer analysis, unit economics, positioning, quarterly strategy |
| **KPIs** | Hypothesis win rate, share of spend against a stated hypothesis |
| **Inputs** | Discovery interview, store data, margins, competitor research, history |
| **Outputs** | Strategy doc: hypotheses, each with a test, a threshold, and a kill condition |
| **Tools** | `search_documents`, `memory_search`, spreadsheet |
| **Memory** | `tenant:strategy` |
| **Boundary** | May propose strategy. May not change offer or pricing — always the client's. |
| **Escalates** | Unit economics that do not support the target CAC. Loudly, immediately. |
| **Evaluation** | Do hypotheses resolve? Unresolved after 60 days counts as a failure. |

**A strategy without a kill condition is a wish.** Every hypothesis carries what
would falsify it and by when.

## Market Research · Audience Intelligence

| | |
|---|---|
| **Mission** | Know the market and the buyer better than the client does. |
| **Responsibilities** | Competitor ad analysis, category trends, segment definition, angle mining from reviews and comments |
| **KPIs** | Insights that become tested angles; angle win rate |
| **Inputs** | Ad libraries, competitor sites, reviews, store data, search trends |
| **Outputs** | Research briefs with citations; audience and angle definitions |
| **Tools** | `fetch_url`, browser, `search_documents`, `memory_write` |
| **Memory** | `tenant:research` |
| **Boundary** | May research and assert with evidence. May not target — that is Media Buying. |
| **Escalates** | Competitor claims that are legally risky to mirror |
| **Evaluation** | Citation validity; does the source say what the brief says it says? |

Every non-obvious claim carries a citation — Jarvis's structural-citation
mechanism (ADR 0006), where the locator survives from extraction to output.
Scraped content is **untrusted**: a competitor page cannot instruct anything.

## Creative Strategy · Creative Studio · Copywriting

The engine room. Three departments, one pipeline.

| | |
|---|---|
| **Mission** | Ship 30–50 tested, on-brand variants a month, each testing something. |
| **Responsibilities** | Briefs, concepts, assets, copy, variant assembly, internal filtering |
| **KPIs** | Variants shipped, win rate (>15%), cost per variant, brand-violation rate (zero) |
| **Inputs** | Strategy hypotheses, research angles, winners' lineage, brand rules |
| **Outputs** | Briefs → concepts → assets → variants → per-channel renditions, each with lineage |
| **Tools** | Image/video generation, `memory_search`, brand-rule validator |
| **Memory** | `tenant:creative` |
| **Boundary** | May generate anything as a **draft**. May not publish. Never autonomous past the review queue in v1. |
| **Escalates** | Any claim needing substantiation; any third-party IP; anything the brand validator rejects |
| **Evaluation** | Human review pass rate; live win rate; brand violations (must be zero) |

Three points that make or break this:

**Every variant tests one thing.** Lineage records the parent and the changed
variable. Fifty random variants teach nothing; fifty variants each changing one
element against a control teach a great deal.

**Internal scoring is a filter, not a judge.** It removes the mechanically
broken — wrong ratio, banned claim, off-palette, text-heavy — so the human
reviews twenty candidates rather than two hundred. It does not predict
performance, because nothing does.

**Brand rules are deterministic.** Palette, logo, banned words, required
disclaimers: a validator, not a prompt. A prompt can be talked out of it.

## Media Buying · Campaign Operations

| | |
|---|---|
| **Mission** | Structure and run accounts so the platform's algorithm can do its job. |
| **Responsibilities** | Program structure, budget allocation, launch, pacing, scaling |
| **KPIs** | CAC vs target, pacing accuracy, launch latency, mandate breaches (zero), recommendation adoption |
| **Inputs** | Strategy, approved creative, mandate, capabilities, performance |
| **Outputs** | Proposals → decisions → actions **or** delivered recommendations |
| **Tools** | The channel port, via Actuation only |
| **Memory** | `tenant:media` |
| **Boundary** | Everything through the mandate check. No adapter access from the agent — proposals only, in neutral verbs. |
| **Escalates** | Anything outside the mandate; anything the reconciler flags |
| **Evaluation** | Proposal accuracy at tiers 0/R; outcome verdicts; recommendation clarity |

**Campaign Operations has no agent.** Launch, pacing checks and reconciliation
are a deterministic workflow. Media Buying proposes; Operations executes *or*
delivers, depending on the connection's capabilities; the mandate check sits
between them.

**This department is one capability, not the product.** It is the stage the
brief was most excited about and the stage where the least defensible value
sits — see `00-STRATEGY.md §3`. It proposes in channel-neutral verbs
(`shift_budget`, `set_status`), which is what lets the same agent, the same
prompts and the same evaluation cases work against a channel that does not exist
yet.

Do not over-structure accounts. Modern platform algorithms perform better with
consolidated spend than with the fifteen-ad-set structures agencies built in
2019 to justify their retainer.

## Performance Analysis · Creative Analytics

| | |
|---|---|
| **Mission** | Explain what happened, with evidence, or say that it cannot be explained. |
| **Responsibilities** | Diagnosis, fatigue detection, cohort analysis, creative attribution |
| **KPIs** | Diagnosis accuracy scored against outcomes; time-to-detect |
| **Inputs** | Metric snapshots, reconciliation, decision ledger, creative lineage |
| **Outputs** | Signals (deterministic) → diagnoses (AI) |
| **Tools** | Query, `memory_search` |
| **Memory** | `tenant:analysis` |
| **Boundary** | May diagnose. May not act — diagnosis feeds proposals, it is not one. |
| **Escalates** | Reconciliation confidence <0.8; anything it cannot explain |
| **Evaluation** | Was the diagnosis right, judged when the outcome landed? |

**Creative Analytics has no agent.** Fatigue curves, frequency thresholds and
significance tests are statistics. A model asked "is this significant" produces
a confident answer uncorrelated with significance.

The Performance Analysis agent is grounded: it is handed the snapshots and may
only reason over them. It never queries freely and never recalls a number from
training.

## Landing Page Optimisation

| | |
|---|---|
| **Mission** | Notice when the ad is fine and the page is the problem. |
| **Responsibilities** | Funnel analysis, page-speed and mobile checks, message-match, recommendations |
| **KPIs** | Recommendations adopted; conversion-rate lift where adopted |
| **Inputs** | Store analytics, page content, ad-to-page match |
| **Outputs** | Recommendations with evidence |
| **Tools** | `fetch_url`, browser, analytics |
| **Memory** | `tenant:landing` |
| **Boundary** | **Recommend only.** Never touches the client's site. |
| **Escalates** | Tracking broken on the page — blocks everything downstream |

Advisory forever. Editing a client's storefront is a category of risk with no
upside for us.

## Reporting · Finance

| | |
|---|---|
| **Mission** | Numbers that are correct, and prose that does not oversell them. |
| **Responsibilities** | Weekly and monthly reports, spend reconciliation, margin, invoicing |
| **KPIs** | Report accuracy (zero corrections issued), delivery punctuality |
| **Inputs** | Reconciled truth, decision ledger, mandate |
| **Outputs** | Reports, invoices, margin analysis |
| **Tools** | Document composer, spreadsheet |
| **Memory** | `tenant:reporting` |
| **Boundary** | May narrate. Every number is passed in — the model computes nothing. |
| **Escalates** | Any figure it cannot reconcile |
| **Evaluation** | Do stated numbers match the source? Deterministic and mandatory. |

**Finance has no agent.** Money arithmetic is code, per the brief's own
philosophy and per Jarvis's briefing design, where a model writes two sentences
and everything else is arithmetic.

## Compliance · Quality Assurance

| | |
|---|---|
| **Mission** | Nothing ships that gets the account banned or the client sued. |
| **Responsibilities** | Ad policy pre-check, claim substantiation, IP checks, disclaimers, mandate audit |
| **KPIs** | Policy rejections (target zero), account strikes (zero), false-positive rate |
| **Inputs** | Creative, copy, category rules, client legal constraints |
| **Outputs** | Pass / block / escalate |
| **Tools** | Rule engine + a review agent |
| **Memory** | `tenant:compliance` |
| **Boundary** | **May block anything. May approve nothing on its own** in a regulated category. |
| **Escalates** | Any health, financial or income claim; any comparative claim |
| **Evaluation** | Recall on a corpus of known-violating ads. Precision matters less than recall. |

Deliberately asymmetric: blocking costs a delay, missing costs an account. A
banned ad account can end a client relationship in an afternoon and cannot be
appealed on our timetable.

## Knowledge Management · Continuous Learning

| | |
|---|---|
| **Mission** | The company is better at client fifty than at client five. |
| **Responsibilities** | Outcome scoring, knowledge cards, anonymised publication, contradiction detection |
| **KPIs** | Cards published; cards *used* in later briefs; win-rate trend across cohorts |
| **Inputs** | Outcomes, creative lineage, experiments, decision ledger |
| **Outputs** | Knowledge cards with evidence, scope, confidence |
| **Tools** | `memory_write`, Obsidian, statistics |
| **Memory** | `tenant:knowledge` → publishes to agency memory |
| **Boundary** | May publish anonymised claims. **May never move raw client data across the tenant boundary.** |
| **Escalates** | A new card contradicting an established one |
| **Evaluation** | Do cards predict? A card that never changes a decision is noise. |

Three disciplines that separate this from a folder of "insights":

**Scope is part of the claim.** *"Hook framing X beat control in 7 of 9 tests
across 4 apparel brands, £20–60 AOV"* — not *"question hooks work."* A claim
without scope will be recalled where it does not apply, which is worse than no
claim.

**Failures are stored.** They cost the same and carry more information.
Storing only winners is survivorship bias with a database.

**Contradictions surface rather than overwrite.** Two cards disagreeing is a
finding — usually that the scope on one of them is wrong.

---

## Summary: where the AI actually is

| Department | AI? | Why |
|---|---|---|
| Executive Office | prose only | Ranking is arithmetic |
| Operations | **none** | Monitoring is thresholds |
| Client Success | yes | Language, grounded in the ledger |
| Business Strategy | yes | Judgement under uncertainty |
| Market Research | yes | Synthesis across sources |
| Audience Intelligence | yes | Pattern recognition |
| Creative Strategy | yes | Ideation |
| Creative Studio | yes | Generation |
| Copywriting | yes | Language |
| Media Buying | proposals only | Judgement, gated by code |
| Campaign Operations | **none** | Execution is a workflow |
| Performance Analysis | yes | Causal reasoning over given data |
| Creative Analytics | **none** | Statistics |
| Landing Page | yes | Heuristic evaluation |
| Reporting | prose only | Numbers are computed |
| Finance | **none** | Arithmetic |
| Compliance | rules + review | Rules block, model catches the rest |
| Knowledge Mgmt | yes | Abstraction |
| QA | evaluation corpus | Measurement |

**Four of nineteen have no model at all.** Three more use one only for prose
over numbers it did not compute. That ratio is the design working.
