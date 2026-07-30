"""The detectors: small, deterministic, and each answerable on its own.

Every function here takes a `Situation` and returns recommendations. None of
them calls a model. That is the point — the arithmetic is auditable, works
offline, and produces the same answer twice, which is what lets a wrong
recommendation be *fixed* rather than merely disagreed with.

The hard part of a recommendation engine is not finding things to say. It is
not saying too much. A list of forty observations is a list nobody reads, and
the failure mode of every "proactive assistant" is exactly that: it notices
everything, ranks nothing, and gets muted within a week.

So each detector is written to the same three rules:

1. **Only fire on something a person can act on today.** "Your vault has 143
   notes" is a fact, not a recommendation.
2. **Cap the output.** A detector that can produce fifty rows produces its
   worst five, because the alternative is that it buries every other detector.
3. **Say what it saw.** Every recommendation carries evidence, so a wrong one
   points at the data that misled it.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta

from jarvis.chief.models import Impact, Recommendation, Signal, Urgency
from jarvis.chief.situation import Situation
from jarvis.memory.models import MemoryKind

# A project untouched this long has stopped being paused and started being
# abandoned, without anybody having decided that.
COLD_AFTER = timedelta(days=21)
VERY_COLD = timedelta(days=60)
# A goal stated and never mentioned again. Shorter than a cold project, because
# a goal with no activity behind it decays faster than a page does.
GOAL_SILENCE = timedelta(days=14)
STALLED_WORKFLOW = timedelta(hours=6)
# How far ahead a date is worth mentioning. Beyond a fortnight it is noise;
# inside three days it is urgent.
DEADLINE_HORIZON = timedelta(days=14)

# Dates Jarvis has been told about in prose. Deliberately narrow: a loose date
# parser turns every "in 2019" into a deadline, and a recommendation engine
# that cries wolf is one nobody reads.
_DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\b"
    r"|\bby\s+(?:the\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)"
    r"|\b(?:due|deadline|by)\s+(mon|tues|wednes|thurs|fri|satur|sun)day\b",
    re.IGNORECASE,
)

Detector = Callable[[Situation], list[Recommendation]]


def _id(signal: Signal, key: str) -> str:
    """Stable across sweeps, so the same thing is the same recommendation.

    Without this, dismissing something would be meaningless — every sweep would
    produce a fresh id and the thing you dismissed would come straight back
    wearing a new name.
    """
    return f"rec_{signal.value}_{abs(hash(key)) % 10**10:010d}"


# ── Something is waiting on a human ───────────────────────────────────────────


def pending_approvals(situation: Situation) -> list[Recommendation]:
    """The only signal that is certain. Something is stopped, right now."""
    out = []
    for approval in situation.approvals[:5]:
        out.append(
            Recommendation(
                id=_id(Signal.APPROVAL, approval.id),
                signal=Signal.APPROVAL,
                headline=f"Approve or refuse: {approval.tool}",
                impact=Impact.MAJOR,
                # Blocking is not a judgement here — a run is literally parked.
                urgency=Urgency.BLOCKING,
                confidence=1.0,
                evidence=[
                    f"`{approval.tool}` requested by "
                    f"{approval.agent_id or 'an agent'} and still waiting"
                ],
                action=f"Decide the pending approval for {approval.tool}",
                agent="chief_of_staff",
                refs=[approval.id],
                at=situation.now,
            )
        )
    return out


# ── Work that ended badly ─────────────────────────────────────────────────────


def failed_runs(situation: Situation) -> list[Recommendation]:
    """A failure nobody returned to.

    "Returned to" means a later run for the same agent — a crude proxy, and
    marked as such in the confidence, but the right shape: what matters is not
    that something failed, it is that nothing happened afterwards.
    """
    failed = [run for run in situation.runs if getattr(run.state, "value", run.state) == "failed"]
    if not failed:
        return []

    later: Counter[str] = Counter()
    for run in situation.runs:
        if getattr(run.state, "value", run.state) == "succeeded":
            later[run.agent_id] += 1

    out = []
    for run in failed[:5]:
        if later.get(run.agent_id):
            continue  # something worked afterwards; probably handled
        out.append(
            Recommendation(
                id=_id(Signal.FAILED_RUN, run.id),
                signal=Signal.FAILED_RUN,
                headline=f"Retry or abandon: {_short(run.request)}",
                impact=Impact.MODERATE,
                urgency=Urgency.THIS_WEEK,
                confidence=0.7,
                evidence=[
                    f"failed with: {(run.error or 'no error recorded')[:120]}",
                    f"nothing has succeeded for `{run.agent_id}` since",
                ],
                action=run.request,
                agent=run.agent_id,
                refs=[run.id],
                at=situation.now,
            )
        )
    return out


def stalled_workflows(situation: Situation) -> list[Recommendation]:
    """A workflow suspended long enough that it has probably been forgotten.

    Durable suspension is the point of M6 — a run waiting on a human is a
    database row, not a coroutine — and the cost of that design is that a
    forgotten run waits patiently forever. This is the counterweight.
    """
    out = []
    for run in situation.workflow_runs:
        state = getattr(run.state, "value", run.state)
        if state not in ("awaiting_approval", "running"):
            continue
        started = _aware(getattr(run, "created_at", None))
        if not started or situation.now - started < STALLED_WORKFLOW:
            continue
        waiting = situation.now - started
        out.append(
            Recommendation(
                id=_id(Signal.STALLED_WORKFLOW, run.id),
                signal=Signal.STALLED_WORKFLOW,
                headline=f"Unblock the '{run.workflow_name or run.workflow_id}' workflow",
                impact=Impact.MODERATE,
                urgency=Urgency.TODAY if waiting > timedelta(days=1) else Urgency.THIS_WEEK,
                confidence=0.9,
                evidence=[f"{state.replace('_', ' ')} for {_span(waiting)}"],
                action=f"Look at why the {run.workflow_name} workflow is stuck",
                agent="automation",
                refs=[run.id],
                at=situation.now,
            )
        )
    return sorted(out, key=lambda r: r.score, reverse=True)[:3]


# ── Things going quiet ────────────────────────────────────────────────────────


def cold_projects(situation: Situation) -> list[Recommendation]:
    """A project page nobody has touched.

    Needs a vault, and says nothing without one. This is the recommendation a
    system that only reads recall can never make: nobody asked about the
    project, which is precisely the problem.
    """
    out = []
    for page in situation.projects:
        if not page.updated:
            continue
        age = situation.now - page.updated
        if age < COLD_AFTER:
            continue
        very = age >= VERY_COLD
        out.append(
            Recommendation(
                id=_id(Signal.COLD_PROJECT, page.path),
                signal=Signal.COLD_PROJECT,
                headline=f"Decide what happens to {page.title}",
                impact=Impact.MAJOR if very else Impact.MODERATE,
                # Never urgent. That is the whole trap: a cold project is
                # important and never pressing, which is how it got cold.
                urgency=Urgency.SOON if very else Urgency.WHENEVER,
                confidence=0.6,
                evidence=[
                    f"nothing written to {page.path} in {_span(age)}",
                    f"{page.memories} note(s) recorded there",
                ],
                action=f"Review {page.title}: what is the state, and what is next?",
                agent="chief_of_staff",
                refs=[page.path],
                at=situation.now,
            )
        )
    return sorted(out, key=lambda r: r.score, reverse=True)[:4]


def open_goals(situation: Situation) -> list[Recommendation]:
    """A goal stated and then never mentioned again.

    The Life Coach's prompt promises to "notice drift". This is what noticing
    drift looks like when it is a property of the system rather than something
    a model is asked to do from an empty context.
    """
    goals = [m for m in situation.memories if m.kind is MemoryKind.GOAL]
    if not goals:
        return []

    # What has been said since, so a goal being actively worked on stays quiet.
    recent = " ".join(
        m.content.lower()
        for m in situation.memories
        if m.kind is not MemoryKind.GOAL
        and (created := _aware(m.created_at))
        and situation.now - created < GOAL_SILENCE
    )

    out = []
    for goal in goals:
        created = _aware(goal.created_at)
        if not created or situation.now - created < GOAL_SILENCE:
            continue
        subject = _subject(goal.content)
        if subject and subject in recent:
            continue
        out.append(
            Recommendation(
                id=_id(Signal.OPEN_GOAL, goal.id),
                signal=Signal.OPEN_GOAL,
                headline=f"Still open: {_short(goal.content)}",
                impact=Impact.MODERATE,
                urgency=Urgency.SOON,
                confidence=0.5,
                evidence=[
                    f"stated {_span(situation.now - created)} ago",
                    "nothing since mentions it",
                ],
                action=f"Where are we on: {_short(goal.content)}?",
                agent="life_coach" if goal.scope in ("life_coach", "global") else "planner",
                refs=[goal.id],
                at=situation.now,
            )
        )
    return sorted(out, key=lambda r: r.score, reverse=True)[:4]


def deadlines(situation: Situation) -> list[Recommendation]:
    """Dates Jarvis has been told about, inside the horizon.

    Only ISO dates and a couple of explicit "by <date>" forms. A loose parser
    turns every "in 2019" into a deadline, and an engine that cries wolf is one
    nobody reads.
    """
    out = []
    for memory in situation.memories:
        for match in _DATE.finditer(memory.content):
            when = _parse_date(match, situation.now)
            if when is None:
                continue
            ahead = when - situation.now
            if ahead < timedelta(0) or ahead > DEADLINE_HORIZON:
                continue
            # The date is already in the prefix; leaving it in the excerpt too
            # produces "Due 2026-08-01: the lease is due 2026-08-01".
            without_date = _DATE.sub("", memory.content).replace("  ", " ").strip(" ,.:;-")
            out.append(
                Recommendation(
                    id=_id(Signal.DEADLINE, f"{memory.id}:{match.group(0)}"),
                    signal=Signal.DEADLINE,
                    headline=f"Due {when.date().isoformat()}: {_short(without_date)}",
                    impact=Impact.MAJOR,
                    urgency=(
                        Urgency.TODAY
                        if ahead <= timedelta(days=3)
                        else Urgency.THIS_WEEK
                        if ahead <= timedelta(days=7)
                        else Urgency.SOON
                    ),
                    confidence=0.8,
                    # The scope is only worth naming when it is one — "recorded
                    # for global" is filing jargon, not evidence.
                    evidence=[
                        f"'{match.group(0).strip()}' in a note"
                        + (f" under {memory.scope}" if memory.scope != "global" else "")
                    ],
                    action=f"What is outstanding for: {_short(without_date)}?",
                    agent="planner",
                    refs=[memory.id],
                    at=when,
                )
            )
            break  # one deadline per memory; the first date is the operative one
    return sorted(out, key=lambda r: (r.score, -(r.at or situation.now).timestamp()), reverse=True)[
        :5
    ]


# ── Patterns ──────────────────────────────────────────────────────────────────


def repeated_mistakes(situation: Situation) -> list[Recommendation]:
    """The same thing going wrong more than once.

    A single mistake is an event. Three in the same scope is a process problem,
    and telling the difference is something only a system with history can do.
    """
    mistakes = [m for m in situation.memories if m.kind is MemoryKind.MISTAKE]
    by_scope: Counter[str] = Counter(m.scope for m in mistakes)
    out = []
    for scope, count in by_scope.most_common(3):
        if count < 3:
            continue
        examples = [m.content for m in mistakes if m.scope == scope][:3]
        # "in global" names a default, not a place. Same jargon leak as the
        # deadline evidence: a scope is only worth saying when it is one.
        where = f" in {scope}" if scope != "global" else ""
        out.append(
            Recommendation(
                id=_id(Signal.REPEATED_MISTAKE, scope),
                signal=Signal.REPEATED_MISTAKE,
                headline=f"Fix the cause: {count} recorded failures{where}",
                impact=Impact.MAJOR,
                urgency=Urgency.THIS_WEEK,
                confidence=0.7,
                evidence=[_short(text) for text in examples],
                action=f"What keeps going wrong{where}, and what would stop it?",
                agent="chief_of_staff",
                refs=[scope],
                at=situation.now,
            )
        )
    return out


def budget_pressure(situation: Situation) -> list[Recommendation]:
    """Spend approaching a ceiling, before it starts refusing work."""
    out = []
    for budget in situation.budget.get("budgets", []):
        hard = float(budget.get("hard_usd") or 0.0)
        spent = float(budget.get("spent_usd") or 0.0)
        if hard <= 0 or spent / hard < 0.7:
            continue
        share = spent / hard
        out.append(
            Recommendation(
                id=_id(Signal.BUDGET, str(budget.get("period"))),
                signal=Signal.BUDGET,
                headline=f"{share:.0%} of the {budget.get('period')} budget is spent",
                impact=Impact.MODERATE if share < 0.9 else Impact.MAJOR,
                urgency=Urgency.TODAY if share >= 0.9 else Urgency.THIS_WEEK,
                confidence=1.0,
                evidence=[f"${spent:.2f} of ${hard:.2f}"],
                action="Review what is costing the most and raise or reduce the ceiling",
                agent="financial_analyst",
                refs=[str(budget.get("period"))],
                at=situation.now,
            )
        )
    return out


def loose_knowledge(situation: Situation) -> list[Recommendation]:
    """Notes connected to nothing, and links that were never made.

    Deliberately the lowest-impact detector in the set, and capped hardest.
    Tidiness is real but it is never the most important thing, and a
    recommendation engine that leads with housekeeping is one that gets muted.
    """
    if not situation.orphans and not situation.unlinked:
        return []
    evidence = []
    if situation.orphans:
        evidence.append(f"{len(situation.orphans)} note(s) connected to nothing")
    if situation.unlinked:
        first = situation.unlinked[0]
        evidence.append(
            f"{len(situation.unlinked)} unlinked mention(s), e.g. {first[1]} in {first[0]}"
        )
    return [
        Recommendation(
            id=_id(Signal.LOOSE_KNOWLEDGE, "vault"),
            signal=Signal.LOOSE_KNOWLEDGE,
            headline="Reconnect knowledge that is stranded in the vault",
            impact=Impact.TRIVIAL,
            urgency=Urgency.WHENEVER,
            confidence=0.9,
            evidence=evidence,
            action="Link the orphaned notes and the unlinked mentions",
            agent="memory",
            refs=situation.orphans[:5],
            at=situation.now,
        )
    ]


DETECTORS: tuple[Detector, ...] = (
    pending_approvals,
    failed_runs,
    stalled_workflows,
    deadlines,
    cold_projects,
    open_goals,
    repeated_mistakes,
    budget_pressure,
    loose_knowledge,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def _short(text: str, limit: int = 90) -> str:
    """Trim, and unwrap wikilinks.

    A memory read out of the vault carries `[[Northbound]]`, which is correct
    in a note and is markup leaking into prose anywhere else — a briefing, a
    notification, a spoken answer. The link belongs to the file format, not to
    the sentence.
    """
    flat = " ".join(_WIKILINK.sub(lambda m: m.group(1), text).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _span(delta: timedelta) -> str:
    days = delta.days
    if days >= 14:
        return f"{days // 7} weeks"
    if days >= 1:
        return f"{days} day{'s' if days > 1 else ''}"
    hours = int(delta.total_seconds() // 3600)
    return f"{hours} hour{'s' if hours != 1 else ''}"


def _subject(text: str) -> str:
    """The longest word in a goal, as a crude "is this being talked about" key.

    Crude on purpose and reflected in the detector's 0.5 confidence. Anything
    cleverer here means a model, and a model here means the drift check stops
    working offline — which is when people most need it.
    """
    words = [w.strip(".,;:'\"").lower() for w in text.split() if len(w) > 5]
    return max(words, key=len) if words else ""


def _aware(value: datetime | None) -> datetime | None:
    from datetime import UTC

    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_WEEKDAYS = ["mon", "tues", "wednes", "thurs", "fri", "satur", "sun"]


def _parse_date(match: re.Match[str], now: datetime) -> datetime | None:
    iso, by_date, weekday = match.group(1), match.group(2), match.group(3)
    if iso:
        try:
            return datetime.fromisoformat(iso).replace(tzinfo=now.tzinfo)
        except ValueError:
            return None
    if by_date:
        parts = by_date.lower().split()
        day = re.sub(r"[^0-9]", "", parts[0])
        month = next((i for i, name in enumerate(_MONTHS, 1) if parts[-1].startswith(name)), None)
        if not day or month is None:
            return None
        year = now.year + (1 if month < now.month else 0)
        try:
            return datetime(year, month, int(day), tzinfo=now.tzinfo)
        except ValueError:
            return None
    if weekday:
        target = next((i for i, name in enumerate(_WEEKDAYS) if weekday.lower() == name), None)
        if target is None:
            return None
        ahead = (target - now.weekday()) % 7 or 7
        return (now + timedelta(days=ahead)).replace(hour=9, minute=0, second=0, microsecond=0)
    return None
