"""The built-in modes.

Four, because four is what a person actually switches between. Each one is a
different answer to "what is Jarvis allowed to be right now", and each is
defined by what it *removes* — a mode that adds nothing and removes nothing has
no reason to exist.

`personal` is the default and deliberately unconstrained: it is the whole
catalog with no briefing and no memory namespace. It exists so that switching
*out* of it is what narrows, rather than the other way round.
"""

from __future__ import annotations

from jarvis.llm.base import RoutingPolicy
from jarvis.modes.spec import Mode, ModeRegistry

PERSONAL = Mode(
    id="personal",
    name="Personal",
    tagline="Everything Jarvis can do, nothing held back.",
    surfaces=("chat", "memory", "knowledge", "workflows", "runs"),
    accent="default",
)

BUSINESS = Mode(
    id="business",
    name="Business",
    tagline="Operating the businesses. Money, customers, and decisions.",
    agents=(
        "ceo",
        "chief_of_staff",
        "financial_analyst",
        "marketing",
        "sales",
        "product_manager",
        "copywriter",
        "data_analyst",
        "legal",
        "social_media",
        "support",
        "email",
        "calendar",
        "meeting",
        "planner",
    ),
    briefing=(
        "You are operating inside a business. Lead with the decision and what it "
        "costs; put the reasoning after it. Quantify where numbers exist and say "
        "plainly where they do not. Never invent a figure to complete a sentence."
    ),
    policy=RoutingPolicy.BALANCED,
    # Business memory is its own namespace. What Jarvis learns about a client
    # must not surface while drafting a personal message, and the reverse
    # matters more: personal detail must not leak into client-facing work.
    memory_scope="business",
    surfaces=("chat", "documents", "workflows", "knowledge", "runs"),
    accent="amber",
)

CODING = Mode(
    id="coding",
    name="Coding",
    tagline="Shipping software. Read the code before changing it.",
    agents=("coding", "architect", "security", "data_analyst", "product_manager", "planner"),
    briefing=(
        "You are working in a real codebase. Read before you write, and match the "
        "conventions already there rather than the ones you prefer. State what you "
        "changed and what you did not verify. A test you did not run is not a test "
        "that passed."
    ),
    # Quality over cost: a cheap model that writes plausible-looking code costs
    # more in review than it saves in tokens.
    policy=RoutingPolicy.QUALITY,
    memory_scope="coding",
    surfaces=("chat", "runs", "knowledge", "tools"),
    accent="violet",
)

RESEARCH = Mode(
    id="research",
    name="Research",
    tagline="Finding out. Every claim carries a source.",
    agents=("research", "data_analyst", "learning", "financial_analyst", "legal", "vision"),
    briefing=(
        "Every non-obvious claim carries a citation to something in the knowledge "
        "base or a page you actually read. Separate what is established from what "
        "is contested and what you inferred. If the sources disagree, say so and "
        "say which you find more credible and why. An uncited claim is a guess "
        "wearing a suit.\n\n"
        "When you lack something, write it as a lack: 'I do not have X.' Never "
        "introduce a list of missing things with a phrase that reads as though "
        "you have them. Measured against a real model this mode produced 'I can "
        "see: your pricing structure...' when it meant the opposite, which is "
        "worse than saying nothing."
    ),
    policy=RoutingPolicy.QUALITY,
    memory_scope="research",
    surfaces=("chat", "knowledge", "documents", "runs"),
    accent="cyan",
)

BUILT_IN = (PERSONAL, BUSINESS, CODING, RESEARCH)


def built_in_modes() -> ModeRegistry:
    return ModeRegistry({m.id: m for m in BUILT_IN}, default_id=PERSONAL.id)
