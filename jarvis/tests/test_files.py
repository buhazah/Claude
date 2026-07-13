"""Tests for file upload/extraction, document export, and signed downloads."""
import re


def test_extract_text_formats():
    from server.files.extract import extract_text, is_image

    assert "Ada" in extract_text(b"name,age\nAda,36", "d.csv")
    assert '"a": 1' in extract_text(b'{"a":1}', "d.json")
    assert extract_text(b"hello world", "note.txt") == "hello world"
    assert is_image("p.PNG") and is_image("x.jpeg")
    assert not is_image("doc.pdf")


def test_extract_truncates_long_text():
    from server.files.extract import MAX_CHARS, extract_text

    big = ("x" * (MAX_CHARS + 500)).encode()
    out = extract_text(big, "big.txt")
    assert len(out) <= MAX_CHARS + 20 and out.endswith("(truncated)")


def test_upload_document_route(auth_client):
    r = auth_client.post(
        "/api/files/analyze",
        files={"file": ("plan.txt", b"Launch is on Friday.", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "document" and "Friday" in body["text"]


def test_upload_requires_auth(client):
    r = client.post("/api/files/analyze", files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 401


async def test_export_document_and_download(auth_client):
    from server.tools import doc_tools  # noqa: F401
    from server.tools.base import registry

    result = await registry.execute(
        "export_document", {"title": "Test Report", "content": "# Hi\n\n- one\n- two", "format": "pdf"}
    )
    assert result.ok
    url = re.search(r"\]\((/api/files/download/[^)]+)\)", result.output).group(1)
    # Valid signed link downloads the file.
    r = auth_client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    # Tampered token is rejected.
    bad = auth_client.get(url.split("?")[0] + "?t=nope.nope")
    assert bad.status_code == 403


def test_download_rejects_path_traversal(auth_client):
    from server.files.download import sign

    name = "../secret"
    r = auth_client.get(f"/api/files/download/{name}?t={sign(name)}")
    assert r.status_code in (400, 404)


def test_market_price_tool_registered():
    import server.tools.live_tools  # noqa: F401  (registers tools)
    from server.agents.definitions import LIVE_TOOLS
    from server.tools.base import registry

    assert registry.get("market_price") is not None
    assert "market_price" in LIVE_TOOLS


def test_response_length_directives_exist():
    from server.agents.orchestrator import _LENGTH_DIRECTIVES

    assert {"short", "medium", "long"} <= set(_LENGTH_DIRECTIVES)
    assert all(v.strip() for v in _LENGTH_DIRECTIVES.values())
