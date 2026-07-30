"""Store contract tests: the in-memory and SQL trading stores must behave
identically to anything built against :class:`TradingStore`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.persistence.db import Database
from jarvis.trading.database.store import InMemoryTradingStore, SqlTradingStore, TradingStore
from jarvis.trading.models import (
    MarketCondition,
    MarketSnapshot,
    OptionsAnalysis,
    OptionsSnapshot,
    PerformanceMetrics,
    RiskLevel,
    Signal,
    SignalStatus,
    Strategy,
    StrategyLeg,
    StrategyType,
    TradeOutcome,
    TradeResult,
    Trend,
    User,
    UserRole,
    VolatilityState,
)

BACKENDS = ["memory", "sqlite"]


@pytest.fixture(params=BACKENDS)
async def store(request: pytest.FixtureRequest, tmp_path) -> AsyncIterator[TradingStore]:
    if request.param == "memory":
        yield InMemoryTradingStore()
        return
    db = Database(f"sqlite+aiosqlite:///{tmp_path}/trading.db")
    await db.create_all()
    try:
        yield SqlTradingStore(db)
    finally:
        await db.dispose()


def make_market(*, timestamp: datetime, events: list[str] | None = None) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=timestamp,
        symbol="SPX",
        price=5500.0,
        volume=1_800_000_000,
        vix=15.0,
        trend=Trend.BULLISH,
        market_condition=MarketCondition.TRENDING_UP,
        economic_events=events or [],
    )


def make_options_analysis() -> OptionsAnalysis:
    return OptionsAnalysis(
        volatility_state=VolatilityState.NORMAL,
        best_expiration="2026-03-24",
        important_strikes=[],
        market_positioning="balanced put/call positioning",
        risk_level=RiskLevel.MEDIUM,
        iv=0.15,
        iv_rank=45.0,
        put_call_ratio=0.9,
        expected_move=120.0,
        expected_move_pct=2.2,
    )


def make_signal(*, timestamp: datetime, result: TradeOutcome | None = None) -> Signal:
    strategy = Strategy(
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
    return Signal(
        timestamp=timestamp,
        market_direction=Trend.BULLISH,
        strategy=strategy,
        confidence=8,
        reasons=["Trend confirmation"],
        risk_level=RiskLevel.MEDIUM,
        message="rendered",
        result=result,
        status=SignalStatus.CLOSED if result else SignalStatus.ACTIVE,
    )


async def test_market_snapshot_round_trips(store: TradingStore):
    snapshot = make_market(timestamp=datetime(2026, 3, 10, tzinfo=UTC))
    await store.save_market_snapshot(snapshot)  # does not raise


async def test_latest_market_snapshot_returns_none_when_empty(store: TradingStore):
    assert await store.latest_market_snapshot() is None


async def test_latest_market_snapshot_returns_the_most_recent(store: TradingStore):
    await store.save_market_snapshot(
        make_market(timestamp=datetime(2026, 3, 10, 10, 0, tzinfo=UTC))
    )
    latest = make_market(timestamp=datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    await store.save_market_snapshot(latest)
    fetched = await store.latest_market_snapshot()
    assert fetched is not None
    assert fetched.timestamp == latest.timestamp


async def test_options_snapshot_round_trips(store: TradingStore):
    snapshot = OptionsSnapshot(
        timestamp=datetime(2026, 3, 10, tzinfo=UTC),
        underlying="SPX",
        analysis=make_options_analysis(),
    )
    await store.save_options_snapshot(snapshot)  # does not raise


async def test_signal_saved_and_fetched_by_id(store: TradingStore):
    signal = make_signal(timestamp=datetime(2026, 3, 10, tzinfo=UTC))
    await store.save_signal(signal)
    fetched = await store.get_signal(signal.id)
    assert fetched is not None
    assert fetched.id == signal.id
    assert fetched.strategy.strategy_type == StrategyType.BULL_PUT_SPREAD


async def test_get_signal_returns_none_for_unknown_id(store: TradingStore):
    assert await store.get_signal("sig_does_not_exist") is None


async def test_list_signals_returns_newest_first(store: TradingStore):
    older = make_signal(timestamp=datetime(2026, 3, 10, 10, 0, tzinfo=UTC))
    newer = make_signal(timestamp=datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    await store.save_signal(older)
    await store.save_signal(newer)
    listed = await store.list_signals(limit=10)
    assert listed[0].id == newer.id


async def test_list_signals_filters_by_status(store: TradingStore):
    active = make_signal(timestamp=datetime(2026, 3, 10, tzinfo=UTC))
    closed = make_signal(timestamp=datetime(2026, 3, 10, tzinfo=UTC), result=TradeOutcome.WIN)
    await store.save_signal(active)
    await store.save_signal(closed)
    listed = await store.list_signals(status=SignalStatus.ACTIVE)
    assert {s.id for s in listed} == {active.id}


async def test_update_signal_status_persists(store: TradingStore):
    signal = make_signal(timestamp=datetime(2026, 3, 10, tzinfo=UTC))
    await store.save_signal(signal)
    await store.update_signal_status(
        signal.id, status=SignalStatus.TARGET_HIT, result=TradeOutcome.WIN
    )
    fetched = await store.get_signal(signal.id)
    assert fetched is not None
    assert fetched.status == SignalStatus.TARGET_HIT
    assert fetched.result == TradeOutcome.WIN


async def test_update_signal_status_on_unknown_id_is_a_noop(store: TradingStore):
    await store.update_signal_status("sig_missing", status=SignalStatus.CLOSED)


async def test_signals_today_counts_only_todays_signals(store: TradingStore):
    today = datetime(2026, 3, 10, 15, 0, tzinfo=UTC)
    yesterday = today - timedelta(days=1)
    await store.save_signal(make_signal(timestamp=today))
    await store.save_signal(make_signal(timestamp=today))
    await store.save_signal(make_signal(timestamp=yesterday))
    assert await store.signals_today(now=today) == 2


async def test_consecutive_losses_counts_from_most_recent(store: TradingStore):
    base = datetime(2026, 3, 10, tzinfo=UTC)
    await store.save_signal(make_signal(timestamp=base, result=TradeOutcome.WIN))
    await store.save_signal(
        make_signal(timestamp=base + timedelta(hours=1), result=TradeOutcome.LOSS)
    )
    await store.save_signal(
        make_signal(timestamp=base + timedelta(hours=2), result=TradeOutcome.LOSS)
    )
    assert await store.consecutive_losses() == 2


async def test_consecutive_losses_resets_after_most_recent_win(store: TradingStore):
    base = datetime(2026, 3, 10, tzinfo=UTC)
    await store.save_signal(make_signal(timestamp=base, result=TradeOutcome.LOSS))
    await store.save_signal(
        make_signal(timestamp=base + timedelta(hours=1), result=TradeOutcome.WIN)
    )
    assert await store.consecutive_losses() == 0


async def test_consecutive_losses_ignores_signals_without_a_result_yet(store: TradingStore):
    base = datetime(2026, 3, 10, tzinfo=UTC)
    await store.save_signal(make_signal(timestamp=base, result=TradeOutcome.LOSS))
    await store.save_signal(make_signal(timestamp=base + timedelta(hours=1)))  # still active
    assert await store.consecutive_losses() == 1


async def test_trade_results_round_trip_newest_first(store: TradingStore):
    first = TradeResult(
        signal_id="sig_1",
        outcome=TradeOutcome.WIN,
        pnl_usd=120.0,
        pnl_pct=31.5,
        closed_at=datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
    )
    second = TradeResult(
        signal_id="sig_2",
        outcome=TradeOutcome.LOSS,
        pnl_usd=-380.0,
        pnl_pct=-100.0,
        closed_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
    )
    await store.save_trade_result(first)
    await store.save_trade_result(second)
    results = await store.list_trade_results()
    assert results[0].signal_id == "sig_2"
    assert len(results) == 2


async def test_performance_metrics_latest_returns_most_recent(store: TradingStore):
    older = PerformanceMetrics(
        total_signals=5,
        winning_signals=3,
        losing_signals=2,
        win_rate=60.0,
        average_return_pct=10.0,
        max_drawdown_pct=5.0,
        computed_at=datetime(2026, 3, 9, tzinfo=UTC),
    )
    newer = PerformanceMetrics(
        total_signals=8,
        winning_signals=6,
        losing_signals=2,
        win_rate=75.0,
        average_return_pct=15.0,
        max_drawdown_pct=4.0,
        computed_at=datetime(2026, 3, 10, tzinfo=UTC),
    )
    await store.save_performance_metrics(older)
    await store.save_performance_metrics(newer)
    latest = await store.latest_performance_metrics()
    assert latest is not None
    assert latest.total_signals == 8


async def test_latest_performance_metrics_is_none_when_empty(store: TradingStore):
    assert await store.latest_performance_metrics() is None


async def test_upsert_user_creates_then_updates(store: TradingStore):
    created = await store.upsert_user(
        User(telegram_id=111, username="trader1", created_at=datetime(2026, 3, 10, tzinfo=UTC))
    )
    updated = await store.upsert_user(
        User(
            telegram_id=111,
            username="trader1_renamed",
            role=UserRole.ADMIN,
            created_at=datetime(2026, 3, 10, tzinfo=UTC),
        )
    )
    fetched = await store.get_user_by_telegram_id(111)
    assert fetched is not None
    assert fetched.username == "trader1_renamed"
    assert fetched.role == UserRole.ADMIN
    assert updated.id == created.id  # the same logical user, not a duplicate


async def test_get_user_by_telegram_id_returns_none_when_unknown(store: TradingStore):
    assert await store.get_user_by_telegram_id(999) is None


async def test_list_users_filters_by_role(store: TradingStore):
    await store.upsert_user(
        User(telegram_id=1, role=UserRole.SUBSCRIBER, created_at=datetime(2026, 3, 10, tzinfo=UTC))
    )
    await store.upsert_user(
        User(telegram_id=2, role=UserRole.ADMIN, created_at=datetime(2026, 3, 10, tzinfo=UTC))
    )
    admins = await store.list_users(role=UserRole.ADMIN)
    assert {u.telegram_id for u in admins} == {2}
