# Jarvis — Execution Roadmap

Each milestone is independently shippable, tested, and committed. No milestone
begins before the previous one's suite is green.

| # | Milestone | Contents | State |
|---|---|---|---|
| **M1** | **Kernel** | Config, structured logging, event bus, model router + provider adapters (Anthropic/OpenAI/Echo), agent spec + runtime + registry + 30-agent catalog, memory store + embeddings + categorizer, run store, tool registry, FastAPI surface with SSE streaming | ✅ **done** |
| **M2** | **Client** | Next.js app, design system, command palette with routing preview, dashboard, streaming chat, agent/memory/run/tool browsers, live activity rail off the event firehose | ✅ **done** |
| **M3** | **Persistence** | Postgres + pgvector, Alembic migrations, hosted embeddings, Redis-backed bus, docker-compose | ✅ **done** |
| **M4** | **Tools & connectors** | Agentic tool loop, filesystem/shell/HTTP tools, MCP client for every connector, approval gate, hash-chained audit log | ✅ **done** |
| **M5** | **Knowledge** | Ingestion (PDF/DOCX/PPTX/XLSX/CSV/HTML/URLs/code/folders), locator-preserving chunking, hybrid retrieval, structural citations | ✅ **done** |
| **M6** | **Workflows** | Graph engine with durable suspension, structured conditions, schedule/event triggers, scheduler with boot recovery, workflow UI | ✅ **done** |
| **M7** | **Voice** | Streaming STT, TTS, barge-in/interruption, wake word | ✅ **done** |
| **M8** | **Computer control** | Sandboxed desktop/browser control with screenshot loop and a hard permission wall | ✅ **done** |
| **M9** | **Modes** | Business / Coding / Research mode surfaces + document generation | ✅ **done** |
| **M10** | **Hardening** | Vault, audit chain, cost governance, CI/CD, load + chaos tests, packaging | ✅ **done** |

**Phase 11 — intelligence.** The platform is stable; from here the work is
making Jarvis *smarter*, not larger.

| # | Milestone | Contents | State |
|---|---|---|---|
| **M11.1** | **Intelligence audit** | Every prompt, routing rule and system instruction reviewed; the structurally provable defects fixed | ✅ **done** |
| **M11.2** | **Evaluation corpus** | 288 cases across ten dimensions, confidence-weighted scoring, committed baseline, CI gate | ✅ **done** |
| **M11.3** | **Measured prompt work** | The behavioural half of the audit, proven against the corpus | ⏸ **needs a provider key** |
| **M11.4** | **Obsidian memory** | A vault behind the `MemoryStore` port — the files *are* the memory | ✅ **done** |
| **M11.5** | **Chief of Staff** | Delegation, and a recommendation engine with no model in the loop | ✅ **done** |
| **M11.6** | **Morning briefing** | Executive read assembled from the same arithmetic | ✅ **done** |
| **M11.7** | **Documentation** | ADRs 0012–0015, prompt strategy, architecture deltas | ✅ **done** |

## Milestone 1 — delivered

**Built**
- `jarvis.kernel` — event bus with hierarchical topics and per-subscriber
  bounded queues; ULID-ish ids; injectable clock; error taxonomy.
- `jarvis.llm` — provider port, model catalog with cost/latency/quality/
  context/privacy attributes, policy-weighted router with fallback chains and
  per-provider circuit breaking; Anthropic, OpenAI and Echo adapters.
- `jarvis.agents` — declarative `AgentSpec`, generic `AgentRuntime` that
  streams onto the bus and records metrics, lexical+capability router, and a
  catalog of 30 agents.
- `jarvis.memory` — tiered store with auto-categorization, salience scoring,
  hybrid lexical+vector recall with recency decay, deterministic embeddings.
- `jarvis.tools` — schema'd tool registry with three permission tiers.
- `jarvis.runs` — durable run records with step timelines and cost ledgers.
- `jarvis.api` — FastAPI app: health, models, agents, memory, runs, chat
  (SSE), and an event firehose.

**Verification** — `pytest` suite covering router scoring, fallback and
circuit breaking, bus fan-out and backpressure, agent routing, memory recall
ranking, run lifecycle, and the HTTP surface end-to-end. Runs with no API keys
and no network.

## Milestone 2 — delivered

**Built**
- Design system in CSS custom properties: dark-first tokens, layered surfaces,
  one accent reserved for live state, glass restricted to floating surfaces.
- App shell — sidebar with spring-animated active indicator, ⌘K palette,
  live activity rail.
- **Command palette** — the defining interaction. As you type, it calls
  `/v1/route` and shows which agents Jarvis would activate, with confidence
  bars and the matched signals, *before* you commit.
- **Streaming chat** — token-by-token rendering with a caret, the answering
  agent and its confidence, recalled-memory count, and live cost/token/latency.
  Interruptible mid-answer via `AbortController`.
- **Live activity rail** — the kernel's event bus rendered directly. Not
  instrumentation; a subscriber.
- Dashboard, agent grid with per-agent metrics, memory browser showing the
  lexical/semantic/recency signals behind each recall, run history, and a tool
  browser grouped by permission tier.
- Every surface defines loading (geometry-matched skeletons), empty, error and
  streaming states.

**Verification** — 20 unit tests (incremental SSE parsing across arbitrary
chunk boundaries, malformed frames, the typed API client) plus a 7-check
Playwright end-to-end run against the real kernel: routing preview →
execution → streaming → run history, with zero console errors. `tsc --noEmit`
and ESLint clean.

## Milestone 3 — delivered

**Built**
- `jarvis.persistence` — SQLAlchemy 2 async schema serving both dialects. The
  only dialect-specific piece is the embedding column: a real pgvector
  `vector` on Postgres, JSON on SQLite, behind one `TypeDecorator`.
- `SqlMemoryStore` / `SqlRunStore` — durable stores behind the existing ports.
  Recall retrieves candidates per-backend (HNSW ANN ∪ lexical on Postgres, a
  bounded window on SQLite) and ranks them with **shared** code, so results
  cannot drift between deployments (ADR 0004).
- Run persistence splits cheap synchronous mutation from explicit awaited
  checkpoints, keeping IO off the streaming hot path.
- Alembic migrations with an HNSW cosine index, applied and verified against a
  live Postgres 16 + pgvector.
- `RedisEventBus` — cross-process fan-out that extends rather than replaces the
  in-process bus, so local delivery keeps its latency and a Redis outage
  degrades to single-node instead of failing.
- `HostedEmbedder` — OpenAI-compatible embeddings that fall back to the
  deterministic local embedder on any failure.
- `docker-compose.yml` + API `Dockerfile` for the server deployment.

**Verification** — 192 tests. The store contract suite runs against all three
backends; migrations are asserted not to have drifted from the models; Redis
cross-node delivery and no-Redis degradation are both covered. Verified for
real against Postgres 16 + pgvector and Redis 7: migrations applied, HNSW index
created, and runs, steps and memories all survived a process restart.

Storage stays opt-in — with no `JARVIS_DATABASE_URL` the system is fully
in-process, and the offline suite (174 tests) still runs with no server.

## Milestone 4 — delivered

**Built**
- **The agentic loop.** Until now tools were advertised to models and never
  run. The runtime now executes requested calls, feeds results back, and loops
  until the model stops asking or hits a ceiling — with a stated cutoff rather
  than a silently truncated answer.
- **Provider tool-call assembly.** Both adapters accumulate the JSON fragments
  providers stream and emit only complete calls; each also replays a tool
  exchange in its own wire shape (Anthropic's `tool_result` user turns,
  OpenAI's `tool_calls` array).
- **Approvals (ADR 0005).** Dangerous tools suspend for a human decision, with
  timeout-as-denial and refusal reported to the model as information. A global
  gate shows the exact call being authorised.
- **System tools** — filesystem, shell and HTTP, contained by a workspace root
  that is checked after symlink resolution, with argv execution (no shell) so
  metacharacters cannot chain a second command.
- **MCP client.** Servers mount as tool namespaces over JSON-RPC/stdio, which
  is how GitHub, Slack, Notion, Stripe and the rest arrive without a bespoke
  adapter each. Imported tools do not choose their own permission tier.
- **Hash-chained audit log**, written before execution, with tamper detection.
- Direct tool invocation over HTTP, through the same permission wall.

**Verification** — 262 tests, including the loop's shape, approval grant/deny/
expiry, workspace escape via `../` *and* symlink, shell metacharacter
injection, audit tamper and deletion detection, and an MCP client driven
against a real JSON-RPC server subprocess. Plus a Playwright run that parks a
real dangerous call, sees the gate render the exact command, approves it, and
confirms a denied command never ran.

## Milestone 5 — delivered

**Built**
- **Extractors** for PDF, DOCX (including tables), PPTX (including speaker
  notes), XLSX, CSV, HTML, Markdown, code and plain text — each emitting blocks
  that carry the document's own idea of *where*: `p. 4`, `slide 2`,
  `Revenue!1:40`, `lines 1–80`, or a section heading.
- **Locator-preserving chunking** (ADR 0006). Packed blocks widen the locator
  (`pp. 3–4`); split blocks narrow it (`p. 7 (part 2/3)`). A citation never
  claims more or less than the passage it points at.
- **Ingestion** of files, folders, URLs and pasted text, with content
  fingerprinting so re-ingesting is a no-op, per-file error reporting so one
  corrupt PDF cannot abort a repository, and explicit deferral for images and
  audio rather than silent empty documents.
- **Knowledge stores** (in-memory and SQL) that keep documents separate from
  memory but rank with the *same* shared ranker, plus an HNSW index on chunk
  embeddings and a migration that no longer drops the existing vector indexes.
- **Citations** as a first-class type, returned by the API and by the
  agent-facing `search_documents` tool, which hands the reference over with the
  passage and marks the content untrusted.
- A **Knowledge page** that leads with the citation rather than the snippet.

**Verification** — 319 tests with backends live. Extraction is tested against
real PDF/DOCX/PPTX/XLSX files generated by the libraries people actually use,
not hand-rolled fixtures. Plus a browser run that ingests through the UI,
retrieves with a visible citation, checks the agent tool returns the same
reference, and confirms a forgotten document stops being retrievable.

## Milestone 6 — delivered

**Built**
- **A graph engine** over agent, tool, approval, branch, parallel, wait and
  note steps, with `on_error` routing, optional steps, an explicit `terminal`
  flag, and a step ceiling so a user-authored cycle terminates.
- **Durable suspension** (ADR 0007) — the fix for M4's stated limitation. The
  cursor and context live in a row, so an approval step returns rather than
  parking on an event, and a new process can resume the run.
- **Structured conditions** (`field` / `op` / `value`) rather than expression
  strings, and dotted-path interpolation rather than a template engine: a
  workflow definition is user input, and this process owns a shell.
- **Triggers** — manual, schedule, and event patterns over the same bus the UI
  reads, with a scheduler that recovers suspended runs on boot.
- Three starter workflows, seeded on first run, covering a linear chain, a
  branch with an approval, and a fan-out.
- API and a Workflows page showing each graph, which steps pause for a human,
  and how every run was triggered.

**Verification** — 381 tests with backends live. Includes a test that starts a
workflow on one engine and database connection, disposes it, and finishes the
run on a *new* engine — the restart property the milestone exists for.

## Milestone 7 — delivered

**Built**
- **A voice session state machine** — idle → waiting-for-wake → listening →
  thinking → speaking — driven by transcripts rather than audio, so the same
  logic serves browser recognition and hosted transcription unchanged.
- **Barge-in that cancels generation as well as playback** (ADR 0008), with
  history recording what was *spoken*, not what was generated, marked
  `[interrupted here]` when truncated. A partial transcript interrupts; only a
  final one is answered.
- **A sentence segmenter** that releases a unit as soon as it is a complete
  thought — so speech starts before generation finishes — and refuses to split
  on abbreviations or decimals, because a fragment spoken aloud cannot be
  un-said.
- **Wake-word detection** within one edit, at the start of an utterance only,
  keeping the request that followed it: "Jarvis, what's on today" is one turn.
- **Speech ports with offline implementations** and hosted Whisper/TTS adapters
  behind them, both degrading to a silent turn rather than a crash.
- `WS /v1/voice`, `POST /v1/voice/transcribe`, and a ⌘⇧V overlay that drives
  browser recognition, interrupts on the first sign of speech, and takes typing
  where there is no recogniser.

**Verification** — 426 tests with backends live, plus a browser suite that
stubs only `SpeechRecognition` and drives the real socket, session, segmenter
and speaker. Its central assertion: after an interruption the surviving reply
is a strict *prefix* of what had been generated, and `voice.interrupted`
reached the bus.

**Found by testing** — the offline speaker was unpaced, so a turn completed in
milliseconds and no human could ever interrupt it. Pacing is now on by default
and disabled only in the unit suite.

## Milestone 8 — delivered

**Built**
- **A browser behind the computer port**, perceived as an *element index* built
  from the DOM — ref, role, accessible name, enabled, secret — rather than as
  pixels the model must squint at (ADR 0009). Screenshots are still captured,
  as evidence rather than as the action space.
- **A permission wall that grades the target, not the verb**, in one place
  called from one choke point: navigation off the allowlist escalates,
  credential and payment fields are refused outright with no approval path,
  committing clicks escalate quoting the page's own words, and a ref that is
  not in the current snapshot is refused as acting blind.
- **Budgets** — step ceiling, wall-clock deadline, and loop detection, because
  an agent driving a browser can burn an afternoon without ever failing.
- **Evidence and containment** — screenshots kept with each step and its
  ruling, page text handed to the model inside an explicit untrusted envelope,
  and the whole capability off unless `enable_computer` is set.
- Research and shopping agents can now browse; `GET /v1/computer`,
  `GET /v1/computer/screen`, and a Computer page showing the live screen, the
  wall, and every action as the sentence a human would have approved.

**Verification** — 477 tests with backends live, including five against real
Chromium, plus a browser suite that drives the kernel's browser through the
kernel's own API and asserts the wall holds: a credential field refused with no
approval offered, a committing click parked in the approval gate quoting the
page, and the denied click on the record as denied.

**Found by testing** — secret-field detection was substring-based, so "Keep
shopping" matched the `pin` hint and an ordinary link was classified as a
credential field. Only the real-browser test surfaced it; the scripted site had
no such text. Matching is now per token.

## Milestone 9 — delivered

**Built**
- **Modes as narrowings, not themes** (ADR 0010). Business, Coding and Research
  each constrain three seams — which agents can be routed to, which tools
  survive the intersection with the agent's own allowlist, and which memory
  namespace is read and written. Personal is the unconstrained default, so
  switching *out* of it is what narrows.
- **The subtract-only invariant**, enforced and tested: a mode cannot grant a
  tool the agent lacks, cannot reach an agent the catalog lacks, and cannot
  raise a permission. A briefing is context, never capability.
- **Fail-closed resolution** — an unknown mode is refused rather than defaulted,
  because the default is the unconstrained one; and pinning an agent is checked
  against the *mode's* catalog so `agent_id` is not a way around it.
- **Document generation** — outline first, then each section written against it
  with passages retrieved per section, citations captured at write time and
  filtered to the markers that actually appear. Markdown and self-contained
  HTML export.
- `GET /v1/modes`, mode-aware `/v1/chat` and `/v1/route`, the `/v1/documents`
  surface, a sidebar mode switcher that states what each mode costs you, and a
  Documents page that shows the outline landing before any prose.

**Verification** — 543 tests with backends live, plus a browser suite that
proves the narrowing is held by the kernel and not merely by the client:
pinning an excluded agent is refused over HTTP, an unknown mode is refused, and
routing preview stays inside the mode.

**Found by testing** — the routing fallback returned a hardcoded
`chief_of_staff` regardless of which registry was asked, so an unmatched
request in coding mode would have escaped straight to an agent coding mode
excludes. Also: `memory_scopes` had been declared on `AgentSpec` since M1 and
never read — dead config that modes made real.

## Milestone 10 — delivered

**Built**
- **A secrets vault whose real work is redaction** (ADR 0011). AES-256-GCM with
  the name as associated data; the model names a secret (`${vault:stripe}`) and
  never holds one, resolved inside the tool registry *after* the audit write.
  Every known value is scrubbed from logs, events, audit entries and exception
  messages — the paths a secret actually escapes through.
- **Cost governance that is a control, not a report.** Checked before each call
  against a deliberately conservative estimate, enforced in the router because
  that is where every call passes. A soft ceiling parks in the same approval
  gate as a dangerous tool; a hard ceiling refuses with no path around it.
- **Everything durable is durable.** The vault, approvals, generated documents
  and agent metrics all have SQL backings behind the Protocols written for the
  swap — retiring three caveats carried since M1, M4 and M9.
- **Load and chaos tests** — concurrent runs, concurrent memory writes, bus
  backpressure under 2,000 messages, a provider failing half the time, a
  circuit opening, budget refusal under twenty concurrent callers, and
  abandoned mid-stream runs.
- `GET /v1/secrets` (names and hints, never values), `PUT`/`DELETE`,
  `GET /v1/budget`, a Settings page, and `python -m jarvis.security.keygen`.

**Verification** — 583 tests with backends live, plus a browser suite that
stores a secret through the UI and asserts it appears in *no response the page
received* and in no audit entry. Durability verified across a real process
restart on Postgres: secret, approval decision, agent metrics and a generated
document all survived.

**Found by testing** — the router only caught `ProviderError`, so an adapter
raising a connection reset or an unwrapped decode error killed the request with
no fallback at all — the exact failure a fallback chain exists for.

## Phase 11 — delivered

**M11.1 — the audit.** Eleven findings in `docs/INTELLIGENCE-AUDIT.md`, six
fixed, separated by what it takes to prove them: structural defects are
arithmetic and were fixed immediately; behavioural ones are hypotheses and wait
for a corpus. That ordering is a deliberate correction to the phase plan —
improving prompts before expanding the evaluation would mean building the ruler
after cutting the wood.

- **The two-stage router had become a one-stage router.** M10 raised the
  ambiguity threshold to 0.55 to stop homonyms deciding; nothing raised the
  *scores*, and one keyword tops out at 0.40. 78% of requests were escalating
  to the arbiter — latency and spend, never an error, so nothing said so. The
  threshold was not wrong; the score was measuring how much text matched rather
  than how much the match *distinguished* an agent (ADR 0012). Escalation
  78% → 48%, accepted 13 → 18, actively wrong 3 → 1.
- **Fourteen agents declared tools nothing implemented**, twelve with none that
  resolved, while `needs_tools` routed them to tool-capable models to use them.
  The Memory Agent's tool was `memory`; the registered ones are `memory_search`
  and `memory_write`, so the agent that curates memory could only talk about
  curating it.
- **Wiring those tools exposed a hole in the mode narrowing.** `memory_search`
  called the store with no scope, which means every scope — one path to memory
  honoured the narrowing and another, reachable by the model, did not.

**M11.2 — the corpus.** 288 cases across routing, planning, tool selection,
memory, research, execution, workflows, documents, coding and business, each
carrying expected behaviour, defensible and actively-wrong agents, expected
tools, success criteria and a confidence (ADR 0015). Two-thirds are free, so CI
runs them on every push against a committed baseline; the exit code answers
"did this change make things worse".

**Found by building it** — recall ranking scored a stopword hit exactly like a
real one, so "what are the margins like" ranked a memory about consulting above
the one stating the gross margin, which scored zero and never appeared.
Underneath: the router had matched by prefix since M1 while recall matched by
equality.

**M11.4 — the vault.** `ObsidianStore` behind the existing `MemoryStore` port.
The design turns on one question — which copy is the truth when the user edits
a note — and the answer is that there is only one copy (ADR 0013). A memory is
a line carrying an Obsidian block reference; the body belongs to the user and
the frontmatter to Jarvis; unrecognised frontmatter is preserved verbatim
because a vault has plugins.

"Every completed task leaves knowledge behind" needed no hook: the runtime has
written a memory after every run since M1, and pointing memory at a vault was
all it took.

**M11.5 — the Chief of Staff.** Delegation closes audit finding F4:
`collaborators` had been read by nothing while two prompts promised
coordination, so every multi-specialist request produced a *description* of the
delegation. And a recommendation engine with no model in the loop — nine
deterministic detectors, ranked `impact × urgency × confidence`, because a
model's opinion cannot be corrected when it is wrong (ADR 0014).

**Found by building it** — an episodic memory lands in two files, and the
journal *pointer* was being counted as a second memory, so every episodic fact
was recalled twice and one lease renewal appeared as two deadlines. It took a
subsystem *consuming* memory to notice there were two of everything.

**M11.6 — the briefing.** "Feels like it was written by an experienced
executive chief of staff" decomposes into four checkable properties: it leads
with the one thing, it says what it does not know, it does not pad, and it is
short. A model writes the opener; everything else is the arithmetic.

**Found by the browser suite** — the echo provider's output was being served as
the opener. It echoes the prompt, it is short and plausible, and it passed every
guard, so the briefing opened with `[echo:52f8ee68] Today: …` and reported
itself model-written. The fallback chain means that happens whenever a real
provider is configured but failing, which is exactly when nobody is watching.
Also a 500 on dismissing everything, and duplicate React keys silently omitting
children.

**What is not done.** M11.3 — the behavioural half of the audit (output
contracts, tool-aware prompting, the house rule that contradicts the planning
agents) — needs a provider key. The corpus is built and calibrated; a full pass
costs a few dollars. Rewriting prompts without it would be exactly the habit
this phase exists to break.

## Definition of done (every milestone)

1. Tests written alongside the code, suite green.
2. `ruff` + `mypy` clean on changed packages.
3. Docs updated (architecture deltas, ADR if a decision changed).
4. Committed with a message that explains the *why*.
