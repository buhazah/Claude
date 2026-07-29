"""Linking: turning a pile of notes into a graph.

Obsidian derives backlinks itself — every `[[wikilink]]` produces one at the
other end automatically, and writing them by hand would duplicate state the
application already maintains. So Jarvis's job is not to *create* backlinks. It
is to put the outgoing links in, which is the part Obsidian cannot do, and to
leave behind a `## Related` section so the connections are legible outside
Obsidian too — in a diff, in a plain editor, in a grep.

Linking is done by exact title match and nothing cleverer, for a reason worth
stating. A fuzzy linker that connects "Ali" to "Alignment" produces a graph
that looks impressive and means nothing, and every wrong link is a wrong
retrieval later. Precision matters more than coverage here, because a missing
link costs a connection the user can add in one keystroke while a wrong one
costs their trust in the whole graph.

Two guards on top of that:

* **Titles shorter than four characters are never auto-linked.** A note called
  "CI" or "Ops" would otherwise link every occurrence of those letters inside
  other words.
* **Text already inside a link is never re-linked**, so running the linker
  twice over the same sentence is a no-op rather than `[[[[Ali]]]]`.
"""

from __future__ import annotations

import re
from functools import lru_cache

from jarvis.obsidian import naming
from jarvis.obsidian.vault import VaultManager

MIN_TITLE = 4
RELATED = "Related"
# How many related notes to list. Beyond this it stops being a pointer and
# starts being an index of the vault.
MAX_RELATED = 8

_EXISTING_LINK = re.compile(r"\[\[[^\]]*\]\]")


class Linker:
    """Inserts wikilinks and maintains `## Related`."""

    def __init__(self, vault: VaultManager) -> None:
        self._vault = vault

    def titles(self) -> dict[str, str]:
        """Every linkable note title → its path.

        Journal entries are excluded. They are dated, so their titles are
        numbers, and auto-linking `2026-07-29` wherever it appears would fill
        every note with links to days.
        """
        found: dict[str, str] = {}
        for path in self._vault.notes():
            relative = self._vault.relative(path)
            if naming.is_journal(relative):
                continue
            title = naming.title_for(relative)
            if len(title) >= MIN_TITLE:
                found[title] = relative
        return found

    def link(self, text: str, *, exclude: str = "") -> str:
        """Wrap known note titles in `[[…]]`, longest first.

        Longest first so "Northbound Supplements" wins over "Northbound" and
        the shorter match does not carve the longer title in half.
        """
        titles = self.titles()
        if exclude:
            titles.pop(naming.title_for(exclude), None)
        if not titles:
            return text

        spans = _protected(text)
        for title in sorted(titles, key=len, reverse=True):
            pattern = _word_pattern(re.escape(title))
            result: list[str] = []
            cursor = 0
            for match in pattern.finditer(text):
                if any(start <= match.start() < end for start, end in spans):
                    continue
                result.append(text[cursor : match.start()])
                result.append(f"[[{match.group(0)}]]")
                cursor = match.end()
            if cursor:
                result.append(text[cursor:])
                text = "".join(result)
                spans = _protected(text)
        return text

    def relate(self, path: str, text: str) -> None:
        """Record in `## Related` the notes this one now points at.

        Only outgoing links, and only ones that resolve. Obsidian shows the
        inbound side in its own panel, and mirroring it here would mean two
        places to keep in step — with the copy going stale the moment somebody
        edits the other note.
        """
        targets = [
            title
            for title in _linked_titles(text)
            if title in self.titles() and title != naming.title_for(path)
        ]
        if not targets:
            return

        note = self._vault.read(path)
        note.path = path
        existing = _linked_titles(note.section(RELATED))
        merged = list(dict.fromkeys([*existing, *targets]))[:MAX_RELATED]
        if merged == existing:
            return

        _replace_section(note, RELATED, "\n".join(f"- [[{title}]]" for title in merged))
        note.properties["related"] = [f"[[{title}]]" for title in merged]
        self._vault.write(note)


@lru_cache(maxsize=512)
def _word_pattern(escaped: str) -> re.Pattern[str]:
    """Match a title only at word boundaries, case-sensitively.

    Case-sensitive because note titles are proper nouns, and matching
    case-insensitively links every "research" in a sentence to a note called
    Research.
    """
    return re.compile(rf"(?<![\w\[]){escaped}(?![\w\]])")


def _protected(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _EXISTING_LINK.finditer(text)]


def _linked_titles(text: str) -> list[str]:
    from jarvis.obsidian.note import _WIKILINK

    return list(dict.fromkeys(m.group(1).strip() for m in _WIKILINK.finditer(text)))


def _replace_section(note: object, heading: str, body: str) -> None:
    """Rewrite one `## section`, leaving the rest of the note alone."""
    from jarvis.obsidian.note import _HEADING, Note

    assert isinstance(note, Note)
    lines = note.body.splitlines()
    out: list[str] = []
    depth = 0
    written = False
    for line in lines:
        match = _HEADING.match(line)
        if match and not depth and match.group(2).strip().lower() == heading.lower():
            depth = len(match.group(1))
            out += [line, "", body]
            written = True
            continue
        if depth and match and len(match.group(1)) <= depth:
            depth = 0
        if not depth:
            out.append(line)
    if not written:
        out += ["", f"## {heading}", "", body]
    note.body = "\n".join(out).strip("\n")
