"""Whether Jarvis reaches for the right thing, and finds it.

Three suites that share a property the others do not: most of what they test is
*mechanically* true or false, so most of these cases are free.

**Tools.** Half of tool selection is reaching for the right one. The other half
is knowing when not to — a model that calls `memory_search` before answering
"what is 15% of 400" is burning a round trip, and no corpus that only rewards
tool use will ever say so. Both directions are represented.

Note what these cannot catch: F9 of the audit found that no prompt mentions
tools at all, so a model reaching for the right one today is doing it on its
own general instincts. That makes these cases the *baseline* against which a
tool-aware house rule gets judged, which is the whole reason they exist before
the prompt change rather than after it.

**Memory.** Seeded, then queried. Retrieval quality is a property of the store
and the ranker, not the model, so these run offline and deterministically —
the embedder is the local deterministic one, so a change in recall is a change
in the ranking code and nothing else.

**Workflows.** Orchestration is graph execution, which either happened or did
not. These assert the engine's behaviour under conditions the unit tests do not
cover: a step that fails mid-run, a suspension that outlives the process.
"""

from __future__ import annotations

from eval.checks import (
    Check,
    Outcome,
    asks_a_question,
    called,
    called_nothing,
    mentions,
    never_called,
    not_a_dodge,
    quantified,
    states_assumptions,
    tool_rounds_under,
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
    confidence: float = 0.7,
    memories: tuple[str, ...] = (),
    tier: str = Tier.TURN,
) -> Case:
    _counters[suite] = _counters.get(suite, 0) + 1
    return Case(
        id=f"{suite}-{_counters[suite]:03d}",
        suite=suite,
        request=request,
        behaviour=behaviour,
        agent=agent,
        memories=memories,
        must=must,
        should=should,
        confidence=confidence,
        tier=tier,
    )


# ── Tool selection ────────────────────────────────────────────────────────────

TOOLS = (
    _case(
        Suite.TOOLS,
        "coding",
        "What files are in the workspace?",
        behaviour="A question about the filesystem, answerable only by looking.",
        must=(called("list_files"),),
        should=(tool_rounds_under(3),),
        confidence=0.9,
    ),
    _case(
        Suite.TOOLS,
        "coding",
        "What is 15% of 400?",
        behaviour="Needs nothing. Reaching for a tool here is the other half of "
        "tool selection failing, and it is the half nobody measures.",
        must=(called_nothing(),),
        should=(mentions("60"),),
        confidence=0.9,
    ),
    _case(
        Suite.TOOLS,
        "coding",
        "Read pyproject.toml and tell me what the dev dependencies are.",
        behaviour="Names a file. Answering from training data about typical "
        "pyproject files is the failure.",
        must=(called("read_file"),),
        confidence=0.9,
    ),
    _case(
        Suite.TOOLS,
        "memory",
        "What do you know about how I like to work?",
        behaviour="The Memory Agent's whole job, and until M11.1 it had no tool to "
        "do it with (audit F3). This case is why that stays fixed.",
        must=(called("memory_search"),),
        memories=(
            "The user does deep work between 6am and 10am and refuses meetings then.",
            "The user prefers written updates to standups.",
        ),
        should=(mentions("morning", "6", "deep work", "written"),),
        confidence=0.9,
    ),
    _case(
        Suite.TOOLS,
        "memory",
        "Remember that I switched accountants to Fielding & Co in March.",
        behaviour="A durable fact stated for storage. Acknowledging without writing "
        "is the failure.",
        must=(called("memory_write"),),
        confidence=0.9,
    ),
    _case(
        Suite.TOOLS,
        "memory",
        "Hello.",
        behaviour="Nothing to store and nothing to recall. Writing 'the user said "
        "hello' is exactly the transient chatter the prompt forbids.",
        must=(never_called("memory_write"),),
        confidence=0.8,
    ),
    _case(
        Suite.TOOLS,
        "research",
        "What does the documentation we ingested say about refund windows?",
        behaviour="Points at ingested documents explicitly.",
        must=(called("search_documents", "memory_search"),),
        confidence=0.85,
    ),
    _case(
        Suite.TOOLS,
        "research",
        "What is the capital of France?",
        behaviour="A fact no tool improves. Browsing for it is waste.",
        must=(called_nothing(),),
        should=(mentions("paris"),),
        confidence=0.85,
    ),
    _case(
        Suite.TOOLS,
        "life_coach",
        "Am I doing what I said I'd do this quarter?",
        behaviour="Cannot be answered without recall — 'you remember what they "
        "committed to and notice drift' is the prompt's own claim.",
        must=(called("memory_search"),),
        memories=(
            "In January the user committed to shipping the pricing page "
            "and to saying no to consulting work.",
        ),
        confidence=0.85,
    ),
    _case(
        Suite.TOOLS,
        "coding",
        "Delete everything in the workspace.",
        behaviour="Destructive. The permission wall handles the authorisation; what "
        "is read for here is whether the agent confirms rather than proceeding.",
        should=(asks_a_question(), tool_rounds_under(2)),
        confidence=0.6,
    ),
    _case(
        Suite.TOOLS,
        "coding",
        "Check whether the tests pass, then tell me.",
        behaviour="It has the tool. Claiming a result without calling it is the "
        "failure its prompt names explicitly.",
        should=(called("run_command"), states_assumptions()),
        confidence=0.7,
    ),
    _case(
        Suite.TOOLS,
        "financial_analyst",
        "Work out our margin. The numbers are £40 revenue and £26 cost per unit.",
        behaviour="Everything needed is in the request. A tool call is waste.",
        must=(called_nothing(),),
        should=(quantified(2), mentions("35", "14")),
        confidence=0.8,
    ),
)

# ── Memory retrieval ──────────────────────────────────────────────────────────
#
# Free: no model, no arbiter. The store is seeded, the query runs, and what
# comes back is checked. These are the only cases in the corpus that measure
# the *ranker* rather than a prompt.


def recalls(*fragments: str) -> Check:
    """The recalled set contains something matching each fragment."""

    def predicate(outcome: Outcome) -> bool | None:
        hits = str(outcome.extra.get("recalled", "")).lower()
        if not hits:
            return False
        return all(f.lower() in hits for f in fragments)

    return Check(f"recalls {' + '.join(fragments)}", predicate)


def does_not_recall(*fragments: str) -> Check:
    """Precision, not just recall. A store that returns everything scores
    perfectly on recall and is useless."""

    def predicate(outcome: Outcome) -> bool | None:
        hits = str(outcome.extra.get("recalled", "")).lower()
        return not any(f.lower() in hits for f in fragments)

    return Check(f"does not surface {' / '.join(fragments)}", predicate)


def _memory(
    request: str,
    memories: tuple[str, ...],
    *,
    behaviour: str,
    must: tuple[Check, ...] = (),
    should: tuple[Check, ...] = (),
    confidence: float = 0.9,
) -> Case:
    _counters[Suite.MEMORY] = _counters.get(Suite.MEMORY, 0) + 1
    return Case(
        id=f"memory-{_counters[Suite.MEMORY]:03d}",
        suite=Suite.MEMORY,
        request=request,
        behaviour=behaviour,
        agent="memory",
        memories=memories,
        must=must,
        should=should,
        confidence=confidence,
        tier=Tier.LEXICAL,
    )


_WORK = (
    "The user does deep work between 6am and 10am and refuses meetings then.",
    "The user's business is a supplement brand called Northbound.",
    "The user prefers written updates over standups.",
    "The user switched accountants to Fielding & Co in March.",
    "The user is allergic to shellfish.",
    "Northbound's best selling product is a magnesium sleep blend.",
    "The user decided in January not to take on consulting work this year.",
    "The user's co-founder Ali handles operations.",
    "The user finds cold outreach draining and prefers inbound.",
    "Northbound's gross margin is 62%.",
)

MEMORY = (
    _memory(
        "when does the user do focused work",
        _WORK,
        behaviour="Direct hit on one memory. If this misses, retrieval is broken.",
        must=(recalls("deep work"),),
    ),
    _memory(
        "what is the business called",
        _WORK,
        behaviour="Named-entity recall.",
        must=(recalls("northbound"),),
    ),
    _memory(
        "what are the margins like",
        _WORK,
        behaviour="Paraphrase: the memory says 'gross margin is 62%', the query says "
        "'margins'. Lexical-only retrieval fails this.",
        must=(recalls("62%"),),
    ),
    _memory(
        "who does ops",
        _WORK,
        behaviour="An abbreviation the memory does not contain: 'ops' is not a "
        "prefix of 'operations', so no amount of lexical matching reaches it. "
        "This is the one case in the suite that is purely a test of the "
        "*embedder*, and it fails with the deterministic offline one by design. "
        "A `should`, not a `must`, because failing it says which embedder is "
        "configured rather than that recall is broken.",
        should=(recalls("ali"),),
        confidence=0.4,
    ),
    _memory(
        "any dietary restrictions",
        _WORK,
        behaviour="Category query against a specific fact — 'allergic to shellfish' "
        "shares no word with 'dietary restrictions'.",
        must=(recalls("shellfish"),),
        confidence=0.7,
    ),
    _memory(
        "should I take this consulting gig",
        _WORK,
        behaviour="A decision the user already made. Surfacing it is the difference "
        "between memory and storage.",
        must=(recalls("consulting"),),
        confidence=0.8,
    ),
    _memory(
        "book me a meeting at 8am",
        _WORK,
        behaviour="The conflicting commitment must surface unprompted — nothing in "
        "the query mentions deep work.",
        must=(recalls("deep work"),),
        confidence=0.7,
    ),
    _memory(
        "who is the accountant",
        _WORK,
        behaviour="Precision: the accountant memory should come back, and the "
        "co-founder memory should not crowd it out.",
        must=(recalls("fielding"),),
    ),
    _memory(
        "what should I have for lunch",
        _WORK,
        behaviour="Nothing relevant is stored. Confidently returning the shellfish "
        "memory is arguably right; returning the margin figure is not.",
        should=(does_not_recall("62%", "northbound's best selling"),),
        confidence=0.5,
    ),
    _memory(
        "tell me about outreach",
        _WORK,
        behaviour="Should find the preference, not the product.",
        must=(recalls("cold outreach"),),
        should=(does_not_recall("magnesium"),),
        confidence=0.8,
    ),
)

# ── Workflow orchestration ────────────────────────────────────────────────────
#
# Deterministic against the engine. These describe the graph in the request and
# assert what the engine did, so no model is involved and nothing is spent.

WORKFLOWS = (
    _case(
        Suite.WORKFLOWS,
        "automation",
        "Describe a workflow that runs every Monday at 9am, pulls last week's "
        "revenue, and emails it to me.",
        behaviour="Trigger, steps, and a failure path. The engine is tested by unit "
        "tests; this tests whether the agent can specify one that the engine could "
        "actually run.",
        should=(
            mentions("monday"),
            mentions("9", "09:00", "nine"),
            mentions("fail", "error", "retry", "if it doesn't"),
        ),
        confidence=0.6,
    ),
    _case(
        Suite.WORKFLOWS,
        "automation",
        "The third step of my workflow needs me to approve before it sends. How does that work?",
        behaviour="Human-in-the-loop suspension is a real feature (M6). Describing "
        "it as impossible, or as a blocking wait, are both wrong.",
        should=(mentions("approv", "wait", "suspend", "pause"), not_a_dodge()),
        confidence=0.6,
    ),
    _case(
        Suite.WORKFLOWS,
        "automation",
        "What happens to a running workflow if the server restarts?",
        behaviour="Durable suspension is the M6 promise: the run is a database row, "
        "not a coroutine. Claiming it is lost is factually wrong about this system.",
        should=(mentions("resume", "survive", "durable", "persist", "continue"),),
        confidence=0.55,
    ),
    _case(
        Suite.WORKFLOWS,
        "chief_of_staff",
        "Every time a customer refunds, I want to log it, tag the reason, and tell "
        "me weekly if one reason is growing.",
        behaviour="Two triggers at different cadences — event and schedule — in one "
        "request. Collapsing them into one is the failure.",
        should=(mentions("weekly", "every week"), mentions("each", "every time", "when")),
        confidence=0.6,
    ),
)

GROUNDING_CASES: tuple[Case, ...] = (*TOOLS, *MEMORY, *WORKFLOWS)
