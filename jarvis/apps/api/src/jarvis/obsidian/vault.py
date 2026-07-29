"""The vault: where files live, and the rules for touching them.

Jarvis writes into a directory a human owns and syncs. That makes three things
non-negotiable, and they are the whole of this module.

**A write never half-happens.** Every save is a temp file plus an atomic
replace. A vault is usually inside iCloud, Dropbox or Syncthing, and those
watch for changes; a partially written note is one a sync client will happily
propagate to every other device before the rest of it arrives.

**A path never escapes the vault.** Note names come from memory tags, which
come from agents, which read untrusted documents. `../../.ssh/config` is a
plausible note title if nobody checks, so every path is resolved and required
to sit under the root.

**A write never loses what was there.** Saving means parse, merge, re-render —
never truncate and rewrite. The user's headings, their prose, their plugin
frontmatter and their manual links all survive a Jarvis write, because the
moment one of them does not, the vault stops being somewhere they keep things.

Reading is cached by mtime and size. A vault of a few thousand notes is
re-scanned on every recall otherwise, and recall is on the hot path of every
single agent turn.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

from jarvis.kernel.errors import PermissionDeniedError
from jarvis.obsidian import note as note_format
from jarvis.obsidian.note import Note

log = structlog.get_logger(__name__)

MARKDOWN = ".md"
# Obsidian's own reserved characters, plus the ones Windows rejects. A note
# name is derived from user data, so this is a sanitiser and not a suggestion.
ILLEGAL = set('#^[]|<>:"?*\\/\0')


@dataclass(frozen=True, slots=True)
class Stat:
    mtime_ns: int
    size: int


def safe_name(text: str, *, fallback: str = "Untitled") -> str:
    """A filename-safe note title.

    Not a slug: the name is what the user sees in their sidebar and what
    `[[wikilinks]]` have to match, so spaces and capitals are kept and only
    what a filesystem or Obsidian would reject is removed.
    """
    cleaned = "".join(" " if char in ILLEGAL else char for char in text)
    cleaned = " ".join(cleaned.split()).strip(". ")
    # Trailing dots and spaces are legal on POSIX and silently stripped by
    # Windows, which would make the same vault resolve differently per machine.
    return cleaned[:120] or fallback


class VaultManager:
    """Owns the directory. Everything else in this package goes through it."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self._cache: dict[Path, tuple[Stat, Note]] = {}

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def exists(self) -> bool:
        return self.root.is_dir()

    # ── Paths ─────────────────────────────────────────────────────────────────

    def resolve(self, relative: str) -> Path:
        """A path inside the vault, or an error.

        Resolved before the check, so `Projects/../../etc/passwd` is caught
        along with the obvious form. Symlinks resolve too: a link planted
        inside the vault pointing out of it is the interesting attack, and
        comparing unresolved paths would miss it.
        """
        if not relative.endswith(MARKDOWN):
            relative += MARKDOWN
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise PermissionDeniedError(f"path escapes the vault: {relative}")
        return candidate

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def notes(self) -> list[Path]:
        """Every note, excluding Obsidian's own configuration directory."""
        if not self.exists:
            return []
        return sorted(
            path
            for path in self.root.rglob(f"*{MARKDOWN}")
            if not any(part.startswith(".") for part in path.relative_to(self.root).parts)
        )

    # ── Reading ───────────────────────────────────────────────────────────────

    def read(self, relative: str) -> Note:
        return self.read_path(self.resolve(relative))

    def read_path(self, path: Path) -> Note:
        """Parse a note, from cache when the file has not changed.

        Keyed on mtime *and* size: mtime alone has one-second resolution on
        some filesystems, and a same-second edit that keeps the length is
        exactly what an automated writer produces.
        """
        try:
            info = path.stat()
        except OSError:
            return Note(path=self._name(path))
        stat = Stat(mtime_ns=info.st_mtime_ns, size=info.st_size)
        if (cached := self._cache.get(path)) and cached[0] == stat:
            return cached[1]

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("vault_note_unreadable", path=str(path), error=str(exc))
            return Note(path=self._name(path))

        parsed = note_format.parse(text, path=self._name(path))
        self._cache[path] = (stat, parsed)
        return parsed

    def _name(self, path: Path) -> str:
        try:
            return self.relative(path)
        except ValueError:
            return path.name

    # ── Writing ───────────────────────────────────────────────────────────────

    def write(self, note: Note) -> Path:
        """Save a note atomically. Returns where it landed."""
        path = self.resolve(note.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = note_format.render(note)

        # Nothing to do — and doing nothing is worth the check, because every
        # write wakes a sync client and touches the user's file history.
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return path

        handle, temporary = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(text)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

        info = path.stat()
        self._cache[path] = (Stat(mtime_ns=info.st_mtime_ns, size=info.st_size), note)
        return path

    def delete(self, relative: str) -> bool:
        path = self.resolve(relative)
        self._cache.pop(path, None)
        try:
            path.unlink()
            return True
        except OSError:
            return False

    def forget_cache(self) -> None:
        """Drop everything cached. For a rescan after an external sync."""
        self._cache.clear()
