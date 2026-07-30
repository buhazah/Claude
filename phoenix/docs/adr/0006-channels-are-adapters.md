# 6. Channels are adapters; the acquisition workflow is the platform

Status: proposed

## Context

The first version of this blueprint was Meta-shaped all the way down. The data
model named `Campaign`, `AdSet` and `Ad` — Meta's nouns. Mandates enumerated
Meta actions. The roadmap treated "a second platform" as a Phase 7 maybe, and
`06-ROADMAP.md` listed Google Ads and TikTok under *what is not on this
roadmap*.

That is a reasonable way to ship one channel quickly and a bad way to build a
platform. Two forces make it wrong here specifically:

**The product is the acquisition workflow, not the media buying.** Strategy,
research, creative generation, campaign orchestration, measurement,
optimisation recommendations and continuous learning are the deliverable. Media
buying is one capability inside it. Every one of those concepts is
channel-independent — a creative brief, a hypothesis, a mandate, a knowledge
card and a reconciliation do not become different objects because the money
went to TikTok.

**Write access is a permission, not a milestone.** Phoenix must be able to
operate in read-only analysis and recommendation mode on a client's existing ad
accounts, and gain execution later, per client, when permissions arrive. If
"can write" is a roadmap phase, the read-only mode is a waiting room. If it is
a declared capability of an adapter, read-only is a first-class operating mode
that some clients simply stay in.

Retrofitting a channel abstraction after the Meta code is written is the most
expensive refactor available: it touches the data model, the mandate checker,
the evaluation corpus and every stored metric.

## Decision

**A channel is a port with declared capabilities. Meta is the first adapter.**

```python
class Channel(Protocol):
    id: str                                  # "meta", "google_ads", "tiktok"
    capabilities: frozenset[Capability]      # what this connection can do

    async def describe(self) -> ChannelSchema: ...
    async def pull(self, window: Window) -> Iterable[EntitySnapshot]: ...
    async def metrics(self, window: Window) -> Iterable[MetricSnapshot]: ...
    async def apply(self, action: Action, *, idempotency_key: str) -> ActionResult: ...
    async def preview(self, action: Action) -> ActionPreview: ...
```

Four obligations, and the third is the one that matters:

**1. Capabilities are declared, per connection, not per channel.** A capability
is granted by the client's permissions, so two clients on the same channel can
have different ones.

```
read.entities   read.metrics   read.creative_library
write.budget    write.status   write.creative   write.campaign
experiment.holdout   experiment.split
```

`write.*` absent is not a degraded state. It is **recommendation mode**: the
loop runs to a decision, and the decision is delivered to the client to execute
rather than executed. Every layer above already handles this, because it is the
same code path shadow mode uses.

**2. Entities map onto a channel-neutral graph.** Phoenix stores four levels
and lets the adapter name them:

```
Account   →  Meta: Ad Account      Google: Customer     TikTok: Advertiser
Program   →  Meta: Campaign        Google: Campaign     TikTok: Campaign
Group     →  Meta: Ad Set          Google: Ad Group     TikTok: Ad Group
Placement →  Meta: Ad              Google: Ad           TikTok: Ad
```

The adapter supplies the display name, so the client still reads "Ad Set" in
their report. Phoenix's code, mandates and evaluation corpus speak
`Account/Program/Group/Placement`. Where a channel has no fourth level, or a
fifth, the adapter collapses or nests — the graph is a lowest common
denominator by design, and channel-specific detail lives in a `native` JSON
field that only the adapter reads.

**3. Metrics are normalised at the boundary, with provenance.** Every adapter
emits the same `MetricSnapshot` in minor currency units with an `as_of`, and
declares its attribution basis (`window`, `model`, `modelled: bool`). Cross-
channel arithmetic is only allowed between metrics whose bases are compatible;
the Truth service refuses to add a modelled conversion to a deterministic one
without saying so.

**4. Actions are channel-neutral verbs with a magnitude.** `shift_budget`,
`set_status`, `launch_creative`, `create_program`. The mandate checker validates
verbs and magnitudes and knows nothing about Meta. The adapter translates a
verb into an API call, or rejects it as unsupported — a fifth capability answer
alongside accept/clamp/reject/escalate.

**What sits above the port, and must never import an adapter:** strategy,
research, briefs, creative generation and lineage, the signal→outcome spine,
mandates, approvals, memory and knowledge cards, workflows, reporting,
evaluation. The composition root is the only place that knows Meta exists —
the same rule as Jarvis Core's kernel, enforced the same way, with a test.

## Alternatives rejected

**Build Meta-native, abstract later.** Cheapest this month. The refactor lands
in the data model, the mandate checker and the historical metric store at once,
and by then there is client history in Meta-shaped rows.

**A universal ad-platform abstraction that covers everything.** The opposite
failure: an interface general enough for search, social and retail media that
expresses nothing well. The graph above is deliberately shallow, and the
`native` escape hatch is deliberately present.

**Channel-specific everything, sharing only the database.** What most agency
tooling does. It means the knowledge layer — the actual moat — cannot see
across channels, which is the one place cross-channel is genuinely worth more
than the sum.

## Consequences

- **Read-only becomes a product, not a phase.** A client who will not grant
  write access is still a full client, receiving diagnosis and ranked
  recommendations. `06-ROADMAP.md` Phase 0 is no longer gated on Meta app
  review.
- **A second channel is an adapter plus an evaluation suite**, not a redesign.
  The estimate is weeks, not a quarter — and the estimate is testable, because
  the first adapter must be written to the port rather than to itself.
- **The cost is real and paid up front:** one indirection layer, a normalisation
  step that must be got right, and the discipline of not letting a Meta concept
  leak upward when it would be convenient. Expect roughly two weeks of extra
  work in Phase 1 and a recurring tax on every adapter feature.
- **Some channel value is unreachable through the port.** Advantage+ specifics,
  Meta's own experiment tooling, Google's asset groups. These are exposed as
  adapter-specific actions that mandates may enumerate explicitly, and Phoenix
  treats them as opt-in rather than pretending they generalise.
- **The evaluation corpus gains a dimension.** Diagnosis and proposal suites are
  written against the neutral graph, so the same cases run against every
  adapter, and a channel that cannot pass them is not shipped.
