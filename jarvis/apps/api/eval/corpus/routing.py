"""Routing cases: who should be asked.

The largest suite and the only free one — every case here is scored against
the registry and the arbiter, with no agent turn, so the whole thing runs on
every commit and only the arbiter costs anything.

Two ideas from the original corpus survive and are worth restating, because
everything below depends on them:

**`accept` is a set of defensible answers, not the one right one.** Several
requests genuinely span two specialists. A corpus that demands one exact id
measures conformity to the author's guesses.

**`avoid` is the sharper instrument.** These are the agents that would be
actively wrong, and a hit there is a real failure rather than a matter of
taste. It is the number the report leads with.

Sections, in the order a reader should care about them:

1. **Bread and butter** — one obvious request per agent. If these miss,
   something structural is broken, which is exactly how the phantom-tool and
   scoring defects in M11.1 were found.
2. **Spanning** — two or more agents are genuinely reasonable.
3. **Homonyms** — the surface word belongs to one agent and the meaning to
   another. The failure mode that forced the ambiguity threshold up.
4. **Intent under a disguise** — the request names an artefact but wants a
   decision, or vice versa.
5. **Vague** — nothing should claim these confidently.
6. **Escalation discipline** — cases asserting *whether* stage one decided,
   not only what it decided. Without these the router can regress into an
   expensive one-stage router without any number moving (F1).
"""

from __future__ import annotations

from eval.checks import Check, decides_alone, escalates
from eval.scoring import Case, Suite, Tier

_n = 0


def _case(
    request: str,
    accept: str,
    avoid: str = "",
    *,
    behaviour: str = "",
    confidence: float = 1.0,
    checks: tuple[Check, ...] = (),
) -> Case:
    global _n
    _n += 1
    return Case(
        id=f"route-{_n:03d}",
        suite=Suite.ROUTING,
        request=request,
        behaviour=behaviour,
        accept=frozenset(accept.split()),
        avoid=frozenset(avoid.split()) if avoid else frozenset(),
        should=checks,
        confidence=confidence,
        tier=Tier.ROUTED,
    )


# ── 1. Bread and butter: one plain request per agent ──────────────────────────

BREAD_AND_BUTTER = (
    _case("what should I focus on this week", "chief_of_staff planner life_coach", "coding legal"),
    _case("break the launch down into steps I can actually do", "planner chief_of_staff", "coding"),
    _case("research the oat milk market in the UK", "research data_analyst", "coding travel"),
    _case("fix the failing test in the auth module", "coding architect", "life_coach health"),
    _case("how should I structure the service boundaries", "architect coding", "designer travel"),
    _case("write a PRD for the referral feature", "product_manager", "coding travel"),
    _case("plan our launch campaign for the new line", "marketing chief_of_staff", "coding legal"),
    _case("find leads for my supplement brand", "sales research marketing", "coding travel"),
    _case("write the landing page headline", "copywriter marketing", "coding"),
    _case("compare our gross margin to last quarter", "financial_analyst data_analyst", "coding"),
    _case("review this contract clause", "legal", "marketing copywriter"),
    _case("book a flight to Lisbon in March", "travel", "coding legal"),
    _case("which laptop should I buy for video editing", "shopping research", "coding legal"),
    _case("I keep procrastinating on the hard tasks", "life_coach", "coding legal"),
    _case("build me a training plan for a half marathon", "health planner", "coding legal"),
    _case("teach me how transformers work", "learning research", "coding travel"),
    _case("automate the weekly invoice reminder", "automation coding", "travel health"),
    _case("what does the churn data actually say", "data_analyst research", "travel"),
    _case("give me a visual direction for the rebrand", "creative_director designer", "coding"),
    _case("design the onboarding screens", "designer creative_director product_manager", "coding"),
    _case("write this week's LinkedIn posts", "social_media copywriter", "coding legal"),
    _case("a customer is angry about a late refund", "support email", "coding travel"),
    _case("clear my inbox and tell me what needs me", "email chief_of_staff", "coding"),
    _case("move my Thursday meetings to Friday", "calendar", "coding legal"),
    _case("turn these meeting notes into action items", "meeting chief_of_staff", "coding travel"),
    _case("remember that I prefer morning meetings", "memory calendar", "meeting research"),
    _case("is it safe to give this script my API key", "security", "shopping travel"),
    _case("what does this screenshot of the error say", "vision coding", "travel shopping"),
    _case("read that back to me out loud", "voice", "coding legal"),
    _case("should we hire a second engineer or a marketer", "ceo chief_of_staff", "coding travel"),
)

# ── 2. Genuinely spanning: either lead is fine, the avoid is the point ────────

SPANNING = (
    _case(
        "our checkout conversion dropped 12% last week",
        "data_analyst product_manager marketing ceo coding",
        "travel health life_coach",
        behaviour="A diagnosis, not a campaign brief.",
    ),
    _case(
        "should we raise prices or cut CAC",
        "ceo financial_analyst marketing product_manager",
        "coding travel shopping",
        behaviour="A strategy question wearing a marketing costume.",
    ),
    _case(
        "the deploy broke and customers are seeing 500s",
        "coding architect security support",
        "marketing copywriter travel",
        behaviour="Incident: engineering leads, support follows.",
    ),
    _case(
        "write a brief for the new supplement line",
        "product_manager marketing copywriter creative_director",
        "coding legal",
    ),
    _case(
        "prepare me for the investor call on Thursday",
        "ceo chief_of_staff financial_analyst meeting planner",
        "coding shopping",
    ),
    _case(
        "our biggest client has gone quiet for three weeks",
        "sales chief_of_staff support ceo",
        "coding health travel",
    ),
    _case(
        "we need to decide between Shopify and a custom build",
        "architect ceo product_manager financial_analyst coding",
        "travel health",
    ),
    _case(
        "the team keeps missing sprint commitments",
        "product_manager chief_of_staff planner ceo coding",
        "travel shopping legal",
    ),
    _case(
        "how much runway do we have if we hire two people",
        "financial_analyst ceo planner",
        "coding travel shopping",
    ),
    _case(
        "put together everything we know about our top competitor",
        "research ceo marketing data_analyst",
        "travel health legal",
    ),
    _case(
        "our onboarding email sequence is not converting",
        "marketing copywriter email data_analyst product_manager",
        "coding travel",
    ),
    _case(
        "I want to launch a paid community next quarter",
        "ceo product_manager marketing planner chief_of_staff",
        "coding travel",
    ),
    _case(
        "the supplier raised prices 18% and I have to respond",
        "financial_analyst ceo sales legal chief_of_staff",
        "coding health",
    ),
    _case(
        "summarise this 40-page PDF",
        "research learning chief_of_staff",
        "shopping travel",
    ),
    _case(
        "what should I say to the investor who passed",
        "ceo copywriter email chief_of_staff sales",
        "coding health",
    ),
)

# ── 3. Homonyms: the word says one agent, the meaning says another ───────────

HOMONYMS = (
    _case(
        "our security deposit on the office is due",
        "financial_analyst legal calendar planner chief_of_staff",
        "security",
        behaviour="'security' is the wrong sense of the word.",
    ),
    _case(
        "I need to kill the process that's eating my week",
        "life_coach chief_of_staff planner coding",
        "security",
        behaviour="'kill process' is a figure of speech here.",
    ),
    _case(
        "design a schema for the orders table",
        "architect coding data_analyst",
        "designer creative_director",
        behaviour="'design' is not visual design.",
    ),
    _case(
        "the copy on this button doesn't convert",
        "copywriter marketing designer product_manager",
        "coding",
        behaviour="'button' is not an engineering request.",
    ),
    _case(
        "my sleep debt is out of control",
        "health life_coach",
        "financial_analyst",
        behaviour="'debt' is not financial here.",
    ),
    _case(
        "we need better coverage in the north east",
        "sales marketing ceo research",
        "coding",
        behaviour="'coverage' is territory, not test coverage.",
    ),
    _case(
        "the pipeline is completely blocked",
        "sales ceo chief_of_staff coding automation",
        "health travel",
        behaviour="Genuinely ambiguous between sales and CI — it should escalate.",
        confidence=0.8,
    ),
    _case(
        "can you scale the logo down a bit",
        "creative_director designer",
        "architect coding",
        behaviour="'scale' is not an infrastructure question.",
    ),
    _case(
        "I want to refactor how I spend my mornings",
        "life_coach planner chief_of_staff",
        "coding",
        behaviour="'refactor' borrowed for a personal habit.",
    ),
    _case(
        "our brand of coffee arrives Tuesday",
        "shopping chief_of_staff calendar",
        "marketing creative_director",
        behaviour="'brand' as a product, not as positioning.",
        confidence=0.7,
    ),
    _case(
        "the terms of the gym membership look off",
        "legal financial_analyst",
        "health",
        behaviour="A contract question that mentions a gym.",
    ),
    _case(
        "write a test for whether people click this",
        "marketing copywriter data_analyst product_manager",
        "coding",
        behaviour="An A/B test, not a unit test.",
        confidence=0.8,
    ),
    _case(
        "audit what my subscriptions are costing me",
        "financial_analyst chief_of_staff data_analyst",
        "security",
        behaviour="'audit' as review, not as security audit.",
    ),
    _case(
        "my energy crashes every afternoon",
        "health life_coach",
        "financial_analyst data_analyst",
        behaviour="'energy' as the human kind.",
    ),
    _case(
        "the deal memo needs tightening before Friday",
        "legal copywriter ceo financial_analyst",
        "sales",
        behaviour="Writing a document, not working a deal.",
        confidence=0.7,
    ),
)

# ── 4. Intent under a disguise ────────────────────────────────────────────────

DISGUISED = (
    _case(
        "just give me a spreadsheet of our costs",
        "financial_analyst data_analyst",
        "coding shopping",
        behaviour="Names an artefact, wants the analysis.",
    ),
    _case(
        "can you look at my website",
        "marketing designer research product_manager copywriter",
        "coding legal",
        behaviour="Open enough that it should not decide confidently.",
        confidence=0.7,
    ),
    _case(
        "I have three hours before the meeting, what's the highest leverage thing",
        "chief_of_staff planner life_coach",
        "coding shopping",
    ),
    _case(
        "everyone says we need AI, do we",
        "ceo product_manager architect research",
        "coding travel",
        behaviour="A strategy question, not an engineering one.",
    ),
    _case(
        "tell me why last month was bad",
        "data_analyst financial_analyst ceo chief_of_staff",
        "life_coach health",
        behaviour="Business post-mortem, not an emotional one — but close enough to escalate.",
        confidence=0.7,
    ),
    _case(
        "make this sound less like a robot wrote it",
        "copywriter",
        "coding architect",
    ),
    _case(
        "what am I not thinking about",
        "chief_of_staff ceo planner life_coach",
        "coding travel shopping",
        confidence=0.7,
    ),
    _case(
        "set it up so I never have to do this again",
        "automation chief_of_staff planner",
        "shopping travel",
    ),
    _case(
        "I said I'd ship this by Friday and I won't",
        "life_coach chief_of_staff planner product_manager",
        "coding legal",
    ),
    _case(
        "who actually owns this decision",
        "chief_of_staff planner ceo product_manager",
        "coding shopping travel",
    ),
)

# ── 5. Vague: nothing should claim these ──────────────────────────────────────

VAGUE = (
    _case("handle it", "chief_of_staff planner ceo", "", behaviour="Should be low confidence."),
    _case("what should I do today", "planner chief_of_staff life_coach", ""),
    _case("this isn't working", "chief_of_staff support coding life_coach", ""),
    _case("help", "chief_of_staff", "", behaviour="Nothing to go on at all."),
    _case("thoughts?", "chief_of_staff ceo", ""),
    _case("go on then", "chief_of_staff", ""),
    _case("same as last time", "chief_of_staff memory", "", confidence=0.6),
    _case("i'm stuck", "life_coach chief_of_staff coding", ""),
)

# ── 6. Escalation discipline ──────────────────────────────────────────────────
#
# These assert *how* the router decided, not only what it decided. Without
# them, F1 could recur invisibly: the router regressing into a one-stage design
# with an expensive first stage moves no accuracy number at all.

ESCALATION = (
    _case(
        "what's on my calendar tomorrow",
        "calendar planner",
        "coding",
        behaviour="One word, uncontested. Stage one should decide alone — this is "
        "what the two-stage design is for.",
        checks=(decides_alone(),),
    ),
    _case(
        "book a flight to Lisbon in March",
        "travel",
        "coding legal",
        checks=(decides_alone(),),
    ),
    _case(
        "review this contract clause",
        "legal",
        "marketing copywriter",
        checks=(decides_alone(),),
    ),
    _case(
        "remember that I like aisle seats",
        "memory travel",
        "coding",
        checks=(decides_alone(),),
    ),
    _case(
        "should we raise prices this quarter",
        "financial_analyst ceo shopping marketing product_manager",
        "coding travel",
        behaviour="'price' is claimed by two agents, so the evidence is contested "
        "and the arbiter should be asked.",
        checks=(escalates(),),
    ),
    _case(
        "write me a post about the launch",
        "copywriter social_media marketing",
        "coding legal",
        behaviour="'post' is contested between Copywriter and Social Media.",
        checks=(escalates(),),
    ),
    _case(
        "what's our strategy here",
        "ceo planner chief_of_staff",
        "coding travel",
        behaviour="'strategy' is contested between the CEO and the Planner.",
        checks=(escalates(),),
    ),
)

ROUTING_CASES: tuple[Case, ...] = (
    *BREAD_AND_BUTTER,
    *SPANNING,
    *HOMONYMS,
    *DISGUISED,
    *VAGUE,
    *ESCALATION,
)
