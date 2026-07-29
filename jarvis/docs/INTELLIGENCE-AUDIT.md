# Intelligence audit

An audit of everything that decides *what Jarvis does*: the thirty agent
prompts, the shared house rules, the two-stage router, the arbiter, and the
planning strategy. Phase 11 opens here because the platform is stable and the
remaining gains are in judgement, not in surface area.

Two rules govern this document.

**Nothing is rewritten without a reason that survives being written down.** A
prompt change that cannot be stated as "this specific behaviour was wrong, and
this is why the new wording fixes it" is a guess wearing a diff.

**Findings are separated by what it takes to prove them.** Some defects are
structural — a tool that does not exist, a field nothing reads, a threshold the
scoring function cannot reach. Those are provable offline, arithmetically, and
they are fixed in this milestone. Others are behavioural — is this prompt any
good — and those are only knowable by running a real model against a corpus.
Those are listed here and deferred to M11.3, *after* the corpus exists.

That ordering is a deliberate correction to the phase plan. Improving prompts
before expanding the evaluation would mean building the ruler after cutting the
wood.

---

## Summary

| # | Finding | Severity | Provable offline | Status |
|---|---|---|---|---|
| F1 | 78% of requests escalate to the LLM arbiter; the router's central claim is false | **high** | yes | fixed |
| F2 | 14 of 30 agents declare tools that do not exist; 12 have none that resolve | **high** | yes | fixed |
| F3 | The Memory Agent cannot read or write memory | **high** | yes | fixed |
| F4 | `collaborators` is read by nothing — there is no delegation mechanism | **high** | yes | documented → M11.5 |
| F5 | `responsibilities` never reaches the model | medium | yes | documented |
| F6 | Capability tags silently double-count for half the catalog | medium | yes | fixed |
| F7 | Seven keyword pairs collide under prefix matching | medium | yes | fixed |
| F8 | No agent prompt states an output contract | medium | no | → M11.3 |
| F9 | No agent prompt mentions the tools it was given | medium | no | → M11.3 |
| F10 | A house rule contradicts the four planning agents | low | no | → M11.3 |
| F11 | The memory tools ignored scope, so a mode's narrowing had a hole | **high** | yes | fixed |

---

## F1 — The two-stage router became a one-stage router

`docs/adr/0003-two-stage-routing.md` and the README both claim that a free
lexical pass handles most requests and the arbiter is consulted only when that
pass is genuinely ambiguous — "most messages therefore cost zero extra latency
to route."

Measured against the existing 23-case corpus, that is no longer true:

```
threshold=0.55   escalated 18/23 = 78%
top-confidence   median 0.40   max 0.73
```

The cause is arithmetic. `AgentRegistry._score` awards `1.0` per keyword hit
and squashes with `hits / (hits + 1.5)`, so:

| evidence | score |
|---|---|
| one keyword | 0.40 |
| two keywords | 0.57 |
| one phrase | 0.57 |
| three keywords | 0.67 |

When `AMBIGUITY_THRESHOLD` was raised from 0.35 to 0.55 — correctly, to stop
homonyms routing confidently and wrongly — nothing raised the *scores*. A
single precise keyword tops out at 0.40, which is below the new bar. So
"calendar" in "what's on my calendar tomorrow" now escalates. So does
"margin", and "flight", and "test".

This is worse than the failure it replaced. The homonym cases are now handled,
but every unambiguous request pays a model call for a decision the lexical pass
already had right, and the escalation is invisible: it shows up as latency and
spend, never as an error.

### Why the fix is not "lower the threshold back"

Lowering it reinstates the homonym failures the raise was measured to fix
("our **security** deposit is due" → the Security Agent at 0.50). The threshold
is not wrong. The *score* is wrong, because it measures **how much text
matched** rather than **how much the match distinguishes this agent from the
others**.

Those are different quantities, and only the second one is evidence. "calendar"
appearing in a request is strong evidence for the Calendar Agent because no
other agent claims it. "post" appearing is weak evidence for anyone, because
the Copywriter and the Social Media Manager both claim it. Today both are worth
exactly 1.0.

### The change

Each keyword's weight is divided by the number of agents *in this registry*
that claim a prefix-colliding keyword. An exclusive keyword is worth as much as
a phrase, because it is as diagnostic as one; a keyword two agents share is
worth half that, which lands it below the threshold and escalates — which is
the correct outcome, since two agents claiming a word is the definition of
ambiguity.

Computed per registry rather than per catalog, because a mode narrows by
handing over a smaller registry (ADR 0010). In coding mode a keyword three
agents share may be exclusive to one of the six that survive, and it should
score as the strong evidence it has become.

Measured effect on the 23-case corpus, lexical stage only, arbiter disabled:

```
                       before      after
escalation rate        78%         48%
accepted (of 23)       13          18
actively wrong          3           1
```

Escalations fall by a third *and* lexical accuracy rises, because the cases
that stop escalating are exactly the ones stage one already had right. The
cases that still escalate are the genuinely contested ones — which is what the
arbiter is for.

The single remaining actively-wrong lead ("design a schema for the orders
table" → Product Designer) now escalates rather than deciding, so the arbiter
gets its chance at it; before, it decided alone.

### A catalog gap the measurement exposed

Weighting by exclusivity only works if colliding words actually collide, and
checking that turned up two words the Financial Analyst never claimed:

- **`price`** is not a prefix of **`pricing`** — they diverge at the fifth
  character — so the agent that owns pricing strategy scored nothing on
  "should we raise prices", and Shopping took it uncontested at 0.57.
- **`deposit`** was claimed by nobody, which is why "our security deposit on
  the office is due" was a confident, unopposed match for the Security Agent.

Both are core financial vocabulary that belonged on that spec since M1. Adding
them turns both requests into ties that escalate — the second one being the
exact homonym failure the threshold was raised for, now handled by evidence
rather than by a threshold that had to be set high enough to catch it.

## F2 — Fourteen agents declare tools that do not exist

`ToolRegistry.schemas_for` skips names it does not recognise. The docstring
justifies this: a spec may name a tool whose connector is not installed, and
that should degrade the agent's reach rather than break the request. That is
right. What is wrong is that nothing anywhere reports the gap, so it grew:

```
marketing           declares 2   resolve 0   phantom: web_search analytics
sales               declares 3   resolve 0   phantom: web_search email crm
financial_analyst   declares 2   resolve 0   phantom: spreadsheet stripe
data_analyst        declares 3   resolve 0   phantom: database spreadsheet analytics
social_media        declares 2   resolve 0   phantom: social analytics
support             declares 3   resolve 0   phantom: email crm knowledge_base
email               declares 3   resolve 0   phantom: gmail outlook email
calendar            declares 2   resolve 0   phantom: calendar email
meeting             declares 3   resolve 0   phantom: calendar transcription email
memory              declares 1   resolve 0   phantom: memory
security            declares 2   resolve 0   phantom: audit vault
vision              declares 2   resolve 0   phantom: screenshot ocr
voice               declares 2   resolve 0   phantom: stt tts
travel              declares 2   resolve 1   phantom: calendar
```

The consequence is not only a missing capability. `AgentRuntime.stream` sets
`needs_tools=bool(spec.tools)` from the *declared* list, so these agents route
to a tool-capable model and pay for it while being handed an empty tool array.
Twelve of thirty agents are paying a capability premium for nothing.

Three of these names were never going to resolve under any installation:
`audit`, `vault`, `stt`, `tts` and `screenshot` are **ports**, not tools —
internal seams the kernel wires, with no invocable surface. `ocr` is a model
capability. Listing them expresses an intention the architecture already
fulfils by other means.

The rest — `gmail`, `calendar`, `crm`, `stripe`, `analytics` — are real
capabilities that arrive over MCP. But MCP mounts a server as a *namespace*
(`github.create_issue`), so a bare `gmail` would not have matched even with the
connector installed. These are aspirations spelled as facts.

### The change

Three parts, in order of how much they matter:

1. **Wire the tools that already exist.** `memory_search`, `memory_write`,
   `search_documents`, `read_file` and `fetch_url` are registered and were
   simply not on the specs that most obviously need them (F3).
2. **Delete the names that cannot resolve**, rather than leaving a spec that
   describes a system nobody built.
3. **Make the gap loud.** A startup check logs every spec'd tool with no
   registered implementation, and a test asserts the catalog declares nothing
   unresolvable outside a known connector-gated set. The defect that produced
   this was not the missing tools; it was that nothing noticed for ten
   milestones.

Connector-gated agents keep their remit and lose their phantom list. When the
Gmail MCP server is mounted, the correct spec entry is `gmail.*`, and the
grant model already governs a whole namespace at once.

## F3 — The Memory Agent could not touch memory

The clearest instance of F2, called out separately because it is a plain bug
rather than an aspiration. The Memory Agent's prompt says:

> You curate long-term memory. Store durable facts, preferences, decisions and
> outcomes — not transient chatter. Merge duplicates, supersede stale facts.

Its declared tool is `memory`. The registered tools are `memory_search` and
`memory_write`. So the agent responsible for curating memory was given an
empty tool array and could do none of it — it could only *talk* about curating
memory, which is precisely the failure mode the house rules open by forbidding.

Same shape as the Copywriter defect found in M10: an instruction that lived in
`responsibilities`, which the model never sees. Both are the same class of
error — a capability declared in a field nothing enforces.

## F4 — There is no delegation, anywhere

`AgentSpec.collaborators` is documented as "agents that this one commonly
delegates to, used by the planner." Nothing reads it. `grep -rn collaborators`
returns the field definition and the seven specs that populate it.

This is not a dead field so much as a missing subsystem, and the prompts have
been writing cheques against it since M1:

- Chief of Staff: *"you decide whether to answer it, decompose it, or hand it
  to specialists"* — there is no mechanism to hand anything to anyone.
- Planner: *"each step names an owner (agent or human)"* — no owner is ever
  dispatched to.
- `Orchestrator.handle` routes to exactly one agent and streams exactly that
  agent's output. `matches[1:]` is reported to the client as candidates and
  then discarded.

So the Chief of Staff, told it is accountable for the end-to-end outcome, is in
fact a single-turn generalist that has been instructed to believe otherwise.
Every multi-specialist request produces a description of the delegation rather
than the delegation, because describing it is the only thing available.

This is the largest single gap between what the intelligence layer promises and
what the runtime does — and it is the thing standing between "AI assistant" and
"AI Chief of Staff." It is a subsystem, not a prompt fix, so it belongs to
M11.5 where Part 4 puts it.

## F5 — `responsibilities` is metadata the model never sees

`_spec()` composes `system_prompt` from the house rules and the prompt body
only. `responsibilities` is read by `api/schemas.py` for display and by nothing
else.

This caused a measured failure. The Copywriter's third responsibility is
"Produce variants for testing"; asked for a headline, it returned one headline,
because the instruction to produce variants was never sent. The M10 fix moved
that requirement into the prompt body, where it worked.

Leaving the field is defensible — the UI needs a human-readable remit, and
concatenating all thirty specs' responsibilities into their prompts would add
tokens for restated intent. What is not defensible is the name, which reads as
behaviour, and the docstring, which does not say otherwise. Renaming it in the
API is a breaking change for the client and is deferred; the field's docstring
now states plainly that it is display-only and that behaviour belongs in the
prompt. Every remaining `responsibilities` entry was checked against its
prompt body; the ones expressing behaviour the prompt does not require are
listed in F8 for M11.3.

## F6 — Capability tags double-count for half the catalog

`_score` adds `0.5` when a capability's value appears as a token. For fifteen
of thirty agents the capability value is *also* one of their keywords:

```
planner(planning)  research(research)  marketing(marketing)  sales(sales)
legal(legal)  travel(travel)  shopping(shopping)  health(health)
learning(learning)  data_analyst(analysis)  designer(design)
support(support)  memory(memory)  security(security)  voice(voice)
```

so "research the market" scores the Research Analyst 1.0 for the keyword plus
0.5 for the capability — one piece of evidence counted twice, and counted twice
only for the agents whose remit happens to be a single English noun. It is a
silent, unearned weighting that favours exactly the agents already easiest to
match, and it makes the score non-interpretable: the same 0.5 sometimes means
"an independent signal agreed" and sometimes means "the same word again."

Users type "analyse this", not "analysis". Capability tags are a routing
vocabulary for the system, not one users speak. The bonus is removed; the
capability is what a mode and the permission model filter on, which is its real
job.

## F7 — Seven keyword pairs collide under prefix matching

`_score` matches by prefix so "analyz" catches analyze/analyzing/analysis. That
is worth having, and it means these pairs fight:

```
strategy ~ strategy    ceo, planner
compare  ~ compare     research, shopping
market   ~ marketing   marketing, research      ← prefix, not equality
product  ~ product     product_manager, shopping
brand    ~ brand       creative_director, marketing
post     ~ post        copywriter, social_media
screen   ~ screenshot  designer, vision         ← prefix, not equality
```

Two are accidents of prefix matching rather than genuine overlap. Research's
`market` swallows every "marketing" request; Designer's `screen` swallows
"screenshot". The other five are real overlaps where two agents plausibly own
the word.

The F1 specificity weighting handles all seven correctly without special-casing
any of them — a shared word is worth half, drops below the threshold, and
escalates to the arbiter, which is the right answer for a genuinely shared
word. The two prefix accidents are additionally fixed at the source
(`market` → `market research`, `screen` → `screens`), because a word that only
collides by accident should not be paying an arbiter call forever.

## F8 — No prompt states an output contract *(deferred to M11.3)*

Not one of the thirty prompts says how long its answer should be, what shape it
should take, or what it must always contain. The house rules say "be concise";
nothing says concise *relative to what*.

The two prompts that do have contracts got them by measurement, after failing:
the Copywriter now specifies three options with a rationale line each, and the
Life Coach now specifies a question plus one concrete next step. Both were
written in M10 in response to observed failures. The other twenty-eight are at
the pre-measurement baseline, and prompt-body length ranges from 23 words
(Meeting) to 87 (Copywriter) with no principle behind the spread.

Candidates visible from inspection, all unproven until measured:

- **Research** — "end with the implication, not a summary" gives an ending but
  no structure; its `responsibilities` promise "a stated confidence" that the
  prompt never requires.
- **Planner** — "prefer five real steps to fifteen" is a preference, not a
  format; nothing requires the owner/input/output/done-condition tuple it
  describes to actually appear.
- **Financial Analyst** — requires the downside case but not a unit.
- **Meeting**, **Vision**, **Designer** — the three shortest prompts, each
  describing a taste rather than a deliverable.

Each becomes a measurable hypothesis once M11.2 exists. None should be rewritten
before then.

## F9 — No prompt mentions the tools it was given *(deferred to M11.3)*

`AgentRuntime` passes tool schemas to the provider, and the agentic loop runs
up to six rounds. No system prompt mentions that tools exist, when to reach for
one, or when to answer from memory instead.

The Research Analyst's prompt demands that "every non-obvious claim carries a
citation" while never telling it that `fetch_url` and `browser_open` are how a
citation is obtained. A model that complies invents a plausible URL; a model
that refuses says it cannot browse. Both are avoidable.

The right fix is probably one house rule rather than thirty edits, and probably
conditional on `spec.tools` being non-empty — but "probably" is why this waits
for the corpus.

## F10 — A house rule contradicts the planning agents *(deferred to M11.3)*

Every agent receives:

> Produce the artefact, do not describe how to produce it.

For the Planner, the Architect, the Product Manager and the Chief of Staff, the
artefact **is** a description of how to produce something. The rule is aimed at
a real failure — models answering "here's how you'd write that landing page"
instead of writing it — but as written it tells a quarter of the catalog that
its own job is forbidden.

Whether models actually get confused by this is an empirical question with a
cheap experiment behind it, and it is exactly the kind of change that should
not be made on the strength of its being noticeable in a text file.

## F11 — The memory tools read every namespace

Found while fixing F3, and the reason F3 mattered more than it looked.

`AgentRuntime._build_context` recalls with `scope=spec.scope`, which a mode
rewrites — that path is correct and ADR 0010 turns on it. The `memory_search`
*tool* did this:

```python
recalls = await memory.search(query, limit=limit)     # scope=None
```

`InMemoryStore.search` treats `scope=None` as "every scope". So an agent had
two routes to memory: the one the runtime opened, which respected the
narrowing, and the one the model could take on its own initiative, which did
not. In Business mode, `memory_search("what do I know about Sam")` returned
personal memories.

`memory_write` had the mirror image: no scope meant `"global"`, so a note taken
in Business mode landed in the namespace every mode reads.

Nothing had exercised it, because until F3 the agents most likely to reach for
these tools did not have them. Fixing F3 would have put a latent hole onto the
hot path.

This is the same shape as the M9 routing-fallback bug — a narrowing enforced in
one place and ignored in another — which is the recurring failure mode of this
architecture and worth naming as such. A narrowing that any single code path
can decline to honour is not a narrowing.

### The change

A tool declares `scoped=True` when it reads or writes the caller's namespace.
`ToolRegistry.invoke` then supplies the scope from the runtime, which takes it
from `spec.scope` — the value the mode rewrote.

The scope is deliberately **not** in the tool's JSON schema, and any `scope`
the model does supply is stripped before authorisation, so it never reaches the
audit entry or the approval prompt either. A namespace the model could name is
a namespace the model could pick, and then the narrowing would be advisory.

---

## What this milestone changed

Only F1, F2, F3, F6, F7 and F11 — every one of which is provable by arithmetic
or by a `grep`, and every one of which is covered by a test that fails on the
old behaviour.

No prompt wording changed. Everything in F8, F9 and F10 is a hypothesis, and
turning hypotheses into edits without a corpus to check them against is the
habit this phase exists to break.

Nine tests were added. Each names its finding, and each fails against the code
as it stood before this milestone:

```
test_every_declared_tool_has_an_implementation            F2
test_the_memory_agent_can_actually_touch_memory           F3
test_an_exclusive_keyword_decides_and_a_shared_one_escalates          F1
test_exclusivity_is_measured_against_the_registry_not_the_catalog     F1
test_capability_tags_do_not_double_count_their_own_keyword            F6
test_prefix_accidents_are_gone_from_the_keyword_lists                 F7
test_a_memory_tool_cannot_read_across_a_mode_narrowing                F11
test_a_model_cannot_choose_its_own_memory_scope                       F11
test_a_memory_written_by_a_tool_lands_in_the_callers_namespace        F11
```

## What is still open

F4 (no delegation) and F5 (`responsibilities`) are documented rather than
fixed. F5 needs only a rename, which is a breaking change for the client and
not worth doing alone; the field's docstring now says plainly that it is
display-only, which is what would have prevented the Copywriter defect.

F4 is a subsystem. It is the largest gap in the intelligence layer and it is
what Part 4 of this phase is for.
