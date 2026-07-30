"""The rule of three.

One customer saying something is a conversation. Three is a finding.

This module does the cheap half of that: it groups evidence by lexical overlap
and surfaces anything said by three or more *distinct* clients. It deliberately
does not try to be clever. Two people can express the same pain with no shared
words — *"I'm flying blind"* and *"I don't know what's working"* — and no
token-overlap method will ever join them.

That is fine, and it is the design. This surfaces candidates; the Friday
synthesis does the judging. A system that claimed to find every pattern would be
trusted to, and then the reading would stop.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# Enough to stop function words dominating a five-word phrase.
STOPWORDS = frozenset(
    """
    a about all also am an and any are arent as at be been but by can cant cause could
    couldnt did didnt do does doesnt doing dont for from get got had has hasnt have
    havent he her here heres hers him his how hows i id if ill im in into is isnt it
    its ive just like me my no nor not of off on one or our out over own re said same
    she should shouldnt so some still such than that thats the their them then there
    theres these they theyre theyve this those to too us ve very was wasnt we were
    werent what whats when where wheres which while who why will with wont would
    wouldnt you youll your youre youve
    """.split()  # noqa: SIM905 — a 128-element list literal is not more readable
)
# `know` is deliberately absent. "I don't know what's working" is the sentence
# this whole module exists to catch, and treating its only content word as noise
# made the flagship case score 0.2 instead of 0.33.

# Below this, a prefix match is meaningless ("we"/"were").
MIN_PREFIX = 4

# A statement with fewer meaningful words than this cannot be compared — one
# word matches far too much, and one-word evidence is bad capture anyway.
MIN_TOKENS = 2

# Containment at which two statements are treated as the same claim.
#
# This was Jaccard at 0.30 and a live smoke test showed it was wrong. Three
# clients said "I don't know what's working", "no idea what is working
# honestly", and "we genuinely don't know what's working" — obviously one
# finding — and it produced none, because Jaccard's denominator punishes the
# longer statement for containing an extra word. Real speech has filler.
#
# Containment asks the right question: *is this claim inside that statement?*
THRESHOLD = 0.50

# The rule. Three *distinct clients*, not three statements — one client saying
# the same thing three times is one client.
RULE_OF_THREE = 3


def tokens(text: str) -> set[str]:
    """Meaningful words, lowercased. Falls back to raw words if all are stopwords.

    Apostrophes are removed rather than split on, so ``don't`` becomes ``dont``
    and matches the contraction in ``STOPWORDS``. Splitting on them instead
    produces ``don`` and ``t``, which are noise words that no stopword list
    catches — and it silently drops the real word next to them.
    """
    flattened = re.sub(r"['’]", "", text.lower())
    words = {w for w in re.split(r"[^a-z0-9]+", flattened) if w}
    meaningful = words - STOPWORDS
    return meaningful or words


def _overlaps(a: str, b: str) -> bool:
    """Same word, or one is a long-enough prefix of the other."""
    if a == b:
        return True
    if len(a) < MIN_PREFIX or len(b) < MIN_PREFIX:
        return False
    return a.startswith(b) or b.startswith(a)


def similarity(left: str, right: str) -> float:
    """Containment: how much of the *shorter* statement appears in the longer.

    Prefix matching means work/working/worked agree.

    Deliberately biased toward merging rather than splitting, which is the
    opposite of the usual instinct and is right here because of how the result
    is displayed: every finding lists all of its member statements, so a wrong
    merge is obvious at a glance and costs a second to dismiss. A missed pattern
    is invisible, and invisible errors are the expensive kind.
    """
    a, b = tokens(left), tokens(right)
    shorter = min(len(a), len(b))
    if shorter < MIN_TOKENS:
        return 0.0
    shared = sum(1 for x in a if any(_overlaps(x, y) for y in b))
    return shared / shorter


@dataclass(slots=True)
class Cluster:
    """A group of statements that appear to be the same claim."""

    kind: str
    members: list[tuple[int, int, str]] = field(default_factory=list)
    """(evidence_id, client_id, verbatim), in the order seen."""

    @property
    def clients(self) -> set[int]:
        return {client_id for _, client_id, _ in self.members}

    @property
    def client_count(self) -> int:
        return len(self.clients)

    @property
    def is_finding(self) -> bool:
        """Three distinct clients. Below that it is still a conversation."""
        return self.client_count >= RULE_OF_THREE

    @property
    def label(self) -> str:
        """The shortest member — usually the least rambling phrasing of it."""
        return min((text for _, _, text in self.members), key=len, default="")


def cluster(
    rows: Iterable[tuple[int, int, str, str]], *, threshold: float = THRESHOLD
) -> list[Cluster]:
    """Group ``(evidence_id, client_id, kind, verbatim)`` into claims.

    Greedy single-pass against each cluster's first member, which keeps the
    result stable and explainable: a statement joins the earliest cluster it
    resembles, and nothing is re-partitioned behind your back.

    Sorted by distinct-client count so findings come first.
    """
    ordered = sorted(rows, key=lambda r: r[0])
    clusters: list[Cluster] = []

    for evidence_id, client_id, kind, text in ordered:
        for existing in clusters:
            if existing.kind != kind:
                continue
            seed = existing.members[0][2]
            if similarity(seed, text) >= threshold:
                existing.members.append((evidence_id, client_id, text))
                break
        else:
            clusters.append(Cluster(kind=kind, members=[(evidence_id, client_id, text)]))

    clusters.sort(key=lambda c: (-c.client_count, -len(c.members), c.label))
    return clusters


def findings(clusters: Sequence[Cluster]) -> list[Cluster]:
    """Only the clusters that have cleared the rule of three."""
    return [c for c in clusters if c.is_finding]
