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
│  LEARNING PLANE  publication gate · contribution ledger · claim store    │
│                  calibration service · corpus builder      (§10, ADR 0007)│
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
│  CHANNEL PORT        one interface · declared capabilities · §5          │
│    ┌──────────┐   ┌──────────────┐   ┌──────────┐                       │
│    │   Meta   │   │ Google Ads   │   │  TikTok  │   … adapters          │
│    │  (first) │   │  (designed)  │   │(designed)│                       │
│    └──────────┘   └──────────────┘   └──────────┘                       │
├──────────────────────────────────────────────────────────────────────────┤
│  INTEGRATION PLANE   Shopify · Stripe · GA4 · CAPI · creative providers  │
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
- the **channel port** and its adapters (§5) — Jarvis has ports, not this one
- OAuth token lifecycle for third-party accounts, including capability
  re-derivation when scopes change under us
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

**Nothing in this spine names a channel.** A signal is a threshold on a
normalised metric, a proposal is a verb with a magnitude, a mandate check is
arithmetic. Meta appears in exactly one stage — `ACTION` — and only through the
port in §5.

## 5. Channels

The second most important structure, and the one that decides whether Phoenix
is a platform or a Meta tool with ambitions.

> **Meta is the first execution channel, not the foundation.** Everything that
> is not literally an API call to an ad platform is channel-neutral.

Full reasoning in [ADR 0006](adr/0006-channels-are-adapters.md). The shape:

```python
class Channel(Protocol):
    id: str                              # "meta", "google_ads", "tiktok"
    capabilities: frozenset[Capability]  # per connection, not per channel

    async def describe(self) -> ChannelSchema: ...
    async def pull(self, window: Window) -> Iterable[EntitySnapshot]: ...
    async def metrics(self, window: Window) -> Iterable[MetricSnapshot]: ...
    async def preview(self, action: Action) -> ActionPreview: ...
    async def apply(self, action: Action, *, idempotency_key: str) -> ActionResult: ...
```

### 5.1 Capabilities, not phases

A connection declares what it may do, and the declaration comes from the
permissions the client granted on **their** Business Manager:

```
read.entities        read.metrics        read.creative_library
write.budget         write.status        write.creative        write.campaign
experiment.holdout   experiment.split
```

Two clients on the same channel routinely have different capability sets. The
absence of `write.*` is **not a degraded state** — it is *recommendation mode*,
a first-class way to operate:

| Mode | Capabilities | Loop runs to | Delivered as |
|---|---|---|---|
| **Shadow** | `read.*` | Decision | nothing — internal scoring only |
| **Recommend** | `read.*` | Decision | a ranked, evidenced action list the client executes |
| **Execute** | `read.*` + `write.*` | Action | the change itself, plus the ledger entry |

All three are the same code path. Shadow and Recommend differ only in whether
the proposal is shown to the client; Recommend and Execute differ only in
whether `apply()` is called. This is why write access is a capability flag and
not a roadmap phase: there is no separate read-only build to maintain.

Outcome measurement works in all three modes, because measuring requires only
`read.metrics`. A recommendation the client executed by hand is scored exactly
like one Phoenix executed itself — which is what makes recommendation mode the
evidence trail that earns a write mandate.

### 5.2 The neutral entity graph

Four levels. Adapters map onto them and supply the display vocabulary, so the
client still reads "Ad Set" in their report while Phoenix's code, mandates and
evaluation corpus speak one language.

```
Account    →  Meta: Ad Account   Google: Customer   TikTok: Advertiser
Program    →  Meta: Campaign     Google: Campaign   TikTok: Campaign
Group      →  Meta: Ad Set       Google: Ad Group   TikTok: Ad Group
Placement  →  Meta: Ad           Google: Ad         TikTok: Ad
```

Deliberately a lowest common denominator. Where a channel has no fourth level,
or a fifth, the adapter collapses or nests, and channel-specific detail lives in
a `native` JSON column **only the adapter reads**. A `native` field appearing in
a prompt, a mandate or a report is a bug.

### 5.3 Normalised metrics with provenance

Every adapter emits the same `MetricSnapshot`: minor currency units, an `as_of`,
and a declared attribution basis (`window`, `model`, `modelled: bool`). The
Truth service will not add a modelled conversion to a deterministic one without
labelling the result — cross-channel arithmetic between incompatible bases is
refused, not silently averaged.

### 5.4 Channel-neutral actions

`shift_budget`, `set_status`, `launch_creative`, `create_program`, each with a
target entity and a magnitude. The mandate checker validates verbs and
magnitudes and has never heard of Meta. The adapter translates or refuses —
`unsupported` is a fifth verdict alongside accept, clamp, reject and escalate,
and it is recorded like the others.

Channel-specific capability that does not generalise — Advantage+ specifics,
Meta's experiment tooling, Google asset groups — is exposed as an
adapter-namespaced action (`meta.enable_advantage_plus`) that a mandate must
enumerate explicitly. Opt-in, never implicit.

### 5.5 The import rule

Strategy, research, briefs, creative and lineage, the spine, mandates,
approvals, memory, knowledge cards, workflows, reporting and evaluation import
no adapter. The composition root is the only module that knows Meta exists.

This is Jarvis Core's kernel rule, and it gets Jarvis's enforcement: a test that
walks the import graph and fails the build on a violation. That test caught a
real violation in Phase 11 when an API route imported `KnowledgeIndexer`
directly, which is the entire argument for having it.

## 6. Service boundaries

Seven services inside each client instance, each independently testable, each
behind a port. **None of them names a channel** — they call the port in §5.

### 6.1 Ingest
Pulls channel entities and metrics via `Channel.pull()` / `Channel.metrics()`,
plus store data from Shopify, Stripe and GA4. Normalises to one schema.
Idempotent by `(entity, date, breakdown)`. Owns rate limiting and backoff, per
tenant and per channel. **No AI.**

The hardest part is not fetching — it is that platforms restate historical data
as attribution windows resolve (Meta for up to ~28 days). Snapshots are
therefore append-only with an `as_of` date, and any figure quoted to a customer
carries the date it was true.

### 6.2 Truth
Reconciles platform-reported conversions against store-recorded orders.
Produces blended CAC, contribution margin, and a **reconciliation confidence**
that gates everything downstream. **No AI.**

This is the service most agencies do not have and the reason their numbers are
wrong. It is also entirely deterministic, which makes it cheap to get right and
cheap to test.

Being the one place that sees every channel's spend against one store's revenue,
Truth is also where blended CAC stops being per-channel arithmetic and becomes
the number the client actually cares about.

### 6.3 Signals
Scheduled detectors over the metric store: fatigue (frequency and CTR decay),
pacing (spend versus plan), anomalies (statistically significant movement, not
"CPA went up"), budget concentration, policy warnings. **No AI.**

Deliberately no AI: a signal is a threshold, and a model asked "is this
anomalous" gives a different answer on different days.

### 6.4 Creative
Hypothesis → brief → concept → asset generation → variant assembly → gates →
ranking → review queue. Heavily AI, and the one service where the model is doing
irreplaceable work. Every output is an artefact with lineage: which brief, which
angle, which hypothesis, which prior winner it derives from — and every shipped
variant carries a **typed, falsifiable prediction** whose rationale is the
ranking's own score decomposition rather than prose written about it afterwards.

Work is batched into **generations** shipped against a common control, with tier
allocation fixed by policy so exploration cannot be ranked out of existence
([ADR 0009](adr/0009-creative-is-a-portfolio.md)). Gates — brand, compliance,
format, distinctness, claim provenance — are deterministic and pass/fail, never
traded against expected lift.

Scoring before human review is a *filter*, not a judgement — it removes the
obviously broken (wrong aspect ratio, banned claim, off-brand palette) so the
human reviews twenty candidates instead of two hundred. It is deliberately
blocked from the explore tier, because a filter trained on past winners kills
exactly the variants whose value is looking unlike them.

Full design in `09-CREATIVE.md`.

A concept is channel-neutral; a *rendition* is not. The same concept produces a
4:5 static and a 9:16 six-second cut, and the channel adapter declares the
format matrix it accepts. Lineage tracks the concept, so a winner on one channel
is evidence for a brief on another.

### 6.5 Decisions
Diagnosis (AI) → proposal (AI, typed) → mandate check (code) → decision record.
The mandate check is the safety boundary and it is pure, synchronous,
side-effect-free code with exhaustive tests.

### 6.6 Actuation
The only service that calls `Channel.apply()`. Idempotency keys, retries with
backoff, reconciliation of desired versus actual, drift detection. **No AI.**

Isolating this means the number of code paths that can spend money is one, and
it can be tested in isolation against recorded fixtures. In recommendation mode
it is not invoked at all: the decision routes to delivery instead, which is a
much stronger safety property than a feature flag inside it.

### 6.7 Narrative
Reports, briefings, client comms, the monthly review, and the delivered
recommendation list. AI writes the prose; every number is passed in, never
generated. Same rule as the Jarvis briefing, where the model writes two
sentences and the arithmetic decides everything else — and where the echo
provider's output had to be explicitly rejected because it was short and
plausible enough to pass every other guard.

## 7. Departments map onto services

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

## 8. Data model

Core entities. Client-instance database unless marked *(control plane)*.

**No table below names a channel.** Where a channel concept is unavoidable it is
a foreign key to `Connection` plus an opaque `native` blob the adapter owns.

**Identity and authority**
```
Tenant            (control plane)  id, name, plan, state
Mandate           (control plane)  tenant, channel, scope, limits, granted_by,
                                   expires_at, revoked_at, version
Connection                         channel_id, external_account_id, token_ref (vault),
                                   granted_scopes, capabilities[], expires_at, health
```
`capabilities[]` is derived from `granted_scopes` by the adapter and re-derived
on every token refresh. It is the single source of truth for whether this client,
on this channel, is in recommend or execute mode (§5.1).

**The acquisition graph** — channel-neutral, mirrored external state plus our intent
```
Account                            connection, external_id, currency, timezone,
                                   spend_cap, display_kind, native
Program                            account, external_id, objective, status,
                                   our_intent, strategy_id, last_reconciled_at,
                                   display_kind, native
Group                              program, external_id, budget, targeting_hash,
                                   status, our_intent, display_kind, native
Placement                          group, external_id, variant_id, status,
                                   our_intent, display_kind, native
```
`our_intent` versus `status` is the drift detector: what we asked for versus what
the channel reports. `display_kind` carries the client's vocabulary
(`"Ad Set"`, `"Ad Group"`) so reports read naturally without the code caring.

**Creative** — channel-neutral concept, channel-shaped rendition
```
Hypothesis                         claim, support[], kill_condition, state,
                                   executions[], resolved_at, verdict
Generation                         index, control_variant, allocation, opened_at,
                                   closed_at, seasonal_boundary
Brief                              hypothesis, angle, audience, constraints
Concept                            brief, angle, hook, rationale
Asset                              concept, kind, uri, provider, cost, checksum
Variant                            asset + copy, lineage[], parent, tests_variable,
                                   tier, generation, approval_state
CreativePrediction                 variant, expected_effect_range, confidence,
                                   basis[], kill_condition, resolve_by
Rendition                          variant, channel_id, format, aspect, duration,
                                   external_creative_id
CreativeResult                     variant, effect, test_structure,
                                   learning_weight, direction_correct,
                                   magnitude_error, reason_confirmed
```
`lineage` is what makes creative learning possible: this variant descends from
that winner, changing this one variable. Splitting `Rendition` off `Variant` is
what lets one concept run on two channels and be compared as one thing.

`Hypothesis` is first-class and owns many variants, because a single failed
execution falsifies nothing — only a hypothesis failing across three independent
executions does. `CreativeResult.learning_weight` is set by test structure
(matched test 1.0, cohort 0.5, observational 0.2, **confounded 0.0**), and a
confounded result is reported to the client but never published to the fleet.

**Measurement**
```
MetricSnapshot                     entity, channel_id, date, as_of, breakdown,
                                   impressions, spend_minor, currency, clicks,
                                   conversions, revenue_minor,
                                   attribution_basis, modelled
StoreOrder                         external_id, at, revenue_minor, cogs_minor,
                                   new_customer, attributed_source
Reconciliation                     period, channel_id | null, platform_conv,
                                   store_conv, delta, confidence, method
```
`attribution_basis` and `modelled` travel with every figure (§5.3). A
`Reconciliation` with a null `channel_id` is the blended, cross-channel one —
the number the client actually cares about.

**The spine**
```
Signal                             kind, entity, observed, threshold, severity
Diagnosis                          signal[], hypothesis, evidence[], confidence
Proposal                           diagnosis, verb, target, magnitude,
                                   expected_effect, confidence
Decision                           proposal, verdict, mandate_version, actor,
                                   clamped_from, mode
Action                             decision, idempotency_key, request, response,
                                   attempts, state
Delivery                           decision, delivered_at, channel_of_record,
                                   acknowledged_at, applied_by_client_at
Outcome                            decision, horizon, expected, actual, verdict
```
`Decision.mode` is `shadow | recommend | execute`. A decision in `recommend`
mode gets a `Delivery` row instead of an `Action` row, and still gets an
`Outcome` — measured the same way, because measuring needs only read access.
That symmetry is what turns recommendation mode into the evidence that earns a
write mandate.

**Learning**
```
KnowledgeCard   (control plane)    claim, evidence[], scope, channel_scope,
                                   confidence, decay_class, as_of,
                                   supporting_tenants, contributions[],
                                   supersedes, contradicts[], tenant_visible
Experiment                         hypothesis, design, holdout, result, power
```

`decay_class` is `structural | behavioural` and sets the half-life over which
confidence falls arithmetically; platform-mechanical claims are **not stored as
knowledge at all** — they are thresholds re-derived from recent data, because
encoding auction folklore is how a system ends up confidently applying 2026 to
2028 (`08-MOAT.md §10`). `contributions[]` is what makes a card recomputable
without a departing tenant.

`channel_scope` is part of the claim, exactly as vertical and AOV are: *"held on
Meta, untested elsewhere"* is a different card from *"held on Meta and TikTok."*
A card recalled onto a channel it was never tested on is the cross-channel
version of the transfer failure in §10.

Knowledge cards are the only thing that crosses the tenant boundary, and only
upward, only anonymised, only with the tenant's contractual permission.

## 9. Events

Phoenix publishes onto the Jarvis bus. Hierarchical topics, existing
subscribers.

```
ingest.completed          tenant, channel, source, entities, as_of
truth.reconciled          tenant, period, confidence
signal.raised             tenant, kind, entity, severity
diagnosis.formed          tenant, signal[], confidence
proposal.made             tenant, verb, magnitude
decision.recorded         tenant, verdict, mode, mandate_version
decision.escalated        tenant, reason              → human console
decision.delivered        tenant, count, channel_of_record   (recommend mode)
action.executed           tenant, channel, external_id, attempts
action.failed             tenant, channel, error, will_retry
action.unsupported        tenant, channel, verb       → adapter gap, not a fault
action.drifted            tenant, expected, actual    → reconciliation
outcome.measured          tenant, mode, verdict, delta
mandate.breached          tenant, attempted, limit    → page a human
connection.capabilities_changed  tenant, channel, added[], removed[]
creative.shipped          tenant, variant, channel, program, tier, test_structure
generation.opened         tenant, index, control, allocation
generation.resolved       tenant, index, frontier_lift, hypotheses_resolved
hypothesis.resolved       tenant, hypothesis, verdict, executions
creative.fatigued         tenant, variant, cohort_wide       → refresh vs retire
creative.retired          tenant, variant, reason
creative.revived          tenant, variant, rested_days
observation.emitted       tenant, kind, scope[]        → outbox, pulled not pushed
publication.gated         reason, generalised_to | suppressed
knowledge.published       card, scope, channel_scope, supporting_tenants
knowledge.contradicted    card_a, card_b, proposed_split
knowledge.decayed         card, confidence_now         → fell below recall threshold
contribution.withdrawn    tenant, cards_recomputed, cards_suppressed
calibration.drifted       action_type, scope, delta    → the world may have moved
```

`mandate.breached` should never fire. If it does, something bypassed the check,
and that is a P0.

`connection.capabilities_changed` is the event that moves a client between
recommend and execute mode. It fires on grant, on revocation, and on a token
refresh that comes back with fewer scopes than it went in with — which is how a
client silently losing write access surfaces as a mode change rather than as a
week of failing writes.

`calibration.drifted` is the fleet's early-warning system. When stated confidence
stops matching observed accuracy **across many tenants at once**, the most likely
explanation is that the environment changed, not that one account got unlucky —
and it fires earlier than any single client's performance would
(`08-MOAT.md §12`).

## 10. Memory

Three tiers, mapped to Jarvis's existing scoping.

**Tenant memory** — everything about one client, in their instance, in their
Obsidian vault. Brand rules, offer economics, what has been tried, what worked.
Never leaves.

**Agency memory** — cross-client, in the control plane. Only knowledge cards:
anonymised, structured claims with evidence and confidence. *"Hook framing X
beat control in 7 of 9 tests across 4 apparel brands, mean lift 14%, CI
±6%."* Never raw creative, never client names, never account data.

**Model memory** — none. Nothing is fine-tuned on client data, in any tier, ever.
Unlearning is impossible in weights and mechanical in data, and a client who
leaves must be able to take their contribution with them
([ADR 0008](adr/0008-learning-lives-in-data-not-weights.md)).

**Why knowledge cards rather than "store winning creatives":** three failure
modes the naive version has. *Confidentiality* — a winning ad is the client's
IP. *Transfer* — what works for supplements does not work for furniture, and a
memory that does not carry its scope will be recalled where it does not apply.
*Survivorship* — storing only winners teaches nothing; the failures carry more
information and cost the same to store.

**How a card gets made, and how it crosses.** A tenant emits *observations* into
an append-only outbox; the control plane **pulls** and runs them through a
deterministic **publication gate** — k-anonymity ≥ 5 tenants, ≥ 3 independent
tests, controlled vocabulary, no verbatim content, consent live. A model may
propose an observation; a model never decides what crosses a tenant boundary.
Claims that are too narrow to be anonymous generalise upward or stay tenant-local
rather than failing. No control-plane service holds a tenant database credential,
so the blast radius of a compromised control plane is the outboxes — which
contain only publication-shaped rows. Full design in
[ADR 0007](adr/0007-knowledge-crosses-as-gated-claims.md) and `08-MOAT.md`.

**Learning-plane stores** (control plane, alongside the claim store):

```
Observation      kind, scope[], features[], treatment, control, effect, ci, n,
                 measurement_confidence, as_of, vocabulary_version, contribution_id
Contribution     contribution_id → tenant, observation, withdrawn_at
                 (append-only; the ledger that makes unlearning mechanical)
Calibration      action_type, vertical, spend_band, channel,
                 stated_confidence_bucket, observed_accuracy, n
Vocabulary       version, term, kind, parent          (the learned taxonomy)
```

`Contribution` is the table that lets a departing tenant be removed by
recomputation rather than by promise. Cards are derived, never authored.

## 11. Integrations

Official APIs, always. Browser automation only where no API exists, and never
for anything that spends money.

**Channel adapters** — behind the §5 port, one row each:

| Channel | Status | Capabilities typically granted | Notes |
|---|---|---|---|
| **Meta** | first adapter | read from day one; write when the client grants it | App review + business verification for write. Start day one; nothing is blocked behind it. Rate limits are tiered — confirm current terms. |
| Google Ads | designed for, not built | — | Second adapter. The port exists so this is weeks, not a redesign. |
| TikTok | designed for, not built | — | Third. Format matrix differs most here. |

**Everything else** — ordinary integrations, not channels:

| Integration | Direction | Criticality | Notes |
|---|---|---|---|
| Meta Conversions API | W | Critical | Server-side signal. Post-ATT this is not optional. Sits beside the channel adapter, not inside it. |
| Shopify Admin | R | Critical | Revenue truth |
| Stripe | R | High | Where Shopify is not the processor |
| GA4 | R | Medium | Corroboration, not truth |
| Creative generation | W | High | Multiple providers behind one port — terms and quality both move |
| Obsidian | R/W | Medium | Already a Jarvis adapter |
| Slack / email | W | Medium | Escalation, reports, recommendation delivery |

**Token lifecycle is a real subsystem, not a config field.** Tokens expire, get
revoked when a user leaves the client's business, and fail in ways that look
like rate limits. A dead connection must degrade that capability loudly, surface
in the client's console, and never silently produce stale numbers. Under the
agency model this is more likely, not less: the permissions live on the client's
Business Manager and their staff changes are outside our control.

**Every integration is a port with a recorded-fixture implementation.** The
whole system runs offline against recorded API responses, which is Jarvis's
existing offline-determinism requirement applied to third parties. For channels
this does double duty: the fixture adapter is also the conformance test a second
channel must pass before it ships.

## 12. Security

Inherits Jarvis's posture, plus what multi-tenancy demands.

- **Isolation by database.** Not by query filter.
- **Secrets in the vault.** Channel tokens are `${vault:<channel>.<tenant>}`; the
  model names them and never holds them; resolved in the tool registry after the
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
- **Least privilege on every channel.** Request the narrowest scopes that work,
  and request them incrementally — read first, write per action type as trust is
  earned. **Never hold billing permissions**, which under the agency model is
  both a safety property and the line that keeps us from being a spend reseller.
- **The client owns the accounts.** Phoenix operates inside their Business
  Manager as a granted partner. Every permission is theirs to revoke without
  asking us, and revocation must degrade to recommendation mode cleanly rather
  than error.
- **PII.** Customer lists and CAPI payloads are hashed before transmission and
  never enter a prompt.

## 13. Deployment

**Control plane** — Postgres, the console, the fleet scheduler. Small, boring,
always up.

**Client instances** — containerised Jarvis + Phoenix. One per tenant. Scheduled
work is driven by the control plane rather than by an in-process loop per
container, so a sleeping tenant costs nothing.

**Environments** — dev (recorded fixtures, no network), staging (channel sandbox
plus one real low-spend account), production.

**Migrations** — Alembic, per tenant, applied by the control plane in a rollout
with a canary tenant first.

**Observability** — the Jarvis event bus is already the substrate. What
Phoenix adds: spend per tenant per day, decision latency, mandate-check reject
rate, `unsupported` verb rate per adapter, drift count, reconciliation
confidence, recommendation adoption rate, AI cost per client. Reconciliation
confidence and AI cost are the health metrics nobody thinks to add and everybody
needs; recommendation adoption is the one that tells you whether a read-only
client is getting value.

## 14. Deliberately not built in v1

- **A second channel adapter.** The port is built and the Meta adapter is
  written *to* it; Google and TikTok wait for a client whose retention depends
  on one. Depth before breadth — but the abstraction is not deferred, because
  that is the part that gets expensive later (ADR 0006).
- Multi-touch attribution modelling — expensive, contested, and holdout tests
  answer the real question better
- Fine-tuning on client data
- Self-serve onboarding
- A creative asset marketplace
- Real-time bidding intervention — the platform's job, and we would lose
- Holding client ad accounts or reselling spend — the agency model is
  deliberate, not a stepping stone
