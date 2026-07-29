"""The long tail: how people actually type.

The routing suite proper is organised by what each case is *testing*. This file
is organised by nothing — it is a wide, flat sample of ordinary requests across
every domain Jarvis claims, written the way someone types at 8am rather than
the way a corpus author writes when they are thinking about routing.

It exists because a curated corpus drifts towards the cases its author found
interesting, and the interesting cases are the hard ones. A router can be
excellent at the twenty traps in `routing.py` and mediocre at "where's my
parcel" — and only volume catches that.

Compact on purpose: request, defensible agents, actively-wrong agents. Anything
needing a paragraph of justification belongs in `routing.py` instead.
"""

from __future__ import annotations

from eval.scoring import Case, Suite, Tier

# (request, accept, avoid)
_TABLE: tuple[tuple[str, str, str], ...] = (
    # ── Personal admin ────────────────────────────────────────────────────────
    ("where's my parcel", "shopping support chief_of_staff", "coding legal"),
    ("cancel my gym membership", "chief_of_staff legal email", "coding research"),
    ("renew the car insurance before it lapses", "chief_of_staff calendar shopping", "coding"),
    ("what did I spend on subscriptions last month", "financial_analyst data_analyst", "coding"),
    ("I need a plumber this week", "chief_of_staff shopping research", "coding legal"),
    ("remind me to call my mother on Sunday", "calendar memory chief_of_staff", "coding"),
    ("sort out the stuff I keep putting off", "chief_of_staff life_coach planner", "coding"),
    ("what's my day look like", "calendar chief_of_staff planner", "coding legal"),
    ("I need to move £2000 before Friday", "financial_analyst chief_of_staff", "coding"),
    ("find me a decent birthday present for my dad", "shopping research", "coding legal"),
    # ── Health and habits ─────────────────────────────────────────────────────
    ("I'm exhausted all the time", "health life_coach", "coding financial_analyst"),
    ("build me a push pull legs split", "health", "coding legal"),
    ("how much protein should I be eating", "health research", "coding legal"),
    ("I've stopped going to the gym again", "life_coach health", "coding legal"),
    ("my back hurts after deadlifts", "health", "coding legal"),
    ("help me actually sleep before midnight", "health life_coach", "coding"),
    ("review how this week went", "life_coach chief_of_staff planner", "coding"),
    ("I want to read more and scroll less", "life_coach learning planner", "coding"),
    ("what habits should I drop", "life_coach chief_of_staff", "coding shopping"),
    ("I keep saying yes to things I don't want", "life_coach chief_of_staff", "coding legal"),
    # ── Coding and engineering ────────────────────────────────────────────────
    ("why is this returning undefined", "coding", "life_coach legal"),
    ("write a migration to add a nullable column", "coding architect", "legal travel"),
    ("our tests take 11 minutes, speed them up", "coding architect automation", "travel"),
    ("set up CI for this repo", "coding automation architect", "travel health"),
    ("what's the difference between a mutex and a semaphore", "learning coding", "travel"),
    ("review my pull request", "coding architect", "legal marketing"),
    ("this SQL query is slow", "coding data_analyst architect", "travel legal"),
    ("should we use websockets or polling", "architect coding", "marketing travel"),
    ("explain what this regex does", "coding learning", "legal travel"),
    ("we need error tracking, what should I use", "coding architect research", "travel"),
    ("the build fails only on CI", "coding automation", "marketing travel"),
    ("document this module", "coding architect", "copywriter legal"),
    # ── Money ─────────────────────────────────────────────────────────────────
    ("are we profitable yet", "financial_analyst ceo data_analyst", "coding travel"),
    ("build me a cash flow forecast for six months", "financial_analyst", "coding travel"),
    ("what should I charge for this", "financial_analyst ceo marketing product_manager", "coding"),
    ("chase the unpaid invoices", "financial_analyst sales email chief_of_staff", "coding"),
    ("is this expense worth it", "financial_analyst ceo chief_of_staff", "coding travel"),
    ("VAT is due and I don't understand the form", "financial_analyst legal", "coding"),
    ("model what happens if we lose our biggest client", "financial_analyst ceo", "coding"),
    (
        "how much did the last campaign actually make us",
        "data_analyst financial_analyst marketing",
        "coding",
    ),
    # ── Selling and marketing ─────────────────────────────────────────────────
    ("write me a cold email that doesn't sound cold", "sales copywriter", "coding legal"),
    ("who should I be selling to", "sales marketing ceo research", "coding travel"),
    ("build a follow up sequence for trial users", "marketing email sales copywriter", "coding"),
    ("our ads stopped working", "marketing data_analyst ceo", "coding travel"),
    ("write the about page", "copywriter marketing", "coding legal"),
    ("what should our tagline be", "copywriter creative_director marketing", "coding"),
    ("plan a product launch", "marketing product_manager planner chief_of_staff", "coding"),
    ("we need testimonials, how do I get them", "marketing sales support", "coding travel"),
    ("rewrite this so it's shorter", "copywriter", "coding architect"),
    ("what's our positioning against the cheap competitor", "marketing ceo research", "coding"),
    ("draft a newsletter about the new range", "copywriter marketing social_media email", "coding"),
    ("come up with names for the new product", "creative_director copywriter marketing", "coding"),
    # ── Customers and comms ───────────────────────────────────────────────────
    ("a customer says the product arrived broken", "support email", "coding legal"),
    ("write a refund policy", "legal support copywriter", "coding travel"),
    ("this reviewer left us one star", "support marketing social_media", "coding"),
    ("summarise this email thread", "email chief_of_staff meeting", "coding travel"),
    ("draft a polite no", "email copywriter chief_of_staff", "coding architect"),
    ("who haven't I replied to", "email chief_of_staff", "coding travel"),
    ("write the agenda for tomorrow's call", "meeting calendar chief_of_staff", "coding"),
    ("what did we decide in the last board meeting", "meeting memory chief_of_staff", "coding"),
    ("find a time that works for four people in three timezones", "calendar", "coding legal"),
    ("decline this meeting without being rude", "calendar email copywriter", "coding"),
    # ── Business and strategy ─────────────────────────────────────────────────
    ("should we expand to Germany", "ceo research financial_analyst", "coding health"),
    (
        "what's the biggest risk to the business right now",
        "ceo chief_of_staff financial_analyst",
        "coding",
    ),
    (
        "write a job description for an ops hire",
        "ceo product_manager copywriter chief_of_staff",
        "coding",
    ),
    ("should I fire this contractor", "ceo chief_of_staff legal", "coding health"),
    ("what would you do with £20k right now", "ceo financial_analyst marketing", "coding"),
    ("we're growing but it feels chaotic", "ceo chief_of_staff planner", "coding travel"),
    ("build me a one page strategy", "ceo planner product_manager", "coding travel"),
    ("what should we stop doing", "ceo chief_of_staff planner", "coding shopping"),
    # ── Research and learning ─────────────────────────────────────────────────
    ("what's the regulation on selling supplements in the EU", "research legal", "coding travel"),
    ("find me three case studies of brands that did this", "research marketing", "coding"),
    ("is this claim actually true", "research data_analyst", "coding travel"),
    ("give me the state of the art on RAG", "research learning", "travel shopping"),
    ("teach me enough SQL to be useful", "learning coding", "travel legal"),
    ("what should I read about pricing", "learning research", "coding travel"),
    ("explain our own architecture back to me", "architect coding learning", "travel"),
    ("what happened in the news about our industry this week", "research", "coding legal"),
    # ── Making things ─────────────────────────────────────────────────────────
    ("design a logo direction", "creative_director designer", "coding legal"),
    ("what should the settings page look like", "designer product_manager", "coding legal"),
    ("our app feels slow and ugly", "designer coding product_manager", "legal travel"),
    ("make a moodboard for the campaign", "creative_director designer marketing", "coding"),
    ("critique this landing page", "designer marketing copywriter creative_director", "coding"),
    ("what should go above the fold", "designer marketing copywriter", "coding legal"),
    # ── Travel ────────────────────────────────────────────────────────────────
    ("I need to be in Berlin Tuesday and back Thursday", "travel calendar", "coding legal"),
    ("do I need a visa for Japan", "travel research", "coding legal"),
    ("my flight was cancelled", "travel support chief_of_staff", "coding legal"),
    ("find a hotel near the conference", "travel shopping", "coding legal"),
    ("plan a week off where I actually rest", "travel life_coach planner", "coding"),
    # ── Buying ────────────────────────────────────────────────────────────────
    ("what's the best CRM for a five person team", "shopping research product_manager", "coding"),
    ("is this worth £400", "shopping financial_analyst", "coding legal"),
    ("compare these two suppliers", "research shopping financial_analyst", "coding"),
    ("find the cheapest way to ship to the US", "shopping research financial_analyst", "coding"),
    ("order more of the magnesium stock", "shopping chief_of_staff", "coding legal"),
    # ── Memory and self ───────────────────────────────────────────────────────
    ("what did I say about this last time", "memory chief_of_staff", "coding travel"),
    ("forget what I told you about the old pricing", "memory", "coding legal"),
    ("what do you know about me", "memory chief_of_staff", "coding travel"),
    ("keep in mind I hate video calls", "memory calendar", "coding legal"),
    ("what were my goals for this year", "memory life_coach planner", "coding"),
    # ── Security and operations ───────────────────────────────────────────────
    ("someone tried to log into my account", "security", "shopping travel"),
    ("rotate our API keys", "security automation coding", "marketing travel"),
    ("is this email a phishing attempt", "security email", "marketing travel"),
    ("who has access to the production database", "security architect coding", "marketing"),
    ("we got a GDPR request", "legal security support", "marketing travel"),
    # ── Voice and vision ──────────────────────────────────────────────────────
    ("just tell me quickly, no lists", "voice chief_of_staff", "coding legal"),
    ("what does this chart show", "vision data_analyst", "travel legal"),
    ("read this document and pull out the numbers", "vision research data_analyst", "travel"),
    ("what's wrong with this UI in the screenshot", "vision designer coding", "travel"),
    # ── Things that should not confidently route anywhere ─────────────────────
    ("ok", "chief_of_staff", ""),
    ("and the other thing", "chief_of_staff memory", ""),
    ("do the usual", "chief_of_staff memory automation", ""),
    ("nope, try again", "chief_of_staff", ""),
    ("that's not what I meant", "chief_of_staff", ""),
)


EVERYDAY_CASES: tuple[Case, ...] = tuple(
    Case(
        id=f"everyday-{i:03d}",
        suite=Suite.ROUTING,
        request=request,
        accept=frozenset(accept.split()),
        avoid=frozenset(avoid.split()) if avoid else frozenset(),
        # Lower than the curated cases. These were written quickly and in bulk,
        # which is their value and also their weakness: a disagreement with one
        # of them is more likely to be the corpus being wrong than the router.
        confidence=0.7,
        tier=Tier.ROUTED,
    )
    for i, (request, accept, avoid) in enumerate(_TABLE, start=1)
)
