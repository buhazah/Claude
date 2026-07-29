"""The file format: a note a human wants to read, that Jarvis can also parse.

Everything about this module follows from one rule.

**The body belongs to the user. The frontmatter belongs to Jarvis.**

A vault Jarvis writes into is a vault the user also edits — that is the entire
point of using Obsidian rather than a database with a markdown exporter. So
nothing Jarvis needs may live in the prose, because the prose is going to be
rewritten, reordered and deleted by somebody who was not thinking about
Jarvis's data model when they did it. And nothing the user has to look at may
be machine noise, because a note full of inline metadata is a note nobody
opens.

That splits the frontmatter in two:

* **Readable keys** — `title`, `type`, `tags`, `created`, `updated`, `related` —
  written as plain YAML, because these are what Obsidian's own properties UI,
  Dataview queries and the graph view read. They are for the user.
* **`jarvis:`** — one line of JSON, holding per-block metadata (kind, scope,
  salience, timestamps, provenance) that no human should have to scroll past.
  YAML is a superset of JSON, so Obsidian parses it happily and Python round-
  trips it exactly.

That last point is also why there is no YAML dependency here. A general YAML
library would be a heavier commitment than the format needs, and — worse — a
full parse-and-reserialise loses comments and reorders keys, which mangles a
file a human has been editing. Instead: the small readable subset is parsed and
rewritten, and **every frontmatter line Jarvis does not recognise is preserved
verbatim**. A vault with a Templater config or a Dataview inline field in its
frontmatter comes back out unchanged.

Individual memories are Obsidian **block references** — `^mem-01j9x` at the end
of a line. That is the native anchor for "this specific line", it survives the
line being moved, and it is something a human can link to from another note.
Block ids may only contain letters, digits and hyphens, so the underscore in
`mem_01j9x` becomes a hyphen on the way in and back on the way out.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

FRONTMATTER_FENCE = "---"
JARVIS_KEY = "jarvis"
SCHEMA_VERSION = 1

# Keys Jarvis writes as readable YAML. Order is fixed so a rewrite produces a
# minimal diff rather than a reshuffle the user has to review.
READABLE_KEYS = ("title", "type", "tags", "created", "updated", "related")

# Obsidian's own constraint on block ids.
_BLOCK_ID = re.compile(r"\^([A-Za-z0-9-]+)\s*$")
_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def to_anchor(memory_id: str) -> str:
    """`mem_01j9x` → `mem-01j9x`. Obsidian block ids forbid underscores."""
    return memory_id.replace("_", "-")


def from_anchor(anchor: str) -> str:
    """The inverse. Only the first hyphen is a prefix separator; ids are
    Crockford base32 and contain no hyphens of their own."""
    return anchor.replace("-", "_", 1)


@dataclass(slots=True)
class Block:
    """One line of a note that Jarvis put there and can find again."""

    anchor: str
    text: str
    heading: str = ""

    @property
    def memory_id(self) -> str:
        return from_anchor(self.anchor)


@dataclass
class Note:
    """A parsed markdown note. Round-trips: ``parse(render(n)) == n``."""

    path: str
    body: str = ""
    # Readable frontmatter, in the order it will be written.
    properties: dict[str, Any] = field(default_factory=dict)
    # Per-block metadata, keyed by memory id. Jarvis's private half.
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Frontmatter lines Jarvis did not recognise, kept exactly as found so a
    # human's Dataview fields and plugin config survive a rewrite.
    passthrough: list[str] = field(default_factory=list)

    # ── Reading ───────────────────────────────────────────────────────────────

    def anchored(self) -> list[Block]:
        """Every line carrying a block id, with the heading it sits under.

        Read from the *body*, not from `blocks`, because the body is what the
        user edits. A memory whose line was deleted by hand no longer exists,
        whatever the frontmatter still says about it.
        """
        found: list[Block] = []
        heading = ""
        for line in self.body.splitlines():
            if match := _HEADING.match(line):
                heading = match.group(2).strip()
                continue
            anchor = _BLOCK_ID.search(line)
            if not anchor:
                continue
            text = line[: anchor.start()].rstrip()
            if item := _LIST_ITEM.match(text):
                text = item.group(1)
            found.append(Block(anchor=anchor.group(1), text=text.strip(), heading=heading))
        return found

    def links(self) -> list[str]:
        """Outgoing wikilink targets, in order of appearance, deduplicated."""
        seen: dict[str, None] = {}
        for match in _WIKILINK.finditer(self.body):
            seen.setdefault(match.group(1).strip(), None)
        return list(seen)

    def section(self, heading: str) -> str:
        """The body under one `## heading`, or empty."""
        lines = self.body.splitlines()
        out: list[str] = []
        depth = 0
        for line in lines:
            match = _HEADING.match(line)
            if match and not depth and match.group(2).strip().lower() == heading.lower():
                depth = len(match.group(1))
                continue
            if depth and match and len(match.group(1)) <= depth:
                break
            if depth:
                out.append(line)
        return "\n".join(out).strip()

    # ── Writing ───────────────────────────────────────────────────────────────

    def upsert_block(self, memory_id: str, text: str, heading: str) -> bool:
        """Put a memory in the note under `heading`. True if anything changed.

        Idempotent by memory id *and* by text: writing the same fact twice
        under a new id updates the existing line rather than producing a second
        copy, which is what "merge duplicate knowledge" means in practice.
        """
        anchor = to_anchor(memory_id)
        for block in self.anchored():
            if block.anchor == anchor:
                if block.text == text:
                    return False
                self._replace_block(anchor, text)
                return True
            if _normalise(block.text) == _normalise(text):
                # Same knowledge, different id: keep the line that is already
                # there and the id already linked to, and record the alias so
                # recall by the new id still lands somewhere.
                self.blocks.setdefault(memory_id, {})["duplicate_of"] = block.memory_id
                return False
        self._append_under(heading, f"- {text} ^{anchor}")
        return True

    def remove_block(self, memory_id: str) -> bool:
        anchor = to_anchor(memory_id)
        kept = [
            line
            for line in self.body.splitlines()
            if not ((m := _BLOCK_ID.search(line)) and m.group(1) == anchor)
        ]
        changed = len(kept) != len(self.body.splitlines())
        if changed:
            self.body = "\n".join(kept)
        self.blocks.pop(memory_id, None)
        return changed

    def prune(self) -> list[str]:
        """Drop metadata for blocks the user deleted from the body.

        Called on every load. Without it the frontmatter grows forever and
        recall returns memories whose text is gone — which reads to the user as
        Jarvis refusing to forget something they deleted.
        """
        live = {block.memory_id for block in self.anchored()}
        # A duplicate alias is live while the block it points at is.
        aliases = {
            mid: meta.get("duplicate_of")
            for mid, meta in self.blocks.items()
            if meta.get("duplicate_of")
        }
        orphaned = [
            mid
            for mid in self.blocks
            if mid not in live and (mid not in aliases or aliases[mid] not in live)
        ]
        for memory_id in orphaned:
            self.blocks.pop(memory_id, None)
        return orphaned

    def _replace_block(self, anchor: str, text: str) -> None:
        out = []
        for line in self.body.splitlines():
            match = _BLOCK_ID.search(line)
            if match and match.group(1) == anchor:
                indent = line[: len(line) - len(line.lstrip())]
                out.append(f"{indent}- {text} ^{anchor}")
            else:
                out.append(line)
        self.body = "\n".join(out)

    def _append_under(self, heading: str, line: str) -> None:
        """Add a line at the end of `## heading`, creating the section if new.

        Appended at the *end* of the section rather than the top, because a
        note read top to bottom should read chronologically, and because
        inserting at the top would move every existing line's position in the
        user's editor on every write.
        """
        lines = self.body.splitlines()
        target = None
        depth = 0
        for i, existing in enumerate(lines):
            match = _HEADING.match(existing)
            if not match:
                continue
            if not depth and match.group(2).strip().lower() == heading.lower():
                depth = len(match.group(1))
                target = i
                continue
            if depth and len(match.group(1)) <= depth:
                target = i - 1
                break
        if target is None:
            block = ["", f"## {heading}", "", line]
            self.body = ("\n".join(lines) + "\n".join(block)).strip("\n") if lines else line
            self.body = "\n".join([*lines, *block]).strip("\n")
            return
        # Walk back over trailing blank lines so the new line joins the list
        # rather than starting a new paragraph after a gap.
        end = target
        while end > 0 and not lines[end].strip():
            end -= 1
        lines.insert(end + 1, line)
        self.body = "\n".join(lines)


def _normalise(text: str) -> str:
    """For duplicate detection: case, punctuation and wikilink syntax removed.

    Wikilinks are stripped because Jarvis links entity names as it writes, so
    the same sentence written twice differs only by whether the linker had seen
    the entity yet — and treating those as different memories would fill the
    vault with near-copies.
    """
    without_links = _WIKILINK.sub(lambda m: m.group(1), text)
    return re.sub(r"[^a-z0-9 ]+", "", without_links.lower()).strip()


# ── Frontmatter ───────────────────────────────────────────────────────────────


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_render_scalar(v) for v in value) + "]"
    return _render_scalar(value)


def _render_scalar(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    # Quote anything YAML would otherwise read as structure. Wikilinks are the
    # common case: a bare [[Ali]] is a nested flow sequence, not a string.
    if not text or text[0] in "[{#&*!|>%@`'\"" or ":" in text or text != text.strip():
        return json.dumps(text)
    return text


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in _split_flow(inner)]
    return _parse_scalar(raw)


def _parse_scalar(raw: str) -> Any:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        try:
            return json.loads(raw) if raw[0] == '"' else raw[1:-1]
        except json.JSONDecodeError:
            return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    return raw


def _split_flow(inner: str) -> list[str]:
    """Split a flow sequence on commas that are not inside quotes or brackets."""
    parts: list[str] = []
    depth, quote, current = 0, "", []
    for char in inner:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and not depth:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return [p for p in parts if p.strip()]


def parse(text: str, *, path: str = "") -> Note:
    """Read a note. Anything unrecognised in the frontmatter is preserved."""
    note = Note(path=path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        note.body = text.strip("\n")
        return note

    end = next(
        (i for i in range(1, len(lines)) if lines[i].strip() == FRONTMATTER_FENCE),
        None,
    )
    if end is None:  # an unterminated fence is not frontmatter
        note.body = text.strip("\n")
        return note

    for line in lines[1:end]:
        if not line.strip():
            continue
        key, separator, raw = line.partition(":")
        key = key.strip()
        if not separator or (key not in READABLE_KEYS and key != JARVIS_KEY):
            note.passthrough.append(line)
            continue
        if key == JARVIS_KEY:
            try:
                payload = json.loads(raw.strip() or "{}")
                note.blocks = dict(payload.get("blocks", {}))
            except (json.JSONDecodeError, AttributeError):
                # Corrupt metadata is recoverable — the body still holds the
                # knowledge — so lose the metadata rather than the note.
                note.blocks = {}
            continue
        note.properties[key] = _parse_value(raw)

    note.body = "\n".join(lines[end + 1 :]).strip("\n")
    return note


def render(note: Note) -> str:
    """Write a note. Stable ordering, so a no-op write is a no-op diff."""
    out = [FRONTMATTER_FENCE]
    for key in READABLE_KEYS:
        if key in note.properties and note.properties[key] not in (None, "", []):
            out.append(f"{key}: {_render_value(note.properties[key])}")
    out.extend(note.passthrough)
    if note.blocks:
        payload = {"v": SCHEMA_VERSION, "blocks": note.blocks}
        out.append(f"{JARVIS_KEY}: {json.dumps(payload, separators=(',', ':'), default=str)}")
    out += [FRONTMATTER_FENCE, "", note.body.strip("\n"), ""]
    return "\n".join(out)
