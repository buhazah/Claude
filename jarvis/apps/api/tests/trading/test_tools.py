from __future__ import annotations

from datetime import timedelta

from jarvis.trading.config import TradingSettings
from jarvis.trading.database.store import InMemoryTradingStore
from jarvis.trading.market_data_agent.agent import MarketDataAgent
from jarvis.trading.market_data_agent.provider import SimulatedMarketDataProvider
from jarvis.trading.models import (
    RiskLevel,
    Signal,
    SignalStatus,
    Strategy,
    StrategyLeg,
    StrategyType,
    Trend,
)
from jarvis.trading.options_analysis_agent.agent import OptionsAnalysisAgent
from jarvis.trading.options_analysis_agent.provider import SimulatedOptionsDataProvider
from jarvis.trading.performance_agent.agent import PerformanceAgent
from jarvis.trading.risk_manager_agent.agent import RiskManagerAgent
from jarvis.trading.signal_generator_agent.agent import SignalGeneratorAgent
from jarvis.trading.strategy_agent.agent import StrategyAgent
from jarvis.trading.technical_analysis_agent.agent import TechnicalAnalysisAgent
from jarvis.trading.tools import TradingTools


def make_tools(*, clock, settings: TradingSettings | None = None, store=None) -> TradingTools:
    settings = settings or TradingSettings()
    market_data_provider = SimulatedMarketDataProvider(seed=11)
    options_data_provider = SimulatedOptionsDataProvider(seed=11)
    return TradingTools(
        settings=settings,
        store=store or InMemoryTradingStore(clock=clock),
        market_data_provider=market_data_provider,
        options_data_provider=options_data_provider,
        market_data_agent=MarketDataAgent(market_data_provider, clock=clock),
        technical_agent=TechnicalAnalysisAgent(),
        options_agent=OptionsAnalysisAgent(),
        strategy_agent=StrategyAgent(),
        risk_agent=RiskManagerAgent(settings),
        signal_agent=SignalGeneratorAgent(),
        performance_agent=PerformanceAgent(account_size_usd=settings.account_size_usd, clock=clock),
        telegram_bot=None,
        clock=clock,
    )


async def test_collect_market_data_persists_snapshots(trading_clock):
    tools = make_tools(clock=trading_clock)
    result = await tools.collect_market_data()
    assert result["price"] > 0
    assert result["best_expiration"]
    assert await tools.store.latest_market_snapshot() is not None


async def test_generate_signal_reports_no_data_before_a_collection(trading_clock):
    tools = make_tools(clock=trading_clock)
    result = await tools.generate_signal()
    assert result["approved"] is False
    assert "no market data" in result["reason"]


async def test_generate_signal_approves_with_permissive_risk_settings(trading_clock):
    permissive = TradingSettings(
        min_probability_of_profit=0.0,
        max_risk_per_trade_pct=1000.0,
        max_daily_signals=99,
        max_consecutive_losses=99,
        account_size_usd=10_000_000.0,
        max_iv_rank_for_entry=100.0,
        min_risk_reward_ratio=0.0,
    )
    tools = make_tools(clock=trading_clock, settings=permissive)
    await tools.collect_market_data()
    result = await tools.generate_signal()
    assert result["approved"] is True
    assert result["signal_id"]
    stored = await tools.store.get_signal(result["signal_id"])
    assert stored is not None
    assert stored.status == SignalStatus.ACTIVE


async def test_generate_signal_rejects_when_daily_cap_is_zero(trading_clock):
    strict = TradingSettings(max_daily_signals=0)
    tools = make_tools(clock=trading_clock, settings=strict)
    await tools.collect_market_data()
    result = await tools.generate_signal()
    assert result["approved"] is False


async def test_daily_report_summarises_the_market(trading_clock):
    tools = make_tools(clock=trading_clock)
    result = await tools.daily_report()
    assert result["price"] > 0
    assert result["sent_to"] == 0  # no telegram bot configured


async def test_monitor_signals_with_nothing_active(trading_clock):
    tools = make_tools(clock=trading_clock)
    result = await tools.monitor_signals()
    assert result == {"checked": 0, "closed": 0}


def make_strategy(*, expiration: str) -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BULL_PUT_SPREAD,
        legs=[
            StrategyLeg(
                action="sell", option_type="put", strike=3000
            ),  # far below any simulated spot
            StrategyLeg(action="buy", option_type="put", strike=2950),
        ],
        entry="Sell SPX 3000 Put / Buy SPX 2950 Put",
        expiration=expiration,
        days_to_expiration=1,
        credit=1.0,
        max_profit=100.0,
        max_loss=400.0,
        probability_of_profit=90.0,
        risk_reward_ratio=0.25,
    )


async def test_monitor_signals_settles_an_expired_signal(trading_clock):
    tools = make_tools(clock=trading_clock)
    yesterday = (trading_clock.now() - timedelta(days=1)).date().isoformat()
    signal = Signal(
        timestamp=trading_clock.now() - timedelta(days=2),
        market_direction=Trend.BULLISH,
        strategy=make_strategy(expiration=yesterday),
        confidence=8,
        reasons=["Trend confirmation"],
        risk_level=RiskLevel.MEDIUM,
        message="rendered",
    )
    await tools.store.save_signal(signal)

    result = await tools.monitor_signals()
    assert result == {"checked": 1, "closed": 1}
    stored = await tools.store.get_signal(signal.id)
    assert stored is not None
    assert (
        stored.status == SignalStatus.EXPIRED_WIN
    )  # short strike 3000 is far below any simulated spot
    assert stored.result is not None

    trade_results = await tools.store.list_trade_results()
    assert len(trade_results) == 1
    assert trade_results[0].signal_id == signal.id


async def test_monitor_signals_leaves_a_healthy_position_open(trading_clock):
    tools = make_tools(clock=trading_clock)
    data = await tools.collect_market_data()
    spot = data["price"]
    future = (trading_clock.now() + timedelta(days=30)).date().isoformat()
    # Put short strike sits just 5 points OTM (inside the +/-25 "still open"
    # band around it); call side is far enough away to never factor in.
    strategy = Strategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=spot - 5),
            StrategyLeg(action="buy", option_type="put", strike=spot - 55),
            StrategyLeg(action="sell", option_type="call", strike=spot + 500),
            StrategyLeg(action="buy", option_type="call", strike=spot + 550),
        ],
        entry="condor",
        expiration=future,
        days_to_expiration=30,
        credit=2.0,
        max_profit=200.0,
        max_loss=4800.0,
        probability_of_profit=90.0,
        risk_reward_ratio=0.04,
    )
    signal = Signal(
        timestamp=trading_clock.now(),
        market_direction=Trend.NEUTRAL,
        strategy=strategy,
        confidence=6,
        reasons=["Range-bound structure"],
        risk_level=RiskLevel.LOW,
        message="rendered",
    )
    await tools.store.save_signal(signal)

    result = await tools.monitor_signals()
    assert result == {"checked": 1, "closed": 0}
    stored = await tools.store.get_signal(signal.id)
    assert stored is not None
    assert stored.status == SignalStatus.ACTIVE


async def test_compute_performance_persists_metrics(trading_clock):
    tools = make_tools(clock=trading_clock)
    result = await tools.compute_performance()
    assert result["total_signals"] == 0
    assert await tools.store.latest_performance_metrics() is not None
