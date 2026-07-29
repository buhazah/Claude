"""What agents actually produce: planning, research, coding, business, execution.

Every case here runs a turn, so every case here costs money. That buys a
different obligation from the routing suite: each one has to be worth a call.
The rule applied throughout is that a case must be able to *fail* in a way that
points at a specific sentence in a specific prompt. "Is this good writing" is
not that. "Did the plan name an owner for each step, as the Planner's prompt
says it will" is.

Confidence is set honestly and it is often low. Checking that a financial
answer contains two numbers is a genuine proxy for "quantified"; checking that
a strategy answer contains the word "stop" is a much weaker proxy for "said
what to stop doing", and is marked 0.4 so the weighted score does not treat the
two as equal evidence.

Where the real question needs a human — tone, judgement, whether the reasoning
holds — the case says so in `behaviour` and the transcript is printed in the
report. Those are not scored, and pretending otherwise is how an evaluation
harness starts lying to the person who built it.
"""

from __future__ import annotations

from eval.checks import (
    Check,
    asks_a_question,
    avoids,
    cites,
    covers,
    mentions,
    names_an_owner,
    no_filler,
    no_preamble,
    not_a_dodge,
    options,
    prose,
    quantified,
    speakable,
    states_assumptions,
    structured,
    under_words,
    words_between,
)
from eval.scoring import Case, Suite, Tier

_counters: dict[str, int] = {}


def _case(
    suite: str,
    agent: str,
    request: str,
    *,
    behaviour: str,
    must: tuple[Check, ...] = (),
    should: tuple[Check, ...] = (),
    confidence: float = 0.6,
    memories: tuple[str, ...] = (),
    mode: str = "",
) -> Case:
    _counters[suite] = _counters.get(suite, 0) + 1
    return Case(
        id=f"{suite}-{_counters[suite]:03d}",
        suite=suite,
        request=request,
        behaviour=behaviour,
        agent=agent,
        mode=mode,
        memories=memories,
        must=must,
        should=should,
        confidence=confidence,
        tier=Tier.TURN,
    )


# ── Planning ──────────────────────────────────────────────────────────────────
#
# The Planner's prompt makes four checkable promises: owned steps, an input and
# output per step, a done condition, and the critical path. F8 of the audit
# noted that none of them is required in a way the output has to honour. These
# cases are how that hypothesis gets tested rather than assumed.

PLANNING = (
    _case(
        Suite.PLANNING,
        "planner",
        "I want to launch a supplement brand in eight weeks. Plan it.",
        behaviour="Ordered steps, each owned, with a critical path. Five real steps "
        "beat fifteen aspirational ones — the prompt says so, so check the count.",
        must=(structured(),),
        should=(
            names_an_owner(),
            mentions("critical path", "blocker", "depends"),
            under_words(500),
        ),
        confidence=0.7,
    ),
    _case(
        Suite.PLANNING,
        "planner",
        "Migrate our billing from Stripe Checkout to Stripe Billing without downtime.",
        behaviour="A technical migration plan. The interesting failure is a plan with "
        "no rollback and no cutover moment.",
        must=(structured(),),
        should=(
            mentions("rollback", "revert", "back out"),
            mentions("cutover", "switch", "migrate"),
        ),
        confidence=0.7,
    ),
    _case(
        Suite.PLANNING,
        "planner",
        "Two of my five steps just failed. The supplier is out of stock and the "
        "designer quit. Re-plan.",
        behaviour="Re-planning is a stated responsibility. Does it replan, or "
        "restate the original plan with sympathy attached?",
        must=(structured(),),
        should=(mentions("instead", "alternative", "replace", "switch"), no_preamble()),
        confidence=0.6,
    ),
    _case(
        Suite.PLANNING,
        "planner",
        "Plan my week. I have a board pack due Thursday, two customer calls, and "
        "I want to ship the pricing page.",
        behaviour="Sequencing against real constraints, not a generic weekly template.",
        must=(structured(),),
        should=(mentions("thursday"), mentions("board"), under_words(450)),
        confidence=0.7,
    ),
    _case(
        Suite.PLANNING,
        "planner",
        "What is the shortest path to £10k monthly recurring revenue from where "
        "I am now, which is £900 and one channel?",
        behaviour="Should notice it does not know enough and say so while still "
        "planning — the house rules require exactly that combination.",
        should=(states_assumptions(), quantified(3), structured()),
        confidence=0.5,
    ),
    _case(
        Suite.PLANNING,
        "chief_of_staff",
        "Handle it: the Q3 board pack, the hiring plan, and the office lease all land next week.",
        behaviour="Does it sequence and delegate, or restate the problem back? The "
        "delegation half cannot actually happen yet (audit F4) — what to read for "
        "is whether it *claims* to have delegated.",
        should=(structured(), mentions("board", "hiring", "lease"), no_preamble()),
        confidence=0.5,
    ),
    _case(
        Suite.PLANNING,
        "chief_of_staff",
        "I have 90 minutes and four things on fire. Pick.",
        behaviour="One recommendation, not a menu. Protecting attention is its remit.",
        should=(under_words(220), no_preamble()),
        confidence=0.5,
    ),
    _case(
        Suite.PLANNING,
        "product_manager",
        "Write a PRD for a referral programme for our supplement store.",
        behaviour="The prompt requires a user problem, a success metric, a scope "
        "boundary and an explicit out-of-scope. All four are checkable.",
        must=(structured(),),
        should=(
            mentions("metric", "measure", "success"),
            mentions("out of scope", "not building", "explicitly out", "non-goal"),
            mentions("problem"),
        ),
        confidence=0.75,
    ),
    _case(
        Suite.PLANNING,
        "product_manager",
        "Our backlog has 40 items. How do I decide what is next?",
        behaviour="Should cut against an outcome, not describe prioritisation frameworks.",
        should=(no_preamble(), mentions("metric", "outcome", "impact")),
        confidence=0.5,
    ),
    _case(
        Suite.PLANNING,
        "architect",
        "We are at 12 requests a second and falling over. What do we change first?",
        behaviour="Lead with the decision and its trade-off, not a survey of options — "
        "the survey is the failure this prompt was written against.",
        should=(mentions("trade-off", "tradeoff", "cost", "downside", "give up"), prose()),
        confidence=0.6,
    ),
)

# ── Research ──────────────────────────────────────────────────────────────────

RESEARCH = (
    _case(
        Suite.RESEARCH,
        "research",
        "What is the current state of solid-state battery commercialisation?",
        behaviour="Separate established from contested, and admit what it cannot "
        "source. Read the transcript for whether the citations are real.",
        should=(
            mentions("established", "consensus", "widely", "confirmed"),
            mentions("contested", "disputed", "disagree", "unclear"),
            states_assumptions(),
        ),
        confidence=0.6,
    ),
    _case(
        Suite.RESEARCH,
        "research",
        "Compare the three biggest UK oat milk brands on positioning and price.",
        behaviour="A comparison is the artefact. Three named brands with figures, "
        "or a paragraph about how one might compare them?",
        must=(structured(),),
        should=(quantified(3), no_preamble()),
        confidence=0.65,
    ),
    _case(
        Suite.RESEARCH,
        "research",
        "Is creatine safe for people over 60? I want the actual evidence.",
        behaviour="Explicitly asked for evidence, so an uncited answer is a failure "
        "of the prompt's central promise.",
        should=(cites(), mentions("study", "trial", "evidence", "review"), not_a_dodge()),
        confidence=0.6,
    ),
    _case(
        Suite.RESEARCH,
        "research",
        "Two sources say our market is £2bn and two say £600m. Which is right?",
        behaviour="Reconciling conflicting sources is a stated responsibility. The "
        "failure is picking one silently, or refusing to pick at all.",
        should=(
            mentions("definition", "scope", "measure", "methodology", "different"),
            not_a_dodge(),
        ),
        confidence=0.6,
    ),
    _case(
        Suite.RESEARCH,
        "research",
        "What are our competitors doing that we are not?",
        behaviour="No competitors named in the request, so it must ask or assume "
        "out loud. Inventing named competitors is the failure.",
        should=(states_assumptions(), asks_a_question()),
        confidence=0.5,
    ),
    _case(
        Suite.RESEARCH,
        "learning",
        "Explain eventual consistency to me. I know SQL but not distributed systems.",
        behaviour="Front-load what unlocks the rest, and include a ten-minute first "
        "exercise — the prompt promises one, so its absence is checkable.",
        should=(mentions("exercise", "try", "practice", "do this"), no_preamble()),
        confidence=0.65,
    ),
    _case(
        Suite.RESEARCH,
        "learning",
        "I want to be dangerous at financial modelling in six weeks.",
        behaviour="A curriculum with progression, not a reading list.",
        must=(structured(),),
        should=(mentions("week"), mentions("exercise", "build", "practice")),
        confidence=0.6,
    ),
    _case(
        Suite.RESEARCH,
        "data_analyst",
        "Sales are up 30% but profit is flat. What is going on?",
        behaviour="State the question, the method, the result, and why it might be "
        "wrong. The last part is the one models skip.",
        should=(
            mentions("might be wrong", "caveat", "however", "could also", "assuming"),
            mentions("margin", "cost", "discount", "mix"),
            quantified(1),
        ),
        confidence=0.65,
    ),
    _case(
        Suite.RESEARCH,
        "data_analyst",
        "Users who use feature X churn less. Should we push everyone to feature X?",
        behaviour="A correlation trap, stated as plainly as one can be. Presenting "
        "it as cause is a hard failure of an explicit prompt instruction.",
        must=(mentions("correlat", "caus", "confound", "selection"),),
        should=(not_a_dodge(),),
        confidence=0.85,
    ),
    _case(
        Suite.RESEARCH,
        "vision",
        "Describe what is in this screenshot.",
        behaviour="No image is attached. The correct answer says so; describing an "
        "imaginary screenshot is the failure.",
        must=(mentions("no image", "not attached", "cannot see", "can't see", "don't see"),),
        confidence=0.8,
    ),
)

# ── Coding ────────────────────────────────────────────────────────────────────

CODING = (
    _case(
        Suite.CODING,
        "coding",
        "Our FastAPI endpoint returns 200 with an empty body maybe 1% of the time. "
        "Where would you look?",
        behaviour="Does it ask for the code or invent a diagnosis? Inventing is the "
        "failure the prompt's 'read the surrounding code first' rule exists for.",
        should=(asks_a_question(), states_assumptions(), no_preamble()),
        confidence=0.6,
    ),
    _case(
        Suite.CODING,
        "coding",
        "Write a Python function that parses an ISO 8601 duration into seconds.",
        behaviour="Concrete enough to just do. Code plus tests is the promise; code "
        "with no test is a failure of a stated rule.",
        must=(
            mentions(
                "def ",
            ),
        ),
        should=(mentions("test", "assert"), mentions("```")),
        confidence=0.8,
    ),
    _case(
        Suite.CODING,
        "coding",
        "Review this: `def total(items): return sum([i.price for i in items])`",
        behaviour="A real review names something specific. Praise with no finding "
        "is the failure mode.",
        should=(mentions("none", "empty", "decimal", "float", "generator", "typing", "type"),),
        confidence=0.55,
    ),
    _case(
        Suite.CODING,
        "coding",
        "Does the auth module pass its tests?",
        behaviour="It has not run anything. 'Never claim something passes that you "
        "have not run' is an explicit rule, so a confident yes is a hard failure.",
        must=(avoids("yes, they pass", "all tests pass", "the tests pass"),),
        should=(mentions("run", "check", "haven't", "have not", "cannot confirm"),),
        confidence=0.8,
    ),
    _case(
        Suite.CODING,
        "coding",
        "Refactor our 900-line views.py. Where do I start?",
        behaviour="Smallest change that fully solves the problem — a big-bang rewrite "
        "recommendation contradicts the prompt.",
        should=(mentions("smallest", "first", "start with", "incremental", "one at a time"),),
        confidence=0.5,
    ),
    _case(
        Suite.CODING,
        "architect",
        "Design the data model for a multi-tenant invoicing system.",
        behaviour="Name the seams where requirements will change and make those the "
        "interfaces. Also: what is deliberately not being built.",
        must=(structured(),),
        should=(
            mentions("tenant"),
            mentions("not building", "out of scope", "deliberately", "later", "not doing"),
        ),
        confidence=0.65,
    ),
    _case(
        Suite.CODING,
        "architect",
        "Postgres or DynamoDB for an event log we will query by time range?",
        behaviour="A decision with its trade-off, not a comparison table with a "
        "shrug at the bottom.",
        should=(prose(), mentions("because", "since", "trade-off", "cost")),
        confidence=0.6,
    ),
    _case(
        Suite.CODING,
        "automation",
        "Every Monday I copy last week's numbers into a spreadsheet and email them. Automate it.",
        behaviour="Trigger, steps, failure handling, approval gate — four named "
        "parts, all checkable.",
        must=(structured(),),
        should=(
            mentions("trigger", "every monday", "schedule"),
            mentions("fail", "error", "retry"),
            mentions("approv", "confirm", "review"),
        ),
        confidence=0.7,
    ),
    _case(
        Suite.CODING,
        "automation",
        "Can you automate replying to customer emails entirely?",
        behaviour="Should push back on 'entirely'. 80% reliably beats 100% flakily "
        "is a stated preference, and this is where it applies.",
        should=(mentions("approv", "review", "human", "not entirely", "partly"),),
        confidence=0.6,
    ),
    _case(
        Suite.CODING,
        "security",
        "Is it safe to paste my Stripe key into this script?",
        behaviour="Refuse, and name the alternative. A hedge is a failure here.",
        must=(not_a_dodge(),),
        should=(
            mentions("no", "don't", "do not", "avoid"),
            mentions("environment", "vault", "secret"),
        ),
        confidence=0.7,
    ),
)

# ── Business ──────────────────────────────────────────────────────────────────

BUSINESS = (
    _case(
        Suite.BUSINESS,
        "ceo",
        "Revenue is flat for the third month. Two product lines, one profitable.",
        behaviour="Lead with a decision and its cost, not a consultancy essay. "
        "'Say what to stop doing' is explicit in the prompt.",
        should=(mentions("stop", "kill", "cut", "drop"), prose(), under_words(450)),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "ceo",
        "Should I raise money or stay bootstrapped?",
        behaviour="One recommendation with reasoning, not a menu. The menu is the "
        "failure mode this prompt names.",
        should=(mentions("i would", "recommend", "you should", "my view"), prose()),
        confidence=0.55,
    ),
    _case(
        Suite.BUSINESS,
        "financial_analyst",
        "Should I take a £40k loan at 11% to buy stock for Q4?",
        behaviour="Quantify, show the downside, and say plainly which numbers it does not have.",
        must=(quantified(3),),
        should=(states_assumptions(), mentions("downside", "worst", "if it doesn't", "risk")),
        confidence=0.75,
    ),
    _case(
        Suite.BUSINESS,
        "financial_analyst",
        "Model our runway. £22k in the bank, £9k monthly burn, £3k monthly revenue "
        "growing 15% month on month.",
        behaviour="Every number is supplied, so an unquantified answer has no excuse. "
        "The assumption that most affects the result is the growth rate.",
        must=(quantified(4),),
        should=(mentions("month"), mentions("assum", "if growth", "sensitiv")),
        confidence=0.85,
    ),
    _case(
        Suite.BUSINESS,
        "marketing",
        "Position our magnesium supplement against the big three.",
        behaviour="A positioning claim it can defend, not adjectives. 'No adjectives "
        "that survive without data' is the prompt's own test.",
        should=(no_filler(), mentions("because", "evidence", "claim", "proof")),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "marketing",
        "Plan our channels for the next quarter. Budget is £6k.",
        behaviour="Audience, message, asset, budget, metric — five named parts per "
        "channel, and the budget must actually add up to £6k.",
        must=(structured(),),
        should=(quantified(4), mentions("metric", "measure", "cpa", "roas", "conversion")),
        confidence=0.7,
    ),
    _case(
        Suite.BUSINESS,
        "sales",
        "Write outreach to the head of ops at a 200-person logistics company.",
        behaviour="Short, specific, leads with their problem, ends with a dated next "
        "step. Generic outreach is explicitly forbidden.",
        should=(under_words(220), mentions("?"), no_filler()),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "sales",
        "Three deals have been 'nearly closed' for two months. What now?",
        behaviour="Every deal has a next step with a date. Sympathy without a date is the failure.",
        should=(mentions("date", "by ", "deadline", "this week", "friday"), structured()),
        confidence=0.55,
    ),
    _case(
        Suite.BUSINESS,
        "copywriter",
        "Headline for a magnesium supplement aimed at people who sleep badly.",
        behaviour="Three options that differ in angle, each with a line on what it "
        "bets the reader cares about. This is the M10 fix; it is here to stay fixed.",
        must=(options(3),),
        should=(no_filler(), under_words(200)),
        confidence=0.9,
    ),
    _case(
        Suite.BUSINESS,
        "copywriter",
        "Subject line for the cart abandonment email.",
        behaviour="Same contract as any short-form ask. One option is a regression.",
        must=(options(3),),
        should=(no_filler(),),
        confidence=0.9,
    ),
    _case(
        Suite.BUSINESS,
        "copywriter",
        "Rewrite this: 'We leverage cutting-edge technology to unlock seamless "
        "growth for forward-thinking brands.'",
        behaviour="The input is made entirely of the words the prompt bans. Echoing "
        "any of them back is an unambiguous failure.",
        must=(no_filler(),),
        confidence=0.9,
    ),
    _case(
        Suite.BUSINESS,
        "legal",
        "Can I use a customer's logo on my website without asking?",
        behaviour="A usable answer with the caveat stated once. Hedging into "
        "uselessness and giving confident legal advice are both failures.",
        must=(not_a_dodge(),),
        should=(mentions("not legal advice", "qualified", "solicitor", "lawyer"), under_words(400)),
        confidence=0.7,
    ),
    _case(
        Suite.BUSINESS,
        "legal",
        "Review this clause: 'Either party may terminate at any time for any reason.'",
        behaviour="Flag risk by severity with the clause reference — both parts are "
        "in the prompt and both are checkable.",
        should=(
            mentions("risk", "severity", "high", "medium", "low"),
            mentions("notice", "period"),
        ),
        confidence=0.65,
    ),
    _case(
        Suite.BUSINESS,
        "support",
        "A customer's order is three weeks late and they want a refund and an "
        "apology. Draft the reply.",
        behaviour="Acknowledge the specific problem, resolve or escalate with a "
        "timeline, no apology template.",
        should=(
            mentions("three weeks", "3 weeks", "delay"),
            avoids("we sincerely apologize for any inconvenience"),
        ),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "life_coach",
        "I am working twelve hour days and it is not helping.",
        behaviour="A question that unsticks, plus one concrete thing to do before "
        "speaking again. The M10 fix; both halves are required.",
        must=(asks_a_question(),),
        should=(mentions("before", "today", "tonight", "this week", "try"), under_words(250)),
        confidence=0.8,
    ),
    _case(
        Suite.BUSINESS,
        "health",
        "I sleep five hours, train four times a week, and I am always sore.",
        behaviour="A specific programme with progression, and a clear line on when "
        "this needs a doctor rather than a plan.",
        should=(structured(), mentions("sleep"), mentions("doctor", "gp", "clinician", "medical")),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "voice",
        "What is on my plate today?",
        behaviour="Spoken output: two or three sentences, no lists, no markdown, no "
        "URLs. The only agent with a hard shape contract already.",
        must=(speakable(),),
        should=(words_between(5, 80),),
        confidence=0.85,
    ),
    _case(
        Suite.BUSINESS,
        "voice",
        "Give me the full breakdown of every project and its status.",
        behaviour="Asked for something that cannot be spoken. Should compress, not "
        "produce a bulleted report read aloud.",
        must=(speakable(),),
        confidence=0.8,
    ),
    _case(
        Suite.BUSINESS,
        "meeting",
        "Notes: Ali wants the launch moved to May. Ben disagrees, says the copy is "
        "not ready. We agreed to decide Friday. Sam will cost the delay.",
        behaviour="Decisions, disagreements and owned actions — not a transcript.",
        must=(structured(),),
        should=(mentions("sam"), mentions("friday"), mentions("disagree", "ben")),
        confidence=0.8,
    ),
    _case(
        Suite.BUSINESS,
        "email",
        "Draft a reply declining a partnership without burning the relationship.",
        behaviour="Reads like the user wrote it. Length is the tell: a five-paragraph "
        "decline is not what anyone sends.",
        should=(under_words(200), no_filler(), no_preamble()),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "creative_director",
        "Give me a direction for the rebrand. We sell recovery supplements to "
        "people who train hard and sleep badly.",
        behaviour="A point of view with reference, palette, typography and tone — and "
        "what it is deliberately not.",
        should=(
            covers(2, "palette", "colour", "color", "typograph", "type", "reference"),
            mentions("not ", "avoid", "away from"),
        ),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "designer",
        "Design the empty state for a dashboard with no data yet.",
        behaviour="Every state, not just the happy path — and the one thing the user "
        "does on this screen.",
        should=(mentions("one thing", "primary", "cta", "action"), structured()),
        confidence=0.6,
    ),
    _case(
        Suite.BUSINESS,
        "social_media",
        "Three posts about our launch, for LinkedIn, X and Instagram.",
        behaviour="Platform-native and not cross-posted. Three identical posts with "
        "different hashtags is the failure.",
        must=(structured(),),
        should=(mentions("linkedin"), mentions("instagram"), no_filler()),
        confidence=0.7,
    ),
)

# ── Multi-step execution ──────────────────────────────────────────────────────
#
# Requests that cannot be answered in one move. What is being read for is
# whether the agent sequences its own work or produces the first step and stops.

EXECUTION = (
    _case(
        Suite.EXECUTION,
        "chief_of_staff",
        "Find out what our three biggest competitors charge, work out where that "
        "leaves us, and tell me what to change.",
        behaviour="Three dependent steps. Does it do them in order, or answer the easiest one?",
        should=(structured(), mentions("price", "pricing", "charge")),
        confidence=0.5,
    ),
    _case(
        Suite.EXECUTION,
        "research",
        "Read the workspace, work out what this project is, and summarise it for "
        "someone joining tomorrow.",
        behaviour="Needs a tool call before it can answer anything. Answering from "
        "imagination is the failure.",
        should=(states_assumptions(),),
        confidence=0.6,
    ),
    _case(
        Suite.EXECUTION,
        "financial_analyst",
        "Work out our unit economics, then tell me the single price change with the "
        "biggest effect.",
        behaviour="Analysis then recommendation. Stopping after the analysis is the "
        "common failure.",
        should=(quantified(3), mentions("recommend", "i would", "change", "raise", "lower")),
        confidence=0.6,
    ),
    _case(
        Suite.EXECUTION,
        "ceo",
        "Compare hiring a salesperson against spending the same money on ads, then decide.",
        behaviour="A comparison that ends in a decision. Ending in 'it depends' is the failure.",
        must=(not_a_dodge(),),
        should=(quantified(2), mentions("i would", "recommend", "choose", "go with")),
        confidence=0.65,
    ),
    _case(
        Suite.EXECUTION,
        "coding",
        "List the files in the workspace, then tell me what is there. If the "
        "directory is empty, say so plainly rather than guessing.",
        behaviour="The tool loop end to end. Inventing a file listing is the failure, "
        "and it is the one that matters most in this whole corpus.",
        should=(mentions("empty", "no files", "nothing"),),
        confidence=0.7,
    ),
    _case(
        Suite.EXECUTION,
        "planner",
        "I have a launch, a board pack and a house move in the same fortnight. "
        "Sequence it and tell me what I should drop.",
        behaviour="Sequencing plus a cut. Refusing to cut anything is the failure.",
        should=(mentions("drop", "cut", "postpone", "delay", "move"), structured()),
        confidence=0.6,
    ),
    _case(
        Suite.EXECUTION,
        "chief_of_staff",
        "Everything is late. Fix it.",
        behaviour="Almost no information. Should establish what 'everything' is "
        "before acting, without refusing to engage.",
        must=(not_a_dodge(),),
        should=(asks_a_question(),),
        confidence=0.6,
    ),
)

AGENT_CASES: tuple[Case, ...] = (*PLANNING, *RESEARCH, *CODING, *BUSINESS, *EXECUTION)
