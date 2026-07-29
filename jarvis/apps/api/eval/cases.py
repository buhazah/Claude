"""The evaluation corpus.

This file is the substance of the harness. Everything else is plumbing.

Each routing case names the agents that would be a *defensible* answer, not
the single correct one — several requests genuinely span two specialists, and
a corpus that demands one exact id measures conformity to my guesses rather
than quality. Where a case really does have one right answer, the set has one
member and that is a deliberate statement.

The `avoid` field is the sharper instrument: these are the agents that would be
actively wrong, and a hit there is a real routing failure rather than a matter
of taste.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RoutingCase:
    request: str
    accept: frozenset[str]
    avoid: frozenset[str] = field(default_factory=frozenset)
    note: str = ""


def _case(request: str, accept: str, avoid: str = "", note: str = "") -> RoutingCase:
    return RoutingCase(
        request=request,
        accept=frozenset(accept.split()),
        avoid=frozenset(avoid.split()) if avoid else frozenset(),
        note=note,
    )


ROUTING_CASES: tuple[RoutingCase, ...] = (
    # ── Unambiguous. If these miss, stage-one scoring is broken. ──────────────
    _case("fix the failing test in the auth module", "coding architect", "life_coach health"),
    _case("what's on my calendar tomorrow", "calendar planner", "coding"),
    _case("draft a reply to this customer complaint", "support email copywriter", "coding"),
    _case("compare our gross margin to last quarter", "financial_analyst data_analyst", "coding"),
    _case("find three suppliers for glass bottles", "research shopping", "coding"),
    _case("write the landing page headline", "copywriter marketing", "coding"),
    _case("review this contract clause", "legal", "marketing copywriter"),
    _case("book a flight to Lisbon in March", "travel", "coding legal"),
    _case("I keep procrastinating on the hard tasks", "life_coach", "coding legal"),
    _case("summarise this 40-page PDF", "research learning", "shopping travel"),
    # ── Genuinely spanning. Either lead is fine; the point is the *avoid*. ────
    _case(
        "our checkout conversion dropped 12% last week",
        "data_analyst product_manager marketing ceo",
        "travel health life_coach",
        "diagnosis, not a campaign brief",
    ),
    _case(
        "should we raise prices or cut CAC",
        "ceo financial_analyst marketing product_manager",
        "coding travel",
        "a strategy question wearing a marketing costume",
    ),
    _case(
        "the deploy broke and customers are seeing 500s",
        "coding architect security support",
        "marketing copywriter travel",
        "incident: engineering leads, support follows",
    ),
    _case(
        "write a brief for the new supplement line",
        "product_manager marketing copywriter",
        "coding legal",
    ),
    _case(
        "prepare me for the investor call on Thursday",
        "ceo chief_of_staff financial_analyst meeting planner",
        "coding shopping",
    ),
    # ── Traps. Surface words point one way, intent points another. ────────────
    _case(
        "I need to kill the process that's eating my week",
        "life_coach chief_of_staff planner coding",
        "security",
        "'kill process' is a figure of speech here",
    ),
    _case(
        "our security deposit on the office is due",
        "financial_analyst legal calendar planner",
        "security",
        "'security' is the wrong sense of the word",
    ),
    _case(
        "design a schema for the orders table",
        "architect coding data_analyst",
        "designer creative_director",
        "'design' is not visual design",
    ),
    _case(
        "the copy on this button doesn't convert",
        "copywriter marketing designer product_manager",
        "coding",
        "'button' is not an engineering request",
    ),
    _case(
        "remember that I prefer morning meetings",
        "memory calendar",
        "meeting research",
        "a memory write, not a scheduling action",
    ),
    # ── Vague. Nothing should confidently claim these. ────────────────────────
    _case("handle it", "chief_of_staff planner ceo", "", "should be low confidence"),
    _case("what should I do today", "planner chief_of_staff life_coach", ""),
    _case("this isn't working", "chief_of_staff support coding", "", "should be low confidence"),
)


@dataclass(frozen=True, slots=True)
class AgentProbe:
    """One turn against one agent, to read what its prompt actually produces."""

    agent_id: str
    request: str
    looking_for: str


# Deliberately few: reading ten transcripts carefully beats skimming fifty.
AGENT_PROBES: tuple[AgentProbe, ...] = (
    AgentProbe(
        "research",
        "What is the current state of solid-state battery commercialisation?",
        "Does it separate established from contested, and admit what it cannot source?",
    ),
    AgentProbe(
        "coding",
        "Our FastAPI endpoint returns 200 with an empty body maybe 1% of the "
        "time. Where would you look?",
        "Does it ask for the code or invent a diagnosis? Inventing is the failure.",
    ),
    AgentProbe(
        "ceo",
        "Revenue is flat for the third month. Two product lines, one profitable.",
        "Does it lead with a decision and its cost, or produce a consultancy essay?",
    ),
    AgentProbe(
        "financial_analyst",
        "Should I take a £40k loan at 11% to buy stock for Q4?",
        "Does it quantify, and say plainly which numbers it does not have?",
    ),
    AgentProbe(
        "copywriter",
        "Headline for a magnesium supplement aimed at people who sleep badly.",
        "Three options with a rationale, or one option and a paragraph of praise for itself?",
    ),
    AgentProbe(
        "chief_of_staff",
        "Handle it: the Q3 board pack, the hiring plan, and the office lease all land next week.",
        "Does it sequence and delegate, or restate the problem back?",
    ),
    AgentProbe(
        "life_coach",
        "I am working twelve hour days and it is not helping.",
        "Is it useful, or does it perform empathy? Both failure modes matter here.",
    ),
    AgentProbe(
        "legal",
        "Can I use a customer's logo on my website without asking?",
        "Does it hedge into uselessness, or give a usable answer with the caveat stated once?",
    ),
)


@dataclass(frozen=True, slots=True)
class ModeProbe:
    """The same request in every mode. If the answers do not differ, the
    briefings are decoration."""

    request: str
    why: str


MODE_PROBES: tuple[ModeProbe, ...] = (
    ModeProbe(
        "We are losing customers after the first month. What now?",
        "Business should decide and cost it; Research should want sources; "
        "Coding should reach for instrumentation.",
    ),
    ModeProbe(
        "Tell me about our pricing.",
        "A deliberately open request — the mode should shape what 'about' means.",
    ),
)


DOCUMENT_PROBES: tuple[tuple[str, str], ...] = (
    (
        "A one-page brief on whether to move our supplement line to subscription pricing",
        "brief",
    ),
    (
        "A short report on what changed in EU cosmetics labelling rules and what we must do",
        "report",
    ),
)

TOOL_PROBE = (
    "List the files in the workspace, then tell me what is there. "
    "If the directory is empty, say so plainly rather than guessing."
)
