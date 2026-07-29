"""The vocabulary a case uses to say what good looks like.

A check is a named question asked of one outcome, answering yes, no, or *not
applicable*. That third answer is what keeps the corpus honest: a check that
cannot be evaluated — because the turn errored, because the tool loop never
ran — must not be silently counted as a pass, and must not be counted as a
failure of the prompt either.

Checks are deliberately mechanical. None of them asks a model anything. That
buys three properties worth more than sophistication:

* **They are free**, so a case can carry ten of them.
* **They are deterministic**, so two runs of the same prompt differ only where
  the model differed.
* **They are honest about their reach.** "Contains three numbered options" is a
  weak proxy for "offered three genuinely different angles", but it is a proxy
  that cannot flatter itself. Where a real judgement is needed the case says so
  in `behaviour` and a human reads the transcript.

The banned-phrase lists are the most opinionated thing here, and they encode
the house style the prompts already claim: no preamble, no filler, no hedging
into uselessness.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# Phrases that mean the model is warming up instead of answering. The house
# rules forbid preamble; this is how that is measured rather than hoped for.
PREAMBLE = (
    "great question",
    "i'd be happy to",
    "i would be happy to",
    "certainly!",
    "sure thing",
    "let me help you",
    "let's dive in",
    "here's a breakdown",
    "in this response",
    "as an ai",
    "i'm an ai",
)

# Marketing filler the Copywriter prompt names explicitly, plus the rest of the
# family. Applied to every writing agent, not just that one.
FILLER = (
    "unlock",
    "elevate",
    "seamless",
    "in today's world",
    "in today's fast-paced",
    "game-changer",
    "game changer",
    "revolutionise",
    "revolutionize",
    "cutting-edge",
    "leverage the power",
    "take it to the next level",
    "delve into",
)

# Hedging that converts an answer into a non-answer. Distinct from a *stated*
# caveat, which several prompts require exactly once — the test is whether the
# hedge replaces the answer, so these are only failures when nothing concrete
# accompanies them.
HEDGES = (
    "it depends on many factors",
    "there are many ways",
    "consult a professional",
    "i cannot provide",
    "i'm unable to provide",
    "it's important to note that everyone",
    "results may vary",
)

_SENTENCE = re.compile(r"[.!?]+(?:\s|$)")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S", re.MULTILINE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S|^\s*\*\*[^*]+\*\*\s*$", re.MULTILINE)
# A locator in the shape M5 preserves: `p. 4`, `slide 2`, `Revenue!1:40`,
# or a bare URL. Loose on purpose — this asks "did it point at something",
# not "is the citation correct".
_CITATION = re.compile(
    r"https?://\S+|\bp{1,2}\.\s?\d+|\bslide\s+\d+|\b\w+![\d:]+|\[\d+\]|\(\d{4}\)", re.IGNORECASE
)
_QUESTION = re.compile(r"\?(?:\s|$)")
_NUMBER = re.compile(r"(?<![\w.])[£$€]?\d[\d,]*(?:\.\d+)?\s?(?:%|k\b|m\b|bn\b)?")


@dataclass(frozen=True, slots=True)
class Outcome:
    """Everything a check is allowed to see about one turn."""

    text: str = ""
    agent: str = ""
    tools_called: tuple[str, ...] = ()
    tools_offered: tuple[str, ...] = ()
    confidence: float = 0.0
    candidates: tuple[str, ...] = ()
    escalated: bool = False
    error: str = ""
    cost_usd: float = 0.0
    tokens: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        """Whether there is an answer here at all to have an opinion about."""
        return not self.error and bool(self.text.strip())

    @property
    def lower(self) -> str:
        return self.text.lower()

    @property
    def words(self) -> int:
        return len(self.text.split())


# A check returns True (met), False (not met), or None (not applicable here).
Predicate = Callable[[Outcome], bool | None]


@dataclass(frozen=True, slots=True)
class Check:
    """A named yes/no/not-applicable question about an outcome."""

    label: str
    predicate: Predicate

    def __call__(self, outcome: Outcome) -> bool | None:
        try:
            return self.predicate(outcome)
        except Exception:  # a broken check must not fail the run
            return None


def _needs_text(fn: Callable[[Outcome], bool]) -> Predicate:
    """Wrap a predicate so an errored or empty turn answers 'not applicable'.

    Without this, every text check on a failed turn reads as a prompt defect,
    and a provider outage looks like a quality regression.
    """

    def predicate(outcome: Outcome) -> bool | None:
        return fn(outcome) if outcome.usable else None

    return predicate


# ── Content ───────────────────────────────────────────────────────────────────


def mentions(*terms: str, label: str = "") -> Check:
    """At least one of these appears. Terms are matched case-insensitively."""
    return Check(
        label or f"mentions {' / '.join(terms)}",
        _needs_text(lambda o: any(t.lower() in o.lower for t in terms)),
    )


def mentions_all(*terms: str, label: str = "") -> Check:
    return Check(
        label or f"covers {', '.join(terms)}",
        _needs_text(lambda o: all(t.lower() in o.lower for t in terms)),
    )


def covers(count: int, *terms: str, label: str = "") -> Check:
    """At least `count` of these appear — the useful middle between any and all."""
    return Check(
        label or f"covers {count}+ of {len(terms)} expected points",
        _needs_text(lambda o: sum(1 for t in terms if t.lower() in o.lower) >= count),
    )


def avoids(*terms: str, label: str = "") -> Check:
    return Check(
        label or f"avoids {' / '.join(terms)}",
        _needs_text(lambda o: not any(t.lower() in o.lower for t in terms)),
    )


def matches(pattern: str, *, label: str = "") -> Check:
    compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    return Check(
        label or f"matches /{pattern}/", _needs_text(lambda o: bool(compiled.search(o.text)))
    )


# ── Shape ─────────────────────────────────────────────────────────────────────


def words_between(low: int, high: int) -> Check:
    return Check(
        f"{low}–{high} words",
        _needs_text(lambda o: low <= o.words <= high),
    )


def under_words(limit: int) -> Check:
    return Check(f"under {limit} words", _needs_text(lambda o: o.words <= limit))


def options(count: int) -> Check:
    """At least `count` distinct listed items.

    A weak proxy for "genuinely different options" and labelled as such, but it
    catches the failure it was written for: the Copywriter returning one bare
    headline while its spec promised variants.
    """
    return Check(
        f"offers {count}+ distinct options",
        _needs_text(lambda o: len(_BULLET.findall(o.text)) >= count),
    )


def structured() -> Check:
    """Headings or a list — anything but an undifferentiated wall of prose."""
    return Check(
        "structured, not a wall of prose",
        _needs_text(lambda o: bool(_BULLET.search(o.text) or _HEADING.search(o.text))),
    )


def prose() -> Check:
    """The opposite, for the agents whose output should read as sentences."""
    return Check(
        "reads as prose, not a bulleted dump",
        _needs_text(lambda o: len(_BULLET.findall(o.text)) <= 1),
    )


def sentences_between(low: int, high: int) -> Check:
    return Check(
        f"{low}–{high} sentences",
        _needs_text(lambda o: low <= len(_SENTENCE.findall(o.text)) <= high),
    )


def speakable() -> Check:
    """Short, unformatted, no URLs — what the Voice Agent promises out loud."""
    return Check(
        "speakable: short, no markup, no URLs",
        _needs_text(
            lambda o: (
                o.words <= 90
                and not _BULLET.search(o.text)
                and not _HEADING.search(o.text)
                and "http" not in o.lower
            )
        ),
    )


# ── Substance ─────────────────────────────────────────────────────────────────


def quantified(count: int = 2) -> Check:
    """Contains real figures. The analyst agents are worthless without them."""
    return Check(
        f"{count}+ concrete figures",
        _needs_text(lambda o: len(_NUMBER.findall(o.text)) >= count),
    )


def cites() -> Check:
    return Check(
        "points at a source",
        _needs_text(lambda o: bool(_CITATION.search(o.text))),
    )


def asks_a_question() -> Check:
    return Check("asks the user something", _needs_text(lambda o: bool(_QUESTION.search(o.text))))


def no_preamble() -> Check:
    return Check(
        "opens with the answer",
        _needs_text(lambda o: not any(p in o.lower[:220] for p in PREAMBLE)),
    )


def no_filler() -> Check:
    return Check(
        "no marketing filler", _needs_text(lambda o: not any(f in o.lower for f in FILLER))
    )


def not_a_dodge() -> Check:
    """Hedged *and* empty. A stated caveat next to a real answer is fine — the
    prompts for Legal and Health require exactly that — so this only fires when
    the hedge is all there is."""
    return Check(
        "answers rather than deflects",
        _needs_text(
            lambda o: (
                not (
                    any(h in o.lower for h in HEDGES)
                    and (
                        o.words < 60 or (not _NUMBER.search(o.text) and not _BULLET.search(o.text))
                    )
                )
            )
        ),
    )


def states_assumptions() -> Check:
    return Check(
        "names what it assumed or lacks",
        _needs_text(
            lambda o: any(
                t in o.lower
                for t in ("assum", "i don't have", "i do not have", "unknown", "you'd need", "if ")
            )
        ),
    )


def names_an_owner() -> Check:
    """Planning output where each step belongs to somebody."""
    return Check(
        "steps carry an owner",
        _needs_text(
            lambda o: any(
                t in o.lower for t in ("owner:", "owner —", "you:", "jarvis:", "agent:", "(you)")
            )
        ),
    )


# ── Tools ─────────────────────────────────────────────────────────────────────


def called(*names: str) -> Check:
    """Reached for at least one of these. Not applicable if none were offered —
    a tool the agent never had is not a tool selection failure."""

    def predicate(outcome: Outcome) -> bool | None:
        if not outcome.tools_offered:
            return None
        if not any(n in outcome.tools_offered for n in names):
            return None
        return any(n in outcome.tools_called for n in names)

    return Check(f"reaches for {' / '.join(names)}", predicate)


def called_nothing() -> Check:
    """Answered from what it already had. The other half of tool selection:
    knowing when *not* to spend a round trip."""

    def predicate(outcome: Outcome) -> bool | None:
        if not outcome.tools_offered:
            return None
        return not outcome.tools_called

    return Check("answers without reaching for a tool", predicate)


def never_called(*names: str) -> Check:
    def predicate(outcome: Outcome) -> bool | None:
        if not outcome.tools_offered:
            return None
        return not any(n in outcome.tools_called for n in names)

    return Check(f"does not call {' / '.join(names)}", predicate)


def tool_rounds_under(limit: int) -> Check:
    """Ran the loop a sane number of times. Six rounds to list a directory is a
    prompt problem, not a model problem."""

    def predicate(outcome: Outcome) -> bool | None:
        if not outcome.tools_offered:
            return None
        return len(outcome.tools_called) <= limit

    return Check(f"{limit} or fewer tool calls", predicate)


# ── Routing ───────────────────────────────────────────────────────────────────


def escalates() -> Check:
    """Stage one declined to decide. For genuinely contested requests this is
    the correct behaviour, and it is invisible unless something asks."""
    return Check("escalated to the arbiter", lambda o: o.escalated)


def decides_alone() -> Check:
    """The opposite, and the one that pays for the two-stage design."""
    return Check("decided without the arbiter", lambda o: not o.escalated)
