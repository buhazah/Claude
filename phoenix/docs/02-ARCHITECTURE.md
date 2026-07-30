# Phoenix — System Architecture

---

## 1. The one idea

Everything below is a consequence of a single rule:

> **AI proposes. Deterministic code disposes.**

No model output ever mutates external state. A model produces a *proposal* — a
typed, validated object — and deterministic code decides whether to accept it,
clamp it, or reject it. Budgets, limits, schedules, retries and reconciliation
are code. Research, strategy, creative, diagnosis and prose are models.

This is the brief's own philosophy, sharpened into something testable: it makes
every AI output an object with a schema, a validator, and an audit row, and it
means the blast radius of a hallucination is a rejected proposal rather than a
£4,000 budget change.

See [ADR 0002](adr/0002-ai-proposes-code-disposes.md).

## 2. Topology

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CONTROL PLANE  (the agency)                                             │
│                                                                          │
│  Tenancy · Billing · Mandate registry · Human console · Fleet scheduler  │
│  Knowledge exchange (anonymised, one-way in)                             │
│                                                                          │
│  Postgres (agency)              never holds client ad data               │
└───────────────┬──────────────────────────────────────────────────────────┘
                │  provisions · schedules · collects
    ┌───────────┼───────────┬───────────────┐
    ▼           ▼           ▼               ▼
┌────────┐  ┌────────┐  ┌────────┐     ┌────────┐
│ CLIENT │  │ CLIENT │  │ CLIENT │ ... │ CLIENT │      one per tenant
│   A    │  │   B    │  │   C    │     │   N    │
│        │  │        │  │        │     │        │
│ Jarvis Core + Phoenix departments                 │
│ own Postgres · own vault · own memory · own audit │
└────┬───┘  └────────┘  └────────┘     └────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  INTEGRATION PLANE   Meta Marketing · Shopify · Stripe · GA4 · creative  │
│  All behind ports. All idempotent. All rate-limited per tenant.          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Why a control plane and isolated tenants:** Jarvis Core is single-principal by
design (`jarvis/docs/ARCHITECTURE.md §7`). Isolation by database is the only
kind a customer's counsel believes, and it makes the confidentiality story for
cross-client learning trivially defensible: knowledge flows *up*, anonymised,
never sideways. Full reasoning in [ADR 0001](adr/0001-control-plane-and-isolated-tenants.md).

## 3. What Jarvis Core already supplies

Phoenix is an application on a platform, not a fork. What it inherits:

| Need | Jarvis Core provides |
|---|---|
| Durable, resumable lifecycles | Workflow engine with suspension surviving restart (ADR 0007) |
| Departments as configuration | Agents-as-data + modes as narrowings (ADR 0002, 0010) |
| Permissioned external action | Tool registry, tiers, approval gate, hash-chained audit (ADR 0005) |
| Connectors | MCP client — each server mounts as a tool namespace |
| Spend control | Cost governor, checked *before* each call (ADR 0011) |
| Secret handling | Vault with redaction across logs, events, audit |
| Long-term memory | Tiered store + hybrid recall + Obsidian (ADR 0013) |
| Proactive work | Recommendation engine, ranked by arithmetic (ADR 0014) |
| Knowing if it works | 288-case evaluation corpus with baselines (ADR 0015) |
| Offline determinism | Echo provider; whole system runs with no keys (ADR 0001) |

**What it does not supply, and Phoenix must build:**

- multi-tenancy and RBAC → **control plane**
- OAuth token lifecycle for third-party accounts (Meta tokens expire)
- webhook ingestion
- time-series metric storage and rollups
- a financial ledger (spend, margin, invoicing)
- per-tenant fleet scheduling
- reconciliation of external state drift

## 4. The spine: Signal → Decision → Outcome

The most important structure in Phoenix. Every automated action passes through
it, and it is the same shape as a trading desk: signal, order, risk check,
execution, fill, attribution.

```
   Metrics ingest (deterministic, scheduled)
        │
        ▼
   SIGNAL           threshold crossed, anomaly, fatigue curve, budget pacing
        │           deterministic detectors — no model
        ▼
   DIAGNOSIS        why did this happen?
        │           AI, grounded in the metric snapshots it is handed
        ▼
   PROPOSAL         typed: {action, target, magnitude, rationale, evidence,
        │           expected_effect, confidence}
        ▼
   MANDATE CHECK    deterministic. accept / clamp / reject / escalate
        │           cannot be argued with, cannot be prompted around
        ▼
   DECISION         persisted: approved | auto | rejected | escalated
        │
        ▼
   ACTION           idempotent external write, retry-safe
        │
        ▼
   OUTCOME          measured 7/14/28 days later against the expected effect
        │
        ▼
   KNOWLEDGE        was the diagnosis right? was the proposal right?
```

Seven tables and one rule. It buys, simultaneously:

- **explainability** — every change has a signal, a rationale, and an actor
- **safety** — the mandate check is deterministic code between AI and money
- **shadow mode** — stop after DECISION and record; execute nothing
- **evaluation** — OUTCOME versus expected effect is a labelled dataset,
  generated by operating
- **learning** — proposals that worked are evidence; proposals that did not are
  better evidence

Detail in `03-AUTONOMY.md`.

## 5. Service boundaries

Seven services inside each client instance, each independently testable, each
behind a port.

### 5.1 Ingest
Pulls Meta insights, Shopify orders, Stripe charges, GA4. Normalises to one
schema. Idempotent by `(entity, date, breakdown)`. Owns rate limiting and
backoff. **No AI.**

The hardest part is not fetching — it is that Meta restates historical data for
up to ~28 days as attribution windows resolve. Snapshots are therefore
append-only with an `as_of` date, and any figure quoted to a customer carries
the date it was true.

### 5.2 Truth
Reconciles platform-reported conversions against store-recorded orders.
Produces blended CAC, contribution margin, and a **reconciliation confidence**
that gates everything downstream. **No AI.**

This is the service most agencies do not have and the reason their numbers are
wrong. It is also entirely deterministic, which makes it cheap to get right and
cheap to test.

### 5.3 Signals
Scheduled detectors over the metric store: fatigue (frequency and CTR decay),
pacing (spend versus plan), anomalies (statistically significant movement, not
"CPA went up"), budget concentration, policy warnings. **No AI.**

Deliberately no AI: a signal is a threshold, and a model asked "is this
anomalous" gives a different answer on different days.

### 5.4 Creative
Brief → concept → asset generation → variant assembly → internal scoring →
review queue. Heavily AI. Every output is an artefact with lineage: which
brief, which angle, which hypothesis, which prior winner it derives from.

Scoring before human review is a *filter*, not a judgement — it removes the
obviously broken (wrong aspect ratio, banned claim, off-brand palette) so the
human reviews twenty candidates instead of two hundred.

### 5.5 Decisions
Diagnosis (AI) → proposal (AI, typed) → mandate check (code) → decision record.
The mandate check is the safety boundary and it is pure, synchronous,
side-effect-free code with exhaustive tests.

### 5.6 Actuation
The only service that writes to Meta. Idempotency keys, retries with backoff,
reconciliation of desired versus actual, drift detection. **No AI.**

Isolating this means the number of code paths that can spend money is one, and
it can be tested in isolation against a recorded API.

### 5.7 Narrative
Reports, briefings, client comms, the monthly review. AI writes the prose; every
number is passed in, never generated. Same rule as the Jarvis briefing, where
the model writes two sentences and the arithmetic decides everything else — and
where the echo provider's output had to be explicitly rejected because it was
short and plausible enough to pass every other guard.

## 6. Departments map onto services

Departments are the customer-facing metaphor and the configuration namespace.
They are not processes.

```
Department              →  Service            →  Jarvis mechanism
──────────────────────────────────────────────────────────────────────
Market Research         →  Creative (input)   →  agent + web/knowledge tools
Audience Intelligence   →  Creative (input)   →  agent + memory scope
Creative Strategy       →  Creative           →  agent + brief workflow
Creative Studio         →  Creative           →  agent + generation tools
Copywriting             →  Creative           →  agent (temp 0.85)
Media Buying            →  Decisions          →  agent + mandate check
Campaign Operations     →  Actuation          →  workflow, no agent
Performance Analysis    →  Decisions          →  agent grounded in snapshots
Creative Analytics      →  Signals            →  deterministic, no agent
Reporting               →  Narrative          →  document composer
Finance                 →  Truth              →  deterministic, no agent
Compliance              →  Decisions (gate)   →  deterministic rules + agent
Knowledge Management    →  all                →  Obsidian memory
Continuous Learning     →  all                →  outcome scoring
Quality Assurance       →  all                →  evaluation corpus
Executive Office        →  Narrative          →  recommendation engine
Client Success          →  Narrative          →  agent + comms
```

**Note what happened:** Campaign Operations, Creative Analytics and Finance have
no agent at all. They are scheduled deterministic functions. Three of the
brief's twenty-one departments are better as code, and saying so is the point
of the exercise.

Full definitions in `04-DEPARTMENTS.md`.

## 7. Data model

Core entities. Client-instance database unless marked *(control plane)*.

**Identity and authority**
```
Tenant            (control plane)  id, name, plan, state
Mandate           (control plane)  tenant, scope, limits, granted_by, expires_at,
                                   revoked_at, version
Connection                         provider, external_account_id, token_ref (vault),
                                   scopes, expires_at, health
```

**The advertising graph** — mirrored external state plus our intent
```
AdAccount                          external_id, currency, timezone, spend_cap
Campaign                           external_id, objective, status, our_intent,
                                   strategy_id, last_reconciled_at
AdSet                              external_id, campaign, budget, targeting_hash
Ad                                 external_id, adset, creative_id, status
```
`our_intent` versus `status` is the drift detector: what we asked for versus
what Meta reports.

**Creative**
```
Brief                              hypothesis, angle, audience, format, constraints
Concept                            brief, angle, hook, rationale
Asset                              concept, kind, uri, provider, cost, checksum
Variant                            asset + copy + format, lineage[], approval_state
```
`lineage` is what makes creative learning possible: this variant descends from
that winner, changing this one variable.

**Measurement**
```
MetricSnapshot                     entity, date, as_of, breakdown, impressions,
                                   spend, clicks, conversions, revenue
StoreOrder                         external_id, at, revenue, cogs, new_customer,
                                   attributed_source
Reconciliation                     period, platform_conv, store_conv, delta,
                                   confidence, method
```

**The spine**
```
Signal                             kind, entity, observed, threshold, severity
Diagnosis                          signal[], hypothesis, evidence[], confidence
Proposal                           diagnosis, action, target, magnitude,
                                   expected_effect, confidence
Decision                           proposal, verdict, mandate_version, actor,
                                   clamped_from
Action                             decision, idempotency_key, request, response,
                                   attempts, state
Outcome                            decision, horizon, expected, actual, verdict
```

**Learning**
```
KnowledgeCard                      claim, evidence[], scope, confidence,
                                   supersedes, tenant_visible
Experiment                         hypothesis, design, holdout, result, power
```

Knowledge cards are the only thing that crosses the tenant boundary, and only
upward, only anonymised, only with the tenant's contractual permission.

## 8. Events

Phoenix publishes onto the Jarvis bus. Hierarchical topics, existing
subscribers.

```
ingest.completed          tenant, source, entities, as_of
truth.reconciled          tenant, period, confidence
signal.raised             tenant, kind, entity, severity
diagnosis.formed          tenant, signal[], confidence
proposal.made             tenant, action, magnitude
decision.recorded         tenant, verdict, mandate_version
decision.escalated        tenant, reason              → human console
action.executed           tenant, external_id, attempts
action.failed             tenant, error, will_retry
action.drifted            tenant, expected, actual    → reconciliation
outcome.measured          tenant, verdict, delta
mandate.breached          tenant, attempted, limit    → page a human
creative.shipped          tenant, variant, campaign
knowledge.published       card, scope
```

`mandate.breached` should never fire. If it does, something bypassed the check,
and that is a P0.

## 9. Memory

Three tiers, mapped to Jarvis's existing scoping.

**Tenant memory** — everything about one client, in their instance, in their
Obsidian vault. Brand rules, offer economics, what has been tried, what worked.
Never leaves.

**Agency memory** — cross-client, in the control plane. Only knowledge cards:
anonymised, structured claims with evidence and confidence. *"Hook framing X
beat control in 7 of 9 tests across 4 apparel brands, mean lift 14%, CI
±6%."* Never raw creative, never client names, never account data.

**Model memory** — none. Nothing is fine-tuned on client data in v1. It removes
an entire class of leakage and compliance argument for a benefit we have not
demonstrated we need.

**Why knowledge cards rather than "store winning creatives":** three failure
modes the naive version has. *Confidentiality* — a winning ad is the client's
IP. *Transfer* — what works for supplements does not work for furniture, and a
memory that does not carry its scope will be recalled where it does not apply.
*Survivorship* — storing only winners teaches nothing; the failures carry more
information and cost the same to store.

## 10. Integrations

Official APIs, always. Browser automation only where no API exists, and never
for anything that spends money.

| Integration | Direction | Criticality | Notes |
|---|---|---|---|
| Meta Marketing API | R/W | **Critical path** | App review + business verification. Start day one. Rate limits are tiered — confirm current terms. |
| Meta Conversions API | W | Critical | Server-side signal. Post-ATT this is not optional. |
| Shopify Admin | R | Critical | Revenue truth |
| Stripe | R | High | Where Shopify is not the processor |
| GA4 | R | Medium | Corroboration, not truth |
| Creative generation | W | High | Multiple providers behind one port — terms and quality both move |
| Obsidian | R/W | Medium | Already a Jarvis adapter |
| Slack / email | W | Medium | Escalation and reports |

**Token lifecycle is a real subsystem, not a config field.** Meta tokens expire,
get revoked when a user leaves the business, and fail in ways that look like
rate limits. A dead connection must degrade that capability loudly, surface in
the client's console, and never silently produce stale numbers.

**Every integration is a port with a recorded-fixture implementation.** The
whole system runs offline against recorded API responses, which is Jarvis's
existing offline-determinism requirement applied to third parties.

## 11. Security

Inherits Jarvis's posture, plus what multi-tenancy demands.

- **Isolation by database.** Not by query filter.
- **Secrets in the vault.** Meta tokens are `${vault:meta.<tenant>}`; the model
  names them and never holds them; resolved in the tool registry after the
  audit write.
- **The mandate is enforced in code**, before actuation, in one place, with
  exhaustive tests. It is not a prompt instruction. A prompt can be argued
  with; a validator cannot.
- **Audit is hash-chained** and per tenant. Every external write, every
  approval, every secret access.
- **Untrusted content.** Competitor pages, ad comments, reviews and customer
  emails are wrapped untrusted and can never elevate a permission or approve an
  action — Jarvis's existing prompt-injection posture, which matters far more
  here because the system spends money.
- **Least privilege on Meta.** Request the narrowest scopes that work. Do not
  hold billing permissions.
- **PII.** Customer lists and CAPI payloads are hashed before transmission and
  never enter a prompt.

## 12. Deployment

**Control plane** — Postgres, the console, the fleet scheduler. Small, boring,
always up.

**Client instances** — containerised Jarvis + Phoenix. One per tenant. Scheduled
work is driven by the control plane rather than by an in-process loop per
container, so a sleeping tenant costs nothing.

**Environments** — dev (recorded fixtures, no network), staging (Meta sandbox +
one real low-spend account), production.

**Migrations** — Alembic, per tenant, applied by the control plane in a rollout
with a canary tenant first.

**Observability** — the Jarvis event bus is already the substrate. What
Phoenix adds: spend per tenant per day, decision latency, mandate-check reject
rate, drift count, reconciliation confidence, AI cost per client. The last two
are the health metrics nobody thinks to add and everybody needs.

## 13. Deliberately not built in v1

- Multi-touch attribution modelling — expensive, contested, and holdout tests
  answer the real question better
- Fine-tuning on client data
- Google/TikTok/LinkedIn — the wedge is Meta; breadth after depth
- Self-serve onboarding
- A creative asset marketplace
- Real-time bidding intervention — Meta's job, and we would lose
