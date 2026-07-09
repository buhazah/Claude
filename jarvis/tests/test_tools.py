"""Tests for the tool framework: validation, sandboxing, and execution."""
import pytest

from server.tools import core_tools  # noqa: F401 - registers tools
from server.tools.base import registry
from server.tools.core_tools import _safe_path


async def test_tool_registered():
    assert "fs_write" in registry.names()
    assert "web_search" in registry.names()


async def test_arg_validation_missing_required():
    result = await registry.execute("fs_write", {"path": "x.txt"})  # missing content
    assert not result.ok
    assert "content" in result.error


async def test_arg_validation_wrong_type():
    result = await registry.execute("fs_write", {"path": "x.txt", "content": 123})
    assert not result.ok
    assert "type" in result.error


async def test_arg_validation_unknown_param():
    result = await registry.execute("fs_read", {"path": "x", "bogus": 1})
    assert not result.ok
    assert "unknown" in result.error


async def test_sandbox_blocks_traversal():
    with pytest.raises(ValueError):
        _safe_path("../../etc/passwd")


async def test_fs_write_read_roundtrip():
    w = await registry.execute("fs_write", {"path": "note.txt", "content": "hello jarvis"})
    assert w.ok, w.error
    r = await registry.execute("fs_read", {"path": "note.txt"})
    assert r.ok
    assert "hello jarvis" in r.output


async def test_python_exec_runs():
    r = await registry.execute("python_exec", {"code": "print(2 + 2)"})
    assert r.ok
    assert "4" in r.output


async def test_unknown_tool():
    r = await registry.execute("does_not_exist", {})
    assert not r.ok
    assert "unknown tool" in r.error


async def test_generate_document_json_validation():
    bad = await registry.execute("generate_document", {"filename": "d.json", "content": "{bad", "format": "json"})
    assert not bad.ok or "Invalid JSON" in bad.output
