"""Rendering a document to something a person can send.

Two targets, both self-contained. Markdown because it is what goes into a repo,
an issue, or another tool; HTML because it is what goes to someone who will not
open a `.md` file — and it prints, which is how a proposal actually gets read.

No `.docx` yet. Producing one honestly means a real OOXML writer, and a
half-working one that Word repairs on open is worse than an HTML file the
recipient can already read.
"""

from __future__ import annotations

from html import escape

from jarvis.documents.models import Document

# Deliberately plain: this stylesheet has to survive being pasted into an email
# client, printed, and read on a phone. Anything clever loses one of the three.
STYLE = """
:root { color-scheme: light dark; }
body {
  font: 16px/1.65 ui-serif, Georgia, "Times New Roman", serif;
  max-width: 44rem; margin: 3rem auto; padding: 0 1.5rem;
  color: #16181d; background: #fff;
}
h1 { font-size: 2rem; line-height: 1.2; margin: 0 0 .25rem; letter-spacing: -.02em; }
h2 { font-size: 1.25rem; margin: 2.5rem 0 .75rem; letter-spacing: -.01em; }
.meta { color: #6b7280; font: 13px/1.5 ui-sans-serif, system-ui, sans-serif;
        margin-bottom: 2.5rem; }
sup a { text-decoration: none; color: #2563eb; }
.sources { margin-top: 3.5rem; border-top: 1px solid #e5e7eb; padding-top: 1.25rem; }
.sources h2 { font-size: 1rem; margin-top: 0; }
.sources ol { font: 14px/1.6 ui-sans-serif, system-ui, sans-serif; color: #4b5563;
              padding-left: 1.25rem; }
.sources li { margin-bottom: .35rem; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e8ec; background: #0f1115; }
  .meta, .sources ol { color: #9aa1ad; }
  .sources { border-color: #262a33; }
  sup a { color: #7aa2f7; }
}
@media print { body { margin: 0; max-width: none; } .meta { color: #444; } }
"""


def _byline(document: Document) -> str:
    bits = [document.kind.value, f"{document.words} words"]
    if document.citations:
        bits.append(f"{len(document.citations)} sources")
    if document.mode != "personal":
        bits.append(f"{document.mode} mode")
    return " · ".join(bits)


def to_markdown(document: Document) -> str:
    lines = [f"# {document.title}", "", f"*{_byline(document)}*", ""]
    for section in document.sections:
        lines += [f"## {section.heading}", "", section.body.strip(), ""]

    if citations := document.citations:
        lines += ["---", "", "## Sources", ""]
        lines += [f"{i}. {c.reference}" for i, c in enumerate(citations, start=1)]
        lines.append("")
    return "\n".join(lines)


def to_html(document: Document) -> str:
    body = [
        f"<h1>{escape(document.title)}</h1>",
        f'<p class="meta">{escape(_byline(document))}</p>',
    ]
    for section in document.sections:
        body.append(f"<h2>{escape(section.heading)}</h2>")
        # Blank-line-separated blocks become paragraphs. Not a markdown
        # renderer — a document body is prose, and pulling in a parser to
        # handle emphasis nobody asked for is not worth the dependency.
        for block in section.body.strip().split("\n\n"):
            if block.strip():
                body.append(f"<p>{escape(block.strip())}</p>")

    if citations := document.citations:
        body.append('<section class="sources"><h2>Sources</h2><ol>')
        body += [f"<li>{escape(c.reference)}</li>" for c in citations]
        body.append("</ol></section>")

    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(document.title)}</title>\n<style>{STYLE}</style>\n"
        "</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )


RENDERERS = {"md": to_markdown, "html": to_html}
MEDIA_TYPES = {"md": "text/markdown; charset=utf-8", "html": "text/html; charset=utf-8"}
