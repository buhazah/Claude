"""The cases that are read, not scored.

Everything in `CASES` has a mechanical verdict. These do not, and pretending
otherwise would be the harness lying to the person who built it: whether an
answer *reasons well* is not a keyword question, and a check that claimed to
measure it would be believed.

So these run, their transcripts are printed in full, and a human decides.
Deliberately few — reading eight transcripts carefully beats skimming fifty.

The mode probes are a different kind of question: the same request in every
mode, side by side. If the four answers are interchangeable, the mode briefings
are decoration and should be rewritten or dropped. That is not a per-answer
judgement, which is why it cannot be a check either.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentProbe:
    """One turn against one agent, to read what its prompt actually produces."""

    agent_id: str
    request: str
    looking_for: str


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
        "Does it sequence and delegate, or restate the problem back? It cannot "
        "actually delegate yet (audit F4) — the question is whether it claims to have.",
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
