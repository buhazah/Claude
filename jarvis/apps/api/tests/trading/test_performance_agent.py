from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.kernel.clock import FrozenClock
from jarvis.trading.database.store import InMemoryTradingStore
from jarvis.trading.models import (
    RiskLevel,
    Signal,
    Strategy,
    StrategyLeg,
    StrategyType,
    TradeOutcome,
    TradeResult,
    Trend,
)
from jarvis.trading.performance_agent.agent import PerformanceAgent

NOW = datetime(2026, 3, 10, tzinfo=UTC)


@pytest.fixture
def store() -> InMemoryTradingStore:
    return InMemoryTradingStore()


def make_signal(*, strategy_type: StrategyType = StrategyType.BULL_PUT_SPREAD) -> Signal:
    return Signal(
        timestamp=NOW,
        market_direction=Trend.BULLISH,
        strategy=Strategy(
            strategy_type=strategy_type,
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
        ),
        confidence=8,
        reasons=["Trend confirmation"],
        risk_level=RiskLevel.MEDIUM,
        message="rendered",
    )


async def test_compute_with_no_trades_is_all_zero(store: InMemoryTradingStore):
    agent = PerformanceAgent(account_size_usd=38_000.0, clock=FrozenClock(NOW))
    metrics = await agent.compute(store)
    assert metrics.total_signals == 0
    assert metrics.win_rate == 0.0
    assert metrics.max_drawdown_pct == 0.0
    assert metrics.strategy_performance == []


async def test_win_rate_and_average_return(store: InMemoryTradingStore):
    win_signal = await store.save_signal(make_signal())
    loss_signal = await store.save_signal(make_signal())
    await store.save_trade_result(
        TradeResult(
            signal_id=win_signal.id,
            outcome=TradeOutcome.WIN,
            pnl_usd=120.0,
            pnl_pct=31.5,
            closed_at=NOW,
        )
    )
    await store.save_trade_result(
        TradeResult(
            signal_id=loss_signal.id,
            outcome=TradeOutcome.LOSS,
            pnl_usd=-380.0,
            pnl_pct=-100.0,
            closed_at=NOW,
        )
    )
    agent = PerformanceAgent(account_size_usd=38_000.0, clock=FrozenClock(NOW))
    metrics = await agent.compute(store)
    assert metrics.total_signals == 2
    assert metrics.winning_signals == 1
    assert metrics.losing_signals == 1
    assert metrics.win_rate == 50.0
    assert metrics.average_return_pct == pytest.approx((31.5 - 100.0) / 2, abs=0.01)


async def test_max_drawdown_tracks_the_worst_peak_to_trough_move(store: InMemoryTradingStore):
    s1 = await store.save_signal(make_signal())
    s2 = await store.save_signal(make_signal())
    s3 = await store.save_signal(make_signal())
    # +500, then -900 (trough at -400 from the peak of +500): drawdown = 900 / account
    await store.save_trade_result(
        TradeResult(
            signal_id=s1.id, outcome=TradeOutcome.WIN, pnl_usd=500.0, pnl_pct=10.0, closed_at=NOW
        )
    )
    await store.save_trade_result(
        TradeResult(
            signal_id=s2.id, outcome=TradeOutcome.LOSS, pnl_usd=-900.0, pnl_pct=-20.0, closed_at=NOW
        )
    )
    await store.save_trade_result(
        TradeResult(
            signal_id=s3.id, outcome=TradeOutcome.WIN, pnl_usd=100.0, pnl_pct=5.0, closed_at=NOW
        )
    )
    agent = PerformanceAgent(account_size_usd=10_000.0, clock=FrozenClock(NOW))
    metrics = await agent.compute(store)
    assert metrics.max_drawdown_pct == pytest.approx(9.0)  # 900 / 10000 * 100


async def test_strategy_performance_groups_by_strategy_type(store: InMemoryTradingStore):
    bull_put = await store.save_signal(make_signal(strategy_type=StrategyType.BULL_PUT_SPREAD))
    iron_condor = await store.save_signal(make_signal(strategy_type=StrategyType.IRON_CONDOR))
    await store.save_trade_result(
        TradeResult(
            signal_id=bull_put.id,
            outcome=TradeOutcome.WIN,
            pnl_usd=120.0,
            pnl_pct=31.5,
            closed_at=NOW,
        )
    )
    await store.save_trade_result(
        TradeResult(
            signal_id=iron_condor.id,
            outcome=TradeOutcome.LOSS,
            pnl_usd=-200.0,
            pnl_pct=-50.0,
            closed_at=NOW,
        )
    )
    agent = PerformanceAgent(account_size_usd=38_000.0, clock=FrozenClock(NOW))
    metrics = await agent.compute(store)
    by_type = {p.strategy_type: p for p in metrics.strategy_performance}
    assert by_type[StrategyType.BULL_PUT_SPREAD].win_rate == 100.0
    assert by_type[StrategyType.IRON_CONDOR].win_rate == 0.0


async def test_ignores_trade_results_whose_signal_no_longer_exists(store: InMemoryTradingStore):
    await store.save_trade_result(
        TradeResult(
            signal_id="sig_missing",
            outcome=TradeOutcome.WIN,
            pnl_usd=100.0,
            pnl_pct=10.0,
            closed_at=NOW,
        )
    )
    agent = PerformanceAgent(account_size_usd=38_000.0, clock=FrozenClock(NOW))
    metrics = await agent.compute(store)
    assert metrics.total_signals == 1  # counted for the win rate
    assert metrics.strategy_performance == []  # but not attributable to a strategy


async def test_computed_at_uses_the_injected_clock(store: InMemoryTradingStore):
    clock = FrozenClock(NOW)
    agent = PerformanceAgent(account_size_usd=38_000.0, clock=clock)
    metrics = await agent.compute(store)
    assert metrics.computed_at == NOW
