"""Tests for the fast-routing heuristic that skips the planner on simple messages."""
from server.agents.orchestrator import _fast_route, _looks_simple


def test_simple_messages_skip_planner():
    assert _looks_simple("hi")
    assert _looks_simple("what's the weather in Dubai?")
    assert _looks_simple("remind me to call mom")
    assert _looks_simple("what's Bitcoin at right now?")


def test_compound_or_long_requests_still_plan():
    assert not _looks_simple("Research our competitors and then draft a positioning memo.")
    assert not _looks_simple("First set up the repo. Then write tests. After that deploy it.")
    assert not _looks_simple("x" * 400)
    # Several distinct sentences => several intents.
    assert not _looks_simple("Summarize this. Translate it. Email it to my team. Then archive it.")


def test_fast_route_picks_specialists_else_assistant():
    assert _fast_route("help me debug this python traceback") == "coding"
    assert _fast_route("review this NDA clause for liability") == "legal"
    assert _fast_route("model our runway and cash flow") == "finance"
    assert _fast_route("write a blog post about focus") == "writing"
    assert _fast_route("what's the weather tomorrow?") == "assistant"
    assert _fast_route("good morning") == "assistant"
