"""The morning briefing.

Phase 11 asked for something that "feels like it was written by an experienced
executive chief of staff". That is a real specification, not a vibe, and it
decomposes into four properties a briefing either has or does not:

**It leads with the one thing.** A good chief of staff opens with "the lease
decision is the thing today", not with a list of nine categories in fixed
order. So the headline is chosen by score, and the sections are ordered by
whether they contain anything.

**It says what it does not know.** Nobody senior pretends to have read the mail
when they have not. Jarvis has no mail or calendar connector unless one is
mounted, and a briefing that invents "3 emails need you" is worse than useless
— it is *confidently* useless, and every later section inherits the doubt. So
absent sources are named, once, at the bottom.

**It does not pad.** A quiet day gets one line. The instinct to fill nine
headings whatever the state of the world is what makes generated briefings
unreadable, and it is the single easiest way to train somebody to stop opening
them.

**It is short.** An executive summary that takes ten minutes to read is a
report.

Everything above is decided by arithmetic (ADR 0014). The model's only job here
is to write the two-sentence opener, and only when one is configured — with a
deterministic fallback that is plainer but never wrong. Facts never come from
the model; it is handed the facts and asked for prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import structlog

from jarvis.chief.engine import Sweep
from jarvis.chief.models import Impact, Recommendation, Signal, Urgency
from jarvis.chief.situation import Situation
from jarvis.llm.base import CompletionRequest, Message, Role, RoutingPolicy
from jarvis.llm.router import ModelRouter
from jarvis.memory.models import MemoryKind

log = structlog.get_logger(__name__)

# The offline provider's name. Its output is never prose — see `_opener`.
ECHO_PROVIDER = "echo"

# Sources a full briefing would use that Jarvis only has via a connector. Named
# so the briefing can say what it could not see, rather than quietly omitting
# a section the reader is expecting.
CONNECTOR_SOURCES = {
    "email": "no mail connector is mounted",
    "calendar": "no calendar connector is mounted",
}

OPENER_PROMPT = (
    "You are the user's chief of staff, writing the first two sentences of "
    "their morning briefing.\n"
    "- Lead with the single most important thing and why it matters today.\n"
    "- Two sentences. Never three.\n"
    "- No greeting, no preamble, no summary of what follows.\n"
    "- Use only the facts given. Never invent a number, a name or a date.\n"
    "- If there is nothing pressing, say that plainly in one sentence."
)


@dataclass(slots=True)
class Section:
    """One heading. Absent when empty — see the no-padding rule."""

    title: str
    lines: list[str] = field(default_factory=list)
    note: str = ""

    def __bool__(self) -> bool:
        return bool(self.lines)


@dataclass(slots=True)
class Briefing:
    day: date
    opener: str = ""
    sections: list[Section] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    unavailable: dict[str, str] = field(default_factory=dict)
    quiet: bool = False
    generated_by: str = "arithmetic"

    def to_markdown(self) -> str:
        out = [f"# {self.day.strftime('%A %-d %B')}", "", self.opener, ""]
        for section in self.sections:
            out += [f"## {section.title}", ""]
            out += [f"- {line}" for line in section.lines]
            if section.note:
                out += ["", f"*{section.note}*"]
            out.append("")
        if self.unavailable:
            missing = "; ".join(f"{name} — {why}" for name, why in sorted(self.unavailable.items()))
            out += ["---", "", f"*Not covered: {missing}.*", ""]
        return "\n".join(out).rstrip() + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "opener": self.opener,
            "quiet": self.quiet,
            "generated_by": self.generated_by,
            "sections": [
                {"title": s.title, "lines": s.lines, "note": s.note} for s in self.sections
            ],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "unavailable": dict(self.unavailable),
        }


class BriefingComposer:
    """Assembles the briefing. Facts from state, prose from a model — never
    the other way round."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router

    async def compose(self, sweep: Sweep, situation: Situation) -> Briefing:
        briefing = Briefing(day=situation.now.date())
        briefing.recommendations = sweep.recommendations
        briefing.unavailable = _unavailable(situation)

        sections = [
            _priorities(sweep),
            _blocked(sweep),
            _risks(sweep),
            _projects(situation),
            _in_flight(situation),
            _learned(situation),
            _next_actions(sweep),
        ]
        briefing.sections = [section for section in sections if section]
        briefing.quiet = not sweep.recommendations and not briefing.sections

        briefing.opener, briefing.generated_by = await self._opener(briefing, sweep)
        return briefing

    async def _opener(self, briefing: Briefing, sweep: Sweep) -> tuple[str, str]:
        """Two sentences. From a model when one exists, arithmetic otherwise."""
        fallback = _plain_opener(briefing, sweep)
        if self._router is None or not sweep.recommendations:
            return fallback, "arithmetic"

        facts = "\n".join(
            f"- [{r.impact.name.lower()}/{r.urgency.name.lower()}] {r.headline} ({r.why})"
            for r in sweep.recommendations[:6]
        )
        try:
            completion = await self._router.complete(
                CompletionRequest(
                    messages=[Message(role=Role.USER, content=f"Today:\n{facts}")],
                    system=OPENER_PROMPT,
                    policy=RoutingPolicy.FAST,
                    max_output_tokens=160,
                    temperature=0.4,
                )
            )
        except Exception as exc:
            log.warning("briefing_opener_failed", error=str(exc))
            return fallback, "arithmetic"

        # The offline provider echoes the prompt back. It is short, it is
        # plausible-looking, and it passed every other guard here — so the
        # briefing opened with "[echo:52f8ee68] Today: - [major/this_week]…"
        # and reported itself as model-written. The fallback chain means this
        # happens whenever a real provider is *configured but failing*, not
        # only when none is set, which is exactly when nobody is watching.
        if completion.provider == ECHO_PROVIDER:
            return fallback, "arithmetic"

        written = " ".join(completion.text.split())
        # A model that returns nothing usable, or a page, is not better than the
        # plain sentence — and the plain sentence is never wrong.
        if not written or len(written.split()) > 70:
            return fallback, "arithmetic"
        return written, "model"


# ── Sections ──────────────────────────────────────────────────────────────────


def _priorities(sweep: Sweep) -> Section:
    """The top of the list, with why. Capped at three: a chief of staff who
    hands you nine priorities has not prioritised anything."""
    top = [r for r in sweep.recommendations if r.urgency is not Urgency.WHENEVER][:3]
    section = Section("Today")
    section.lines = [f"**{r.headline}** — {r.why}" for r in top]
    if sweep.suppressed:
        section.note = f"{sweep.suppressed} more held back"
    return section


def _blocked(sweep: Sweep) -> Section:
    """Things that are stopped. Separate from priorities because "stopped" is a
    different fact from "important" and the reader treats them differently."""
    section = Section("Blocked")
    section.lines = [f"{r.headline} — {r.why}" for r in sweep.blocking]
    return section


def _risks(sweep: Sweep) -> Section:
    """High-impact, not yet urgent. The category a briefing exists to surface,
    because by definition nothing else will."""
    section = Section("Worth watching")
    section.lines = [
        f"{r.headline} — {r.why}"
        for r in sweep.recommendations
        if r.impact >= Impact.MAJOR and r.urgency <= Urgency.SOON
    ][:3]
    return section


def _projects(situation: Situation) -> Section:
    """Movement, not inventory. Which pages changed, and which have not."""
    section = Section("Projects")
    if not situation.projects:
        return section

    recent = sorted(
        (p for p in situation.projects if p.updated),
        key=lambda p: p.updated or datetime.min,
        reverse=True,
    )
    for page in recent[:4]:
        assert page.updated is not None
        age = situation.now - page.updated
        when = "today" if age < timedelta(days=1) else f"{age.days}d ago"
        section.lines.append(f"{page.title} — {page.memories} note(s), last touched {when}")
    return section


def _in_flight(situation: Situation) -> Section:
    """What Jarvis itself did recently. The reader's own work, reflected back."""
    section = Section("Jarvis has been working on")
    recent = [
        run
        for run in situation.runs[:20]
        if getattr(run.state, "value", run.state) == "succeeded" and run.request
    ][:4]
    section.lines = [f"{_short(run.request)} → `{run.agent_id}`" for run in recent]
    return section


def _learned(situation: Situation) -> Section:
    """Decisions and findings recorded since yesterday.

    Decisions rather than conversations: a briefing that lists everything the
    user said is a transcript, and the point of memory kinds is being able to
    tell the difference.
    """
    section = Section("Recorded since yesterday")
    cutoff = situation.now - timedelta(days=1)
    worth_repeating = (MemoryKind.DECISION, MemoryKind.SUCCESS, MemoryKind.MISTAKE)
    for memory in situation.memories:
        created = memory.created_at
        if not created or memory.kind not in worth_repeating:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=situation.now.tzinfo)
        if created >= cutoff:
            section.lines.append(f"[{memory.kind.value}] {_short(memory.content)}")
    section.lines = section.lines[:5]
    return section


def _next_actions(sweep: Sweep) -> Section:
    """Requests the user can hand straight back to Jarvis.

    The difference between a briefing and a to-do list: every line here is
    something the reader can act on by pressing one button, because the
    recommendation already knows which agent should get it.
    """
    section = Section("Suggested next")
    seen: set[str] = set()
    for recommendation in sweep.recommendations:
        if not recommendation.action or recommendation.action in seen:
            continue
        seen.add(recommendation.action)
        section.lines.append(f"`{recommendation.agent}` — {recommendation.action}")
        if len(section.lines) >= 4:
            break
    return section


# ── Helpers ───────────────────────────────────────────────────────────────────


def _unavailable(situation: Situation) -> dict[str, str]:
    """Sources this briefing could not read, and why.

    Connector-gated sources are listed whether or not anybody asked, because
    the reader is expecting a calendar summary and its silent absence reads as
    "nothing on today" rather than "Jarvis cannot see your calendar".
    """
    missing = dict(CONNECTOR_SOURCES)
    for name in situation.unavailable:
        missing[name] = "could not be read"
    return missing


def _plain_opener(briefing: Briefing, sweep: Sweep) -> str:
    """The fallback, and the floor. Plainer than a model's, never wrong."""
    if briefing.quiet:
        return "Nothing needs you this morning."
    if not sweep.recommendations:
        # Sections without recommendations: there is context to read but
        # nothing to decide. Reached most often after dismissing everything,
        # which used to index an empty list and return a 500 — a briefing that
        # crashes once you have acted on it is the worst possible time to.
        return "Nothing needs a decision this morning. Some context below."
    top = sweep.recommendations[0]
    blocking = len(sweep.blocking)
    lead = f"{top.headline} is the thing today — {top.why}."
    if blocking:
        return f"{lead} {blocking} item(s) are blocked and waiting on you."
    others = len(sweep.recommendations) - 1
    if others > 0:
        return f"{lead} {others} other thing(s) are worth a look."
    return lead


def _short(text: str, limit: int = 90) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


__all__ = ["Briefing", "BriefingComposer", "Section", "Signal"]
