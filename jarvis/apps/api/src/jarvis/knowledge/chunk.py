"""Chunking.

Two rules drive every decision here:

1. **Never split a block across chunks silently.** Blocks are already the
   document's own units — a page, a slide, a section. Packing several small
   ones together is fine; tearing one in half loses the thread mid-sentence.
   Oversized blocks *are* split, but on paragraph then sentence boundaries, and
   the locator gains a part number so the citation stays honest.
2. **A chunk's locator must describe everything in it.** Pack pages 3 and 4
   together and the locator is "pp. 3–4", not "p. 3". A citation that points at
   only part of what was retrieved is worse than a vague one, because it looks
   precise.
"""

from __future__ import annotations

import re

from jarvis.knowledge.models import Block, Chunk

# Roughly 1000 tokens at ~4 chars/token, with a little overlap so a fact that
# lands near a boundary is still retrievable from either side.
TARGET_CHARS = 4000
OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 60

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _combine_locators(locators: list[str]) -> str:
    """Describe a span of blocks in one locator."""
    unique = [loc for i, loc in enumerate(locators) if loc and loc not in locators[:i]]
    if not unique:
        return ""
    if len(unique) == 1:
        return unique[0]

    # "p. 3" + "p. 4" → "pp. 3–4"; anything less regular gets an honest join.
    pages = [re.match(r"^p\. (\d+)$", loc) for loc in unique]
    if all(pages):
        numbers = [int(m.group(1)) for m in pages if m]
        return f"pp. {numbers[0]}–{numbers[-1]}"

    slides = [re.match(r"^slide (\d+)$", loc) for loc in unique]
    if all(slides):
        numbers = [int(m.group(1)) for m in slides if m]
        return f"slides {numbers[0]}–{numbers[-1]}"

    return "; ".join(unique[:3]) + ("; …" if len(unique) > 3 else "")


def _split_oversized(block: Block) -> list[Block]:
    """Break a block that cannot fit, on the largest boundary that works."""
    if len(block.text) <= TARGET_CHARS:
        return [block]

    pieces: list[str] = []
    buffer = ""
    # Paragraphs first, sentences within a paragraph that is still too big.
    units = re.split(r"\n\s*\n", block.text)
    for unit in units:
        candidates = [unit] if len(unit) <= TARGET_CHARS else _SENTENCE_RE.split(unit)
        for candidate in candidates:
            if len(buffer) + len(candidate) + 2 > TARGET_CHARS and buffer:
                pieces.append(buffer.strip())
                buffer = candidate
            else:
                buffer = f"{buffer}\n\n{candidate}" if buffer else candidate
    if buffer.strip():
        pieces.append(buffer.strip())

    if len(pieces) <= 1:
        return [block]
    return [
        Block(
            text=piece,
            # The locator says which part, so a citation is never broader than
            # what was actually retrieved.
            locator=f"{block.locator} (part {index + 1}/{len(pieces)})" if block.locator else "",
            order=block.order,
        )
        for index, piece in enumerate(pieces)
    ]


def chunk_blocks(blocks: list[Block], *, document_id: str = "") -> list[Chunk]:
    """Pack located blocks into retrievable chunks."""
    expanded: list[Block] = []
    for block in blocks:
        expanded.extend(_split_oversized(block))

    chunks: list[Chunk] = []
    buffer: list[str] = []
    locators: list[str] = []

    def flush() -> None:
        body = "\n\n".join(buffer).strip()
        if len(body) >= MIN_CHUNK_CHARS or (body and not chunks):
            chunks.append(
                Chunk(
                    document_id=document_id,
                    content=body,
                    locator=_combine_locators(locators),
                    position=len(chunks),
                    tokens=estimate_tokens(body),
                )
            )
        elif body and chunks:
            # A tail too small to stand alone belongs with its neighbour rather
            # than as a fragment nothing will ever match.
            previous = chunks[-1]
            previous.content = f"{previous.content}\n\n{body}"
            previous.locator = _combine_locators([previous.locator, *locators])
            previous.tokens = estimate_tokens(previous.content)
        buffer.clear()
        locators.clear()

    for block in expanded:
        text = block.text.strip()
        if not text:
            continue
        projected = sum(len(b) for b in buffer) + len(text) + 2
        if buffer and projected > TARGET_CHARS:
            tail = buffer[-1][-OVERLAP_CHARS:] if OVERLAP_CHARS else ""
            carried = locators[-1] if locators else ""
            flush()
            if tail.strip():
                buffer.append(tail.strip())
                locators.append(carried)
        buffer.append(text)
        locators.append(block.locator)

    flush()
    return chunks
