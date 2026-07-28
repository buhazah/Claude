"""Composing a document.

**Plan, then write.** A long document produced in one pass drifts: by section
four the model has forgotten what section two claimed, and the whole thing
argues with itself. So an outline is produced first and each section is written
against it. The outline is cheap, inspectable, and the thing to fix when the
document is wrong in shape rather than in detail.

**Each section is retrieved for separately.** The passages that matter for
"Market position" are not the ones that matter for "Regulatory risk". Searching
once for the whole request and stuffing everything into every section wastes
context and produces sections that cite sources they never used.

**Citations are captured at write time, not reconstructed after.** Asking a
model afterwards which sources it used produces a plausible answer, not a true
one. The section's citations are the passages it was handed — which is a claim
about provenance we can actually make.

The honest limit, stated here because it belongs in the code and not only in a
release note: passing a section the right passages makes its claims
*attributable*, not *correct*. Nothing here verifies that a sentence is
supported by the passage next to it. That is a research problem, and pretending
otherwise with a green checkmark would be worse than saying so.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

import structlog

from jarvis.agents.registry import AgentRegistry
from jarvis.agents.runtime import AgentRuntime
from jarvis.documents.models import Citation, Document, DocumentKind, DocumentState, Section
from jarvis.kernel.bus import EventBus
from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.knowledge.store import KnowledgeStore
from jarvis.llm.base import CompletionRequest, Message, Role, RoutingPolicy
from jarvis.llm.router import ModelRouter

log = structlog.get_logger(__name__)

MAX_SECTIONS = 8
PASSAGES_PER_SECTION = 4
MIN_SECTIONS = 2

OUTLINE_PROMPT = (
    "You plan documents. Given a request, return the outline as JSON only — no "
    "prose, no code fence:\n"
    '{"title": "...", "sections": [{"heading": "...", "intent": "what this section '
    'must establish, one sentence"}]}\n'
    f"Between {MIN_SECTIONS} and {MAX_SECTIONS} sections. Each heading must earn its "
    "place: no 'Introduction' that restates the title, no 'Conclusion' that repeats "
    "the body. Order them as an argument, not as a list of topics."
)

SECTION_PROMPT = (
    "You are writing one section of a larger document. Write only this section's "
    "prose — no heading, no preamble, no meta-commentary about what you are doing.\n\n"
    "Where source passages are provided, ground your claims in them and cite inline "
    "as [1], [2] matching the numbering given. Do not cite a passage you did not "
    "use. Where no passage supports a claim, either drop the claim or mark it "
    "explicitly as inference."
)


@dataclass(slots=True)
class Outline:
    title: str
    sections: list[tuple[str, str]]  # (heading, intent)


def parse_outline(text: str, *, fallback_title: str) -> Outline:
    """Read the planner's JSON, tolerating the ways models wrap it.

    A malformed outline degrades to a single section rather than failing the
    document: the user asked for a document, and one badly-structured document
    beats an error message.
    """
    body = text.strip()
    if fence := re.search(r"```(?:json)?\s*(.+?)```", body, re.S):
        body = fence.group(1).strip()
    if (start := body.find("{")) != -1 and (end := body.rfind("}")) != -1:
        body = body[start : end + 1]

    try:
        parsed = json.loads(body)
        sections = [
            (str(s["heading"]).strip(), str(s.get("intent", "")).strip())
            for s in parsed["sections"]
            if str(s.get("heading", "")).strip()
        ][:MAX_SECTIONS]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("outline_unparsed", error=str(exc), reply=text[:160])
        return Outline(fallback_title, [(fallback_title, "")])

    if not sections:
        return Outline(fallback_title, [(fallback_title, "")])
    return Outline(str(parsed.get("title") or fallback_title).strip(), sections)


class DocumentComposer:
    """Turns a request into a structured, cited document."""

    def __init__(
        self,
        *,
        router: ModelRouter,
        runtime: AgentRuntime,
        agents: AgentRegistry,
        knowledge: KnowledgeStore,
        bus: EventBus,
        clock: Clock = SYSTEM_CLOCK,
    ) -> None:
        self._router = router
        self._runtime = runtime
        self._agents = agents
        self._knowledge = knowledge
        self._bus = bus
        self._clock = clock

    async def _outline(self, request: str, kind: DocumentKind) -> Outline:
        prompt = f"Document kind: {kind.value}\nRequest: {request}\n\nOutline:"
        try:
            completion = await self._router.complete(
                CompletionRequest(
                    messages=[Message(role=Role.USER, content=prompt)],
                    system=OUTLINE_PROMPT,
                    policy=RoutingPolicy.BALANCED,
                    max_output_tokens=700,
                    temperature=0.2,
                )
            )
        except Exception as exc:
            log.warning("outline_failed", error=str(exc))
            return Outline(request[:80], [(request[:80], "")])
        return parse_outline(completion.text, fallback_title=request[:80])

    async def _passages(self, query: str, scope: str | None) -> list[Citation]:
        hits = await self._knowledge.search(query, limit=PASSAGES_PER_SECTION, scope=scope)
        return [
            Citation(
                document_id=h.document_id,
                document_title=h.document_title,
                locator=h.locator,
                reference=h.reference(),
                snippet=h.snippet[:400],
            )
            for h in hits
        ]

    @staticmethod
    def _ground(citations: list[Citation]) -> str:
        if not citations:
            return (
                "No source passages were found for this section. Write from the "
                "request alone and say plainly that it is unsourced."
            )
        lines = [
            f"[{index}] {c.reference}\n{c.snippet}" for index, c in enumerate(citations, start=1)
        ]
        return "Source passages:\n\n" + "\n\n".join(lines)

    async def compose(
        self,
        request: str,
        *,
        kind: DocumentKind = DocumentKind.REPORT,
        mode: str = "personal",
        scope: str | None = None,
        agent_id: str = "research",
    ) -> AsyncIterator[tuple[str, Document, str]]:
        """Compose a document, yielding ``(event, document, text)`` as it goes.

        Streams rather than returning, because a document takes long enough
        that a progress bar would be a lie about what is happening — the user
        should see the outline land, then each section fill in.
        """
        document = Document(
            title=request[:120], kind=kind, request=request, mode=mode, created_at=self._clock.now()
        )
        self._bus.publish("document.started", {"id": document.id, "request": request[:160]})

        outline = await self._outline(request, kind)
        document.title = outline.title
        document.sections = [Section(heading=h, intent=i) for h, i in outline.sections]
        document.state = DocumentState.WRITING
        yield ("outline", document, "")
        self._bus.publish(
            "document.outlined",
            {"id": document.id, "title": document.title, "sections": len(document.sections)},
        )

        spec = self._agents.get(agent_id) if agent_id in self._agents else self._agents.all()[0]
        written: list[str] = []

        for section in document.sections:
            # Retrieved per section: the passages that matter for one heading
            # are rarely the ones that matter for the next.
            section.citations = await self._passages(
                f"{document.title} — {section.heading}. {section.intent}", scope
            )

            brief = "\n\n".join(
                [
                    f"Document: {document.title} ({kind.value})",
                    f"Original request: {request}",
                    "Sections already written:\n"
                    + ("\n".join(f"- {w}" for w in written) or "- (this is the first)"),
                    f"Write this section: {section.heading}\nIt must: {section.intent}",
                    self._ground(section.citations),
                ]
            )

            parts: list[str] = []
            async for delta in self._runtime.stream(
                spec,
                brief,
                remember=False,
                system_override=SECTION_PROMPT,
            ):
                if delta.type == "token":
                    parts.append(delta.text)
                    yield ("token", document, delta.text)
                elif delta.type == "done":
                    # A delta's payload is loosely typed by design — narrow it
                    # here rather than trusting it, so a provider that reports
                    # nothing costs nothing instead of raising mid-document.
                    usage = delta.data or {}
                    cost, used = usage.get("cost_usd"), usage.get("tokens")
                    document.cost_usd += cost if isinstance(cost, int | float) else 0.0
                    document.tokens += used if isinstance(used, int) else 0
                elif delta.type == "error":
                    document.state = DocumentState.FAILED
                    document.error = delta.text
                    yield ("error", document, delta.text)
                    return

            section.body = "".join(parts).strip()
            # Only cite what was actually referenced. Handing a section four
            # passages and listing all four regardless would make the
            # bibliography a claim nobody checked.
            section.citations = [
                c
                for index, c in enumerate(section.citations, start=1)
                if f"[{index}]" in section.body
            ]
            written.append(section.heading)
            yield ("section", document, section.heading)
            self._bus.publish(
                "document.section",
                {"id": document.id, "heading": section.heading, "words": section.words},
            )

        document.state = DocumentState.COMPLETE
        self._bus.publish(
            "document.finished",
            {
                "id": document.id,
                "title": document.title,
                "words": document.words,
                "citations": len(document.citations),
            },
        )
        yield ("done", document, "")
