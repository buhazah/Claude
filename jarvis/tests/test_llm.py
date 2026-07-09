"""Tests for the model router scoring and provider request shaping."""
from server.llm.base import ModelSpec
from server.llm.providers import AnthropicProvider
from server.llm.router import ModelRouter, RouteProfile


def test_anthropic_omits_temperature_for_claude5():
    p = AnthropicProvider("key")
    # Claude 5 family + Opus 4.8 reject the temperature parameter.
    assert not p._accepts_temperature("claude-fable-5")
    assert not p._accepts_temperature("claude-sonnet-5")
    assert not p._accepts_temperature("claude-opus-4-8")
    # Older models still accept it.
    assert p._accepts_temperature("claude-haiku-4-5-20251001")
    assert p._accepts_temperature("gpt-4o")


def test_router_prefers_cheaper_model_for_simple_cost_sensitive_task():
    router = ModelRouter()
    router.providers = {"anthropic": AnthropicProvider("key")}
    ranked = router.candidates(RouteProfile(complexity=2, cost_sensitive=True, min_context=1000))
    assert ranked, "expected at least one candidate"
    # A trivial cost-sensitive task should not pick the most expensive frontier model.
    assert ranked[0].cost_in_per_mtok <= 5.0


def test_router_respects_context_window():
    router = ModelRouter()
    router.providers = {"google": type("P", (), {})()}
    # Only Google models with huge context should survive a 500k-token need.
    ranked = router.candidates(RouteProfile(complexity=3, min_context=500_000))
    assert all(s.context_window >= 500_000 for s in ranked)


def test_estimate_cost():
    router = ModelRouter()
    spec = ModelSpec("x", "m", 1000, 10.0, 30.0, 5, 5)
    # 1M in + 1M out = $10 + $30
    assert abs(router.estimate_cost(spec, 1_000_000, 1_000_000) - 40.0) < 1e-6
