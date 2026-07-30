"""The trading department wired through the real ASGI lifespan (main.py),
the way a production deployment actually turns it on: TRADING_ENABLED."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.providers.echo import EchoProvider
from jarvis.main import create_app
from jarvis.trading.config import get_trading_settings


@pytest.fixture(autouse=True)
def _reset_trading_settings_cache():
    # get_trading_settings() is process-cached; env changes below must be
    # visible to the next call, and must not leak into other test modules.
    get_trading_settings.cache_clear()
    yield
    get_trading_settings.cache_clear()


def build_client(settings: Settings) -> TestClient:
    system = container.build(settings, providers=[EchoProvider()], clock=FrozenClock())
    return TestClient(create_app(settings, jarvis=system))


def test_trading_disabled_by_default_registers_no_tools(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TRADING_ENABLED", raising=False)
    settings = Settings(environment="test", enable_scheduler=False, use_llm_arbiter=False)
    with build_client(settings) as client:
        system = client.app.state.jarvis
        assert "trading_collect_market_data" not in {t.name for t in system.tools.all()}


def test_trading_enabled_registers_tools_and_workflows(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRADING_ENABLED", "true")
    settings = Settings(environment="test", enable_scheduler=False, use_llm_arbiter=False)
    with build_client(settings) as client:
        system = client.app.state.jarvis
        tool_names = {t.name for t in system.tools.all()}
        assert "trading_collect_market_data" in tool_names
        assert "trading_generate_signal" in tool_names


def test_trading_enabled_without_a_bot_token_starts_no_polling_task(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.delenv("TRADING_TELEGRAM_BOT_TOKEN", raising=False)
    settings = Settings(environment="test", enable_scheduler=False, use_llm_arbiter=False)
    # Startup and shutdown must both complete without attempting any network
    # call — this only holds if no polling task was ever created.
    with build_client(settings):
        pass
