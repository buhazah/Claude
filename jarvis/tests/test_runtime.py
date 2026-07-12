"""Tests for agent tool-call parsing and answer sanitization."""
from server.agents.runtime import _clean_final, _extract_action


def test_extract_fenced_json_action():
    obj = _extract_action('thinking… ```json\n{"tool": "weather", "args": {"location": "Dubai"}}\n```')
    assert obj == {"tool": "weather", "args": {"location": "Dubai"}}


def test_extract_final_action():
    obj = _extract_action('done ```json\n{"final": "All set."}\n```')
    assert obj == {"final": "All set."}


def test_extract_function_calls_wrapper():
    # Some models wrap the call in <function_calls> tags instead of a fence.
    text = 'Let me check <function_calls> [{"tool": "weather", "args": {"location": "Abu Dhabi"}}] </function_calls>'
    obj = _extract_action(text)
    assert obj == {"tool": "weather", "args": {"location": "Abu Dhabi"}}


def test_clean_final_strips_leaked_tool_syntax():
    leak = 'Weather now <function_calls> [{"tool": "weather", "args": {"location": "X"}}] </function_calls> is hot.'
    cleaned = _clean_final(leak)
    assert "function_calls" not in cleaned
    assert "tool" not in cleaned
    assert "Weather now" in cleaned and "is hot." in cleaned


def test_clean_final_leaves_normal_text():
    assert _clean_final("The weather in Dubai is 38°C and sunny.") == "The weather in Dubai is 38°C and sunny."
