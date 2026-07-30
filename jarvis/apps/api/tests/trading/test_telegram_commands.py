from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.trading.database.store import InMemoryTradingStore
from jarvis.trading.models import (
    MarketCondition,
    MarketSnapshot,
    PerformanceMetrics,
    RiskLevel,
    Signal,
    SignalStatus,
    Strategy,
    StrategyLeg,
    StrategyType,
    Trend,
    UserRole,
)
from jarvis.trading.telegram_agent import commands

NOW = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)


@pytest.fixture
def store() -> InMemoryTradingStore:
    return InMemoryTradingStore()


def make_strategy() -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BULL_PUT_SPREAD,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=5450),
            StrategyLeg(action="buy", option_type="put", strike=5400),
        ],
        entry="Sell SPX 5450 Put / Buy SPX 5400 Put",
        expiration="2026-03-24",
        days_to_expiration=14,
        credit=1.2,
        max_profit=120.0,
        max_loss=380.0,
        probability_of_profit=74.0,
        risk_reward_ratio=0.32,
    )


def make_signal(*, status: SignalStatus = SignalStatus.ACTIVE) -> Signal:
    return Signal(
        timestamp=NOW,
        market_direction=Trend.BULLISH,
        strategy=make_strategy(),
        confidence=8,
        reasons=["Trend confirmation"],
        risk_level=RiskLevel.MEDIUM,
        message="rendered signal text",
        status=status,
    )


# ── /start ───────────────────────────────────────────────────────────────


async def test_start_registers_a_new_user(store: InMemoryTradingStore):
    reply = await commands.handle_start(
        store=store, telegram_id=111, username="trader1", is_admin=False, now=NOW
    )
    assert "Welcome" in reply
    user = await store.get_user_by_telegram_id(111)
    assert user is not None
    assert user.role == UserRole.SUBSCRIBER


async def test_start_grants_admin_role_when_configured_as_admin(store: InMemoryTradingStore):
    reply = await commands.handle_start(
        store=store, telegram_id=111, username="boss", is_admin=True, now=NOW
    )
    assert "/admin" in reply
    user = await store.get_user_by_telegram_id(111)
    assert user is not None
    assert user.role == UserRole.ADMIN


async def test_start_is_idempotent_for_a_returning_user(store: InMemoryTradingStore):
    await commands.handle_start(store=store, telegram_id=111, username="a", is_admin=False, now=NOW)
    await commands.handle_start(store=store, telegram_id=111, username="b", is_admin=False, now=NOW)
    users = await store.list_users()
    assert len(users) == 1
    assert users[0].username == "b"


# ── /signal ──────────────────────────────────────────────────────────────


async def test_signal_reports_no_active_signal(store: InMemoryTradingStore):
    reply = await commands.handle_signal(store=store)
    assert "No active signal" in reply


async def test_signal_returns_the_active_signal_message(store: InMemoryTradingStore):
    await store.save_signal(make_signal())
    reply = await commands.handle_signal(store=store)
    assert reply == "rendered signal text"


async def test_signal_ignores_closed_signals(store: InMemoryTradingStore):
    await store.save_signal(make_signal(status=SignalStatus.CLOSED))
    reply = await commands.handle_signal(store=store)
    assert "No active signal" in reply


# ── /market ──────────────────────────────────────────────────────────────


async def test_market_reports_no_data(store: InMemoryTradingStore):
    reply = await commands.handle_market(store=store)
    assert "No market data" in reply


async def test_market_summarises_the_latest_snapshot(store: InMemoryTradingStore):
    await store.save_market_snapshot(
        MarketSnapshot(
            timestamp=NOW,
            symbol="SPX",
            price=5500.0,
            vix=15.0,
            trend=Trend.BULLISH,
            market_condition=MarketCondition.TRENDING_UP,
        )
    )
    reply = await commands.handle_market(store=store)
    assert "5500.00" in reply
    assert "bullish" in reply


# ── /history ─────────────────────────────────────────────────────────────


async def test_history_reports_no_signals(store: InMemoryTradingStore):
    reply = await commands.handle_history(store=store)
    assert "No signals yet" in reply


async def test_history_lists_recent_signals(store: InMemoryTradingStore):
    await store.save_signal(make_signal())
    reply = await commands.handle_history(store=store)
    assert "bull_put_spread" in reply


# ── /performance ─────────────────────────────────────────────────────────


async def test_performance_reports_no_data(store: InMemoryTradingStore):
    reply = await commands.handle_performance(store=store)
    assert "No performance data" in reply


async def test_performance_summarises_the_latest_metrics(store: InMemoryTradingStore):
    await store.save_performance_metrics(
        PerformanceMetrics(
            total_signals=10,
            winning_signals=7,
            losing_signals=3,
            win_rate=70.0,
            average_return_pct=12.5,
            max_drawdown_pct=6.0,
            computed_at=NOW,
        )
    )
    reply = await commands.handle_performance(store=store)
    assert "70.0%" in reply
    assert "10" in reply


# ── /settings ────────────────────────────────────────────────────────────


async def test_settings_requires_registration_first(store: InMemoryTradingStore):
    reply = await commands.handle_settings(store=store, telegram_id=111, args="")
    assert "/start" in reply


async def test_settings_shows_current_preferences(store: InMemoryTradingStore):
    await commands.handle_start(store=store, telegram_id=111, username="a", is_admin=False, now=NOW)
    reply = await commands.handle_settings(store=store, telegram_id=111, args="")
    assert "Receive signals: on" in reply


async def test_settings_toggles_notifications_off(store: InMemoryTradingStore):
    await commands.handle_start(store=store, telegram_id=111, username="a", is_admin=False, now=NOW)
    reply = await commands.handle_settings(store=store, telegram_id=111, args="off")
    assert "turned off" in reply
    user = await store.get_user_by_telegram_id(111)
    assert user is not None
    assert user.settings.receive_signals is False


# ── /admin ───────────────────────────────────────────────────────────────


async def test_admin_refuses_non_admins(store: InMemoryTradingStore):
    reply = await commands.handle_admin(store=store, is_admin=False, args="")
    assert "not authorized" in reply


async def test_admin_stats_reports_counts(store: InMemoryTradingStore):
    await commands.handle_start(store=store, telegram_id=111, username="a", is_admin=True, now=NOW)
    await store.save_signal(make_signal())
    reply = await commands.handle_admin(store=store, is_admin=True, args="")
    assert "Users: 1" in reply
    assert "Signals stored: 1" in reply


async def test_admin_unknown_subcommand(store: InMemoryTradingStore):
    reply = await commands.handle_admin(store=store, is_admin=True, args="wipe-everything")
    assert "Unknown admin command" in reply
