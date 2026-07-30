"""Obsidian as long-term memory.

Almost every test here is about the same thing from a different angle: **the
user's edits survive.** That is the premise the integration rests on — a
memory system you cannot correct by hand is worse than none — and it is the
property that quietly breaks first, because every convenient implementation
(cache the parse, rewrite the file, keep a shadow record) breaks it.

The rest are about not damaging a directory somebody else owns: no path
escapes the vault, no write half-happens, no rewrite loses a plugin's
frontmatter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import FrozenClock
from jarvis.kernel.errors import PermissionDeniedError
from jarvis.memory.models import MemoryKind
from jarvis.obsidian import KnowledgeIndexer, MemorySynchronizer, ObsidianStore, VaultManager
from jarvis.obsidian import note as note_format
from jarvis.obsidian.links import Linker
from jarvis.obsidian.note import Note
from jarvis.obsidian.vault import safe_name

NOW = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


@pytest.fixture
def vault(tmp_path: Path) -> VaultManager:
    manager = VaultManager(tmp_path / "vault")
    manager.ensure()
    return manager


@pytest.fixture
def store(vault: VaultManager) -> ObsidianStore:
    return ObsidianStore(vault, clock=FrozenClock(NOW))


# ── The file format ───────────────────────────────────────────────────────────


def test_a_note_round_trips_exactly() -> None:
    original = """---
title: Northbound
type: project
tags: [project/northbound, supplements]
created: 2026-07-01
jarvis: {"v":1,"blocks":{"mem_abc":{"kind":"decision","scope":"business"}}}
---

# Northbound

## Decisions

- Stopped taking consulting work ^mem-abc
"""
    parsed = note_format.parse(original, path="Projects/Northbound.md")
    assert parsed.properties["title"] == "Northbound"
    assert parsed.properties["tags"] == ["project/northbound", "supplements"]
    assert parsed.blocks["mem_abc"]["kind"] == "decision"
    assert note_format.parse(note_format.render(parsed)).properties == parsed.properties
    assert note_format.parse(note_format.render(parsed)).body == parsed.body


def test_frontmatter_jarvis_does_not_understand_is_preserved_verbatim() -> None:
    """A vault has plugins. Templater config, Dataview inline fields and
    anything else in the frontmatter must come back out untouched, or Jarvis
    is a program that breaks the user's other tools."""
    original = """---
title: Northbound
cssclasses: [wide-table]
dataview-status: active
banner: "![[cover.png]]"
---

Body.
"""
    parsed = note_format.parse(original)
    rendered = note_format.render(parsed)
    assert "cssclasses: [wide-table]" in rendered
    assert "dataview-status: active" in rendered
    assert 'banner: "![[cover.png]]"' in rendered


def test_a_body_edited_by_hand_is_the_truth() -> None:
    """The single most important behaviour. If the frontmatter says a memory
    reads one thing and the line says another, the line wins — because the
    line is what the user changed."""
    note = note_format.parse(
        '---\njarvis: {"v":1,"blocks":{"mem_abc":{"kind":"fact"}}}\n---\n\n'
        "- Margin is 71%, not 62% ^mem-abc\n"
    )
    blocks = note.anchored()
    assert blocks[0].text == "Margin is 71%, not 62%"


def test_metadata_for_a_line_the_user_deleted_is_pruned() -> None:
    """Otherwise recall keeps returning something the user deleted, which reads
    as Jarvis refusing to forget."""
    note = note_format.parse(
        '---\njarvis: {"v":1,"blocks":{"mem_gone":{"kind":"fact"},"mem_here":{"kind":"fact"}}}\n'
        "---\n\n- Still here ^mem-here\n"
    )
    assert note.prune() == ["mem_gone"]
    assert set(note.blocks) == {"mem_here"}


def test_an_unterminated_fence_is_not_treated_as_frontmatter() -> None:
    note = note_format.parse("---\ntitle: x\n\nno closing fence")
    assert note.properties == {}
    assert "no closing fence" in note.body


def test_corrupt_jarvis_metadata_loses_the_metadata_not_the_note() -> None:
    note = note_format.parse("---\njarvis: {not json\n---\n\n- A fact ^mem-abc\n")
    assert note.blocks == {}
    assert note.anchored()[0].text == "A fact"


def test_writing_the_same_knowledge_twice_does_not_duplicate_the_line() -> None:
    note = Note(path="x.md")
    assert note.upsert_block("mem_1", "Gross margin is 62%", "Facts")
    assert not note.upsert_block("mem_2", "gross margin is 62%.", "Facts")
    assert len(note.anchored()) == 1
    assert note.blocks["mem_2"]["duplicate_of"] == "mem_1"


def test_a_wikilink_does_not_make_the_same_fact_look_new() -> None:
    """Jarvis links entity names as it writes, so the same sentence differs by
    whether the linker had seen the entity yet. Treating those as different
    memories would fill the vault with near-copies."""
    note = Note(path="x.md")
    note.upsert_block("mem_1", "Ali handles operations", "People")
    assert not note.upsert_block("mem_2", "[[Ali]] handles operations", "People")


# ── The directory ─────────────────────────────────────────────────────────────


def test_a_path_cannot_escape_the_vault(vault: VaultManager) -> None:
    """Note names come from tags, which come from agents, which read untrusted
    documents. `../../.ssh/config` is a plausible note title."""
    for attempt in ("../outside", "Projects/../../escape", "/etc/passwd"):
        with pytest.raises(PermissionDeniedError):
            vault.resolve(attempt)


def test_a_symlink_out_of_the_vault_is_caught(vault: VaultManager, tmp_path: Path) -> None:
    """Comparing unresolved paths would miss this one, and it is the
    interesting attack: a link planted inside the vault pointing out."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault.root / "escape").symlink_to(outside)
    with pytest.raises(PermissionDeniedError):
        vault.resolve("escape/notes")


def test_safe_name_strips_what_obsidian_and_windows_reject() -> None:
    assert safe_name("Q3/Q4: plan?") == "Q3 Q4 plan"
    assert safe_name("trailing dots...") == "trailing dots"
    assert safe_name("") == "Untitled"
    assert safe_name("^[]|#") == "Untitled"


def test_an_identical_write_does_not_touch_the_file(vault: VaultManager) -> None:
    """Every write wakes a sync client and adds a version to the user's file
    history, so a no-op has to actually be a no-op."""
    note = Note(path="Areas/x.md", body="- Hello ^mem-1")
    path = vault.write(note)
    before = path.stat().st_mtime_ns
    vault.write(note)
    assert path.stat().st_mtime_ns == before


def test_the_read_cache_notices_a_same_second_edit(vault: VaultManager) -> None:
    """mtime alone has one-second resolution on some filesystems, and a
    same-second edit that keeps the length is exactly what an automated writer
    produces."""
    path = vault.resolve("Areas/x")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ntitle: A\n---\n\nfirst\n")
    assert vault.read("Areas/x").body == "first"
    path.write_text("---\ntitle: B\n---\n\nsecond\n")
    assert vault.read("Areas/x").body == "second"


# ── As a memory store ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_memory_becomes_a_line_in_a_note_and_comes_back(
    store: ObsidianStore, vault: VaultManager
) -> None:
    memory = await store.remember(
        "Gross margin is 62%", kind=MemoryKind.FACT, tags=["project/Northbound"]
    )

    written = (vault.root / "Projects" / "Northbound.md").read_text()
    assert "Gross margin is 62%" in written
    assert "^mem-" in written
    assert "## Facts" in written
    assert "type: project" in written

    recalls = await store.search("what is the margin")
    assert [r.memory.content for r in recalls] == ["Gross margin is 62%"]
    assert recalls[0].memory.id == memory.id
    assert recalls[0].memory.kind is MemoryKind.FACT


@pytest.mark.asyncio
async def test_an_edit_in_obsidian_changes_what_jarvis_recalls(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """The premise of the whole integration, end to end."""
    await store.remember("Gross margin is 62%", tags=["project/Northbound"])

    path = vault.root / "Projects" / "Northbound.md"
    path.write_text(path.read_text().replace("62%", "71%"))
    vault.forget_cache()

    recalls = await store.search("margin")
    assert "71%" in recalls[0].memory.content


@pytest.mark.asyncio
async def test_deleting_a_line_in_obsidian_forgets_the_memory(
    store: ObsidianStore, vault: VaultManager
) -> None:
    await store.remember("Something wrong I typed", tags=["project/Northbound"])
    path = vault.root / "Projects" / "Northbound.md"
    path.write_text(
        "\n".join(line for line in path.read_text().splitlines() if "^mem-" not in line)
    )
    vault.forget_cache()

    assert await store.count() == 0
    assert await store.search("something wrong") == []


@pytest.mark.asyncio
async def test_recall_respects_scope_exactly_as_every_other_store_does(
    store: ObsidianStore,
) -> None:
    await store.remember("Personal thing about Sam", scope="life_coach")
    await store.remember("Acme renews in March", scope="business:sales")
    await store.remember("Everyone can see this", scope="global")

    business = [r.memory.content for r in await store.search("Sam", scope="business:sales")]
    assert not any("Sam" in text for text in business)

    personal = [r.memory.content for r in await store.search("Sam", scope="life_coach")]
    assert any("Sam" in text for text in personal)


@pytest.mark.asyncio
async def test_a_scope_with_a_colon_becomes_a_folder(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """A colon is illegal in a Windows filename and reserved by Obsidian, and
    the nesting is what the scope meant anyway."""
    await store.remember("Acme renews in March", scope="business:sales")
    assert (vault.root / "Areas" / "business" / "sales.md").exists()


@pytest.mark.asyncio
async def test_an_episodic_memory_lands_in_the_day_as_a_pointer(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """A line, not a copy. Two copies drift, and the one the user corrects is
    never the one recall reads."""
    await store.remember(
        "Decided to drop the subscription tier",
        kind=MemoryKind.DECISION,
        tags=["project/Northbound"],
    )
    journal = (vault.root / "Journal" / "2026-07-29.md").read_text()
    assert "[[Northbound]]" in journal
    assert "type: journal" in journal


@pytest.mark.asyncio
async def test_forgetting_removes_the_line(store: ObsidianStore, vault: VaultManager) -> None:
    memory = await store.remember("Temporary thing", tags=["project/Northbound"])
    assert await store.forget(memory.id)
    assert "Temporary thing" not in (vault.root / "Projects" / "Northbound.md").read_text()
    assert await store.get(memory.id) is None


@pytest.mark.asyncio
async def test_memory_events_still_reach_the_bus(vault: VaultManager) -> None:
    """The activity rail, observability and workflow triggers are all
    subscribers. A store that stops publishing silently unwires them."""
    bus = EventBus()
    store = ObsidianStore(vault, bus=bus, clock=FrozenClock(NOW))
    subscription = bus.subscribe("memory.**")
    await store.remember("A fact worth keeping")
    topics = [subscription.queue.get_nowait().topic for _ in range(subscription.queue.qsize())]
    assert "memory.written" in topics


# ── Linking ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_mentioned_note_is_linked_and_a_short_title_is_not(
    store: ObsidianStore, vault: VaultManager
) -> None:
    await store.remember("Runs operations", tags=["person/Alison"])
    await store.remember("Owns CI", tags=["topic/CI"])
    await store.remember("Alison is reviewing the CI pipeline", tags=["project/Northbound"])

    written = (vault.root / "Projects" / "Northbound.md").read_text()
    assert "[[Alison]]" in written
    # "CI" is two characters: auto-linking it would link the letters inside
    # other words across the whole vault.
    assert "[[CI]]" not in written


def test_linking_is_idempotent_and_case_sensitive(vault: VaultManager) -> None:
    vault.write(Note(path="People/Alison.md", body="x"))
    linker = Linker(vault)
    once = linker.link("Alison approved it")
    assert once == "[[Alison]] approved it"
    assert linker.link(once) == once, "running the linker twice must not nest links"
    assert linker.link("alison approved it") == "alison approved it"


def test_the_longest_matching_title_wins(vault: VaultManager) -> None:
    """Otherwise the shorter match carves the longer title in half."""
    vault.write(Note(path="Projects/Northbound.md", body="x"))
    vault.write(Note(path="Projects/Northbound Supplements.md", body="x"))
    assert (
        Linker(vault)
        .link("Northbound Supplements ships Friday")
        .startswith("[[Northbound Supplements]]")
    )


@pytest.mark.asyncio
async def test_related_lists_the_notes_this_one_points_at(
    store: ObsidianStore, vault: VaultManager
) -> None:
    await store.remember("Runs operations", tags=["person/Alison"])
    await store.remember("Alison owns the launch", tags=["project/Northbound"])
    written = (vault.root / "Projects" / "Northbound.md").read_text()
    assert "## Related" in written
    assert "- [[Alison]]" in written


# ── The index ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_index_finds_orphans_backlinks_and_cold_notes(
    store: ObsidianStore, vault: VaultManager
) -> None:
    await store.remember("Runs operations", tags=["person/Alison"])
    await store.remember("Alison owns the launch", tags=["project/Northbound"])
    await store.remember("Nothing links to this", tags=["project/Forgotten"])

    index = KnowledgeIndexer(vault, clock=FrozenClock(NOW)).build()
    assert index.backlinks["Alison"] == ["Northbound"]
    assert "Forgotten" in {note.title for note in index.orphans()}
    assert index.notes["Northbound"].type == "project"

    later = FrozenClock(NOW + timedelta(days=90))
    cold = KnowledgeIndexer(vault, clock=later).build().cold(now=later.now())
    assert {note.title for note in cold} >= {"Northbound", "Forgotten"}


@pytest.mark.asyncio
async def test_the_index_does_not_report_every_past_day_as_neglected(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """A journal entry is supposed to stop changing. Listing them as cold would
    bury the one project that genuinely is."""
    await store.remember("A meeting happened", kind=MemoryKind.EVENT)
    later = FrozenClock(NOW + timedelta(days=90))
    cold = KnowledgeIndexer(vault, clock=later).build().cold(now=later.now())
    assert not any(note.type == "journal" for note in cold)


@pytest.mark.asyncio
async def test_unlinked_mentions_are_the_connections_jarvis_missed(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """The target note usually did not exist when the line was written, which
    is why this cannot be a one-shot job at write time."""
    await store.remember("Alison is reviewing it", tags=["project/Northbound"])
    await store.remember("Runs operations", tags=["person/Alison"])

    mentions = KnowledgeIndexer(vault, clock=FrozenClock(NOW)).build().unlinked_mentions()
    assert ("Projects/Northbound.md", "Alison") in mentions


# ── Synchronising ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_hand_edited_note_wins_over_the_primary_store(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """The conflict rule, and it is not negotiable."""
    from jarvis.memory.store import InMemoryStore

    primary = InMemoryStore()
    synchroniser = MemorySynchronizer(vault=store, primary=primary, clock=FrozenClock(NOW))

    await store.remember("Gross margin is 62%", tags=["project/Northbound"])
    assert (await synchroniser.pull()).imported == 1

    path = vault.root / "Projects" / "Northbound.md"
    path.write_text(path.read_text().replace("62%", "71%"))
    vault.forget_cache()

    report = await synchroniser.pull()
    assert report.updated == 1
    recalled = await primary.search("margin")
    assert "71%" in recalled[0].memory.content


@pytest.mark.asyncio
async def test_pulling_twice_with_no_edits_changes_nothing(store: ObsidianStore) -> None:
    from jarvis.memory.store import InMemoryStore

    primary = InMemoryStore()
    synchroniser = MemorySynchronizer(vault=store, primary=primary, clock=FrozenClock(NOW))
    await store.remember("A durable fact", tags=["project/Northbound"])

    await synchroniser.pull()
    second = await synchroniser.pull()
    assert second.changed == 0
    assert await primary.count() == 1


@pytest.mark.asyncio
async def test_a_finished_run_leaves_knowledge_behind(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """'Every completed task should leave behind useful knowledge inside the
    vault' — a pointer to the run, not a second copy of the transcript."""
    synchroniser = MemorySynchronizer(vault=store, clock=FrozenClock(NOW))
    await synchroniser.record_completion(
        request="Work out whether to move to subscription pricing",
        agent="financial_analyst",
        outcome="Recommended annual-only at £180, breaking even in month seven.",
        run_id="run_123",
        project="Northbound",
    )
    written = (vault.root / "Projects" / "Northbound.md").read_text()
    assert "subscription pricing" in written
    assert "annual-only" in written
    assert "run:run_123" in written
    assert (vault.root / "Journal" / "2026-07-29.md").exists()


@pytest.mark.asyncio
async def test_a_broken_vault_does_not_take_the_kernel_with_it(vault: VaultManager) -> None:
    """A vault on a disconnected network drive is a degraded mirror, not an
    outage. The memory is already in the primary store."""
    from jarvis.memory.store import InMemoryStore

    class Exploding(ObsidianStore):
        async def remember(self, *args: object, **kwargs: object) -> object:
            raise OSError("network drive is not there")

    primary = InMemoryStore()
    memory = await primary.remember("A fact")
    synchroniser = MemorySynchronizer(
        vault=Exploding(vault, clock=FrozenClock(NOW)), primary=primary
    )
    await synchroniser._mirror(memory.id)
    assert await primary.count() == 1


# ── Wired into the kernel ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_configured_vault_becomes_the_kernels_memory(tmp_path: Path) -> None:
    """End to end through the composition root: an agent turn writes a note.

    Also the test that the one-way dependency holds — `jarvis.obsidian` is
    imported by the container and by nothing else, so this passing while
    `test_the_kernel_does_not_import_obsidian` also passes is the whole
    architectural claim.
    """
    from jarvis.config import Settings
    from jarvis.kernel import container

    jarvis = container.build(
        Settings(
            environment="test",
            enable_scheduler=False,
            obsidian_vault=str(tmp_path / "vault"),
        )
    )
    await jarvis.memory.remember("Gross margin is 62%", tags=["project/Northbound"])

    assert (tmp_path / "vault" / "Projects" / "Northbound.md").exists()
    recalls = await jarvis.memory.search("margin")
    assert "62%" in recalls[0].memory.content
    assert jarvis.obsidian is not None


@pytest.mark.asyncio
async def test_without_a_vault_nothing_changes(tmp_path: Path) -> None:
    from jarvis.config import Settings
    from jarvis.kernel import container

    jarvis = container.build(Settings(environment="test", enable_scheduler=False))
    assert jarvis.obsidian is None
    await jarvis.memory.remember("A fact")
    assert not list(tmp_path.rglob("*.md"))


def test_the_kernel_does_not_import_obsidian() -> None:
    """The architectural constraint, asserted rather than trusted.

    Delete `jarvis/obsidian/` and the kernel must still build, still run and
    still remember. The composition root is the single exception, because
    knowing which adapters exist is the entire job of a composition root.
    """
    import ast
    from pathlib import Path as P

    root = P(__file__).parent.parent / "src" / "jarvis"
    offenders = []
    for source in root.rglob("*.py"):
        relative = source.relative_to(root).as_posix()
        if relative.startswith("obsidian/") or relative == "kernel/container.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(name.startswith("jarvis.obsidian") for name in imported):
                offenders.append(relative)
    assert not offenders, (
        f"jarvis core must not import the Obsidian adapter: {sorted(set(offenders))}"
    )


@pytest.mark.asyncio
async def test_the_api_exposes_the_vault_and_syncs_hand_edits(tmp_path: Path) -> None:
    """The sync endpoint exists because the interesting moment is right after
    somebody finishes editing, and waiting for a restart to be believed is not
    a memory system anybody trusts."""
    from fastapi.testclient import TestClient

    from jarvis.config import Settings
    from jarvis.main import create_app

    root = tmp_path / "vault"
    app = create_app(Settings(environment="test", enable_scheduler=False, obsidian_vault=str(root)))
    with TestClient(app) as client:
        client.post(
            "/v1/memory",
            json={"content": "Gross margin is 62%", "tags": ["project/Northbound"]},
        )

        status = client.get("/v1/vault").json()
        assert status["notes"] >= 1
        assert status["memories"] == 1
        assert status["primary"] is True

        note = root / "Projects" / "Northbound.md"
        note.write_text(note.read_text().replace("62%", "71%"))

        assert client.post("/v1/vault/sync").status_code == 200
        recalled = client.get("/v1/memory", params={"q": "margin"}).json()
        assert "71%" in recalled[0]["content"]

        assert client.get("/health").json()["obsidian"]["root"].endswith("vault")


@pytest.mark.asyncio
async def test_the_vault_endpoints_are_absent_without_a_vault() -> None:
    from fastapi.testclient import TestClient

    from jarvis.config import Settings
    from jarvis.main import create_app

    with TestClient(create_app(Settings(environment="test", enable_scheduler=False))) as client:
        assert client.get("/v1/vault").status_code == 404
        assert client.get("/health").json()["obsidian"] is None


@pytest.mark.asyncio
async def test_a_multi_line_memory_stays_one_block(store: ObsidianStore) -> None:
    """One memory is one Obsidian block, and a block reference anchors a line.

    The runtime's own conversation memory is two lines. Without flattening,
    the very first thing a vault ever stored would have put the anchor on the
    second line and orphaned the first — visible only as recall returning half
    a sentence.
    """
    memory = await store.remember("Asked: what is the margin\nAnswered: it is 62%")
    assert "\n" not in memory.content
    recalls = await store.search("margin")
    assert recalls[0].memory.content == memory.content


@pytest.mark.asyncio
async def test_a_completed_run_leaves_knowledge_in_the_vault(tmp_path: Path) -> None:
    """'Every completed task should leave behind useful knowledge inside the
    vault' — satisfied by the existing runtime path, with no extra hook.

    That is the payoff of implementing the port rather than bolting a vault on
    the side: the runtime has written a memory after every run since M1, and
    pointing memory at a vault is all it takes for those to become notes.
    """
    from jarvis.config import Settings
    from jarvis.kernel import container

    jarvis = container.build(
        Settings(environment="test", enable_scheduler=False, obsidian_vault=str(tmp_path / "vault"))
    )
    spec = jarvis.agents.get("financial_analyst")
    async for _ in jarvis.runtime.stream(spec, "What is our gross margin?"):
        pass

    notes = list((tmp_path / "vault").rglob("*.md"))
    assert notes, "a finished run must leave something behind"
    written = "\n".join(path.read_text() for path in notes)
    assert "gross margin" in written.lower()
    assert "run:" in written
    assert any("Journal" in path.parts for path in notes), "and it should be on the day"


@pytest.mark.asyncio
async def test_a_journal_pointer_is_not_a_second_memory(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """An episodic memory lands in two files, and exactly one of them is the
    memory. Counting the journal line too meant every decision was recalled
    twice, ranked twice and recommended twice — which is how the Chief of Staff
    came to report one lease renewal as two separate deadlines.
    """
    await store.remember(
        "Decided to drop the subscription tier",
        kind=MemoryKind.DECISION,
        tags=["project/Northbound"],
    )
    assert await store.count() == 1

    recalls = await store.search("subscription tier")
    assert len(recalls) == 1

    # The line is still in the journal for a human to read.
    assert "subscription tier" in (vault.root / "Journal" / "2026-07-29.md").read_text()


@pytest.mark.asyncio
async def test_a_journal_line_does_not_link_to_a_filing_detail(
    store: ObsidianStore, vault: VaultManager
) -> None:
    """An area note is named after a scope. "→ [[global]]" points at a filing
    detail the reader does not care about."""
    await store.remember("Something happened today", kind=MemoryKind.EVENT)
    journal = (vault.root / "Journal" / "2026-07-29.md").read_text()
    assert "[[global]]" not in journal
    assert "Something happened today" in journal
