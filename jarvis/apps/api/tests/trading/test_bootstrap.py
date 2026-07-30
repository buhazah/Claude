from __future__ import annotations

import pytest

from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.providers.echo import EchoProvider
from jarvis.trading.bootstrap import install_trading
from jarvis.trading.config import TradingSettings
from jarvis.trading.database.store import InMemoryTradingStore, SqlTradingStore
from jarvis.trading.workflows import (
    DAILY_REPORT_WORKFLOW_ID,
    MARKET_SCAN_WORKFLOW_ID,
    SIGNAL_MONITORING_WORKFLOW_ID,
)


@pytest.fixture
def jarvis(tmp_path):
    settings = Settings(
        environment="test",
        use_llm_arbiter=False,
        log_level="WARNING",
        enable_scheduler=False,
        realtime_speech=False,
        workspace_dir=str(tmp_path),
    )
    return container.build(settings, providers=[EchoProvider()], clock=FrozenClock())


async def test_install_trading_is_a_noop_when_disabled(jarvis):
    department = await install_trading(jarvis, TradingSettings(enabled=False))
    assert department is None
    assert "trading_collect_market_data" not in {t.name for t in jarvis.tools.all()}


async def test_install_trading_registers_every_tool(jarvis):
    department = await install_trading(jarvis, TradingSettings(enabled=True))
    assert department is not None
    tool_names = {t.name for t in jarvis.tools.all()}
    assert {
        "trading_collect_market_data",
        "trading_generate_signal",
        "trading_daily_report",
        "trading_monitor_signals",
        "trading_compute_performance",
    } <= tool_names


async def test_install_trading_saves_every_workflow_and_trigger(jarvis):
    await install_trading(jarvis, TradingSettings(enabled=True))
    workflow_ids = {w.id for w in await jarvis.workflows.all()}
    assert {MARKET_SCAN_WORKFLOW_ID, DAILY_REPORT_WORKFLOW_ID, SIGNAL_MONITORING_WORKFLOW_ID} <= (
        workflow_ids
    )
    trigger_workflow_ids = {t.workflow_id for t in await jarvis.workflows.triggers()}
    assert {MARKET_SCAN_WORKFLOW_ID, DAILY_REPORT_WORKFLOW_ID, SIGNAL_MONITORING_WORKFLOW_ID} <= (
        trigger_workflow_ids
    )


async def test_install_trading_uses_in_memory_store_without_a_database(jarvis):
    department = await install_trading(jarvis, TradingSettings(enabled=True))
    assert department is not None
    assert isinstance(department.store, InMemoryTradingStore)


async def test_install_trading_uses_sql_store_when_a_database_is_configured(tmp_path):
    settings = Settings(
        environment="test",
        use_llm_arbiter=False,
        log_level="WARNING",
        enable_scheduler=False,
        realtime_speech=False,
        workspace_dir=str(tmp_path),
        database_url=f"sqlite+aiosqlite:///{tmp_path}/jarvis.db",
    )
    jarvis_with_db = container.build(settings, providers=[EchoProvider()], clock=FrozenClock())
    await jarvis_with_db.start()
    try:
        department = await install_trading(jarvis_with_db, TradingSettings(enabled=True))
        assert department is not None
        assert isinstance(department.store, SqlTradingStore)
    finally:
        await jarvis_with_db.stop()


async def test_install_trading_has_no_telegram_bot_without_a_token(jarvis):
    department = await install_trading(jarvis, TradingSettings(enabled=True, telegram_bot_token=""))
    assert department is not None
    assert department.telegram_bot is None


async def test_install_trading_builds_a_telegram_bot_with_a_token(jarvis):
    department = await install_trading(
        jarvis, TradingSettings(enabled=True, telegram_bot_token="test-token")
    )
    assert department is not None
    assert department.telegram_bot is not None


async def test_tools_are_actually_invocable_through_the_registry(jarvis):
    await install_trading(jarvis, TradingSettings(enabled=True))
    result = await jarvis.tools.invoke("trading_collect_market_data", {})
    assert result["price"] > 0
