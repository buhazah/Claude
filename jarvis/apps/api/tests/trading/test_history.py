from __future__ import annotations

from jarvis.trading.market_data_agent.history import fetch_price_bars
from jarvis.trading.market_data_agent.provider import SimulatedMarketDataProvider


async def test_fetch_price_bars_returns_the_requested_count(trading_clock):
    provider = SimulatedMarketDataProvider(seed=2)
    bars = await fetch_price_bars(provider, now=trading_clock.now(), count=50)
    assert len(bars) == 50


async def test_fetch_price_bars_are_ordered_oldest_first(trading_clock):
    provider = SimulatedMarketDataProvider(seed=2)
    bars = await fetch_price_bars(provider, now=trading_clock.now(), count=10)
    timestamps = [b.timestamp for b in bars]
    assert timestamps == sorted(timestamps)
    assert timestamps[-1] == trading_clock.now()


async def test_fetch_price_bars_is_deterministic(trading_clock):
    provider = SimulatedMarketDataProvider(seed=9)
    first = await fetch_price_bars(provider, now=trading_clock.now(), count=20)
    second = await fetch_price_bars(provider, now=trading_clock.now(), count=20)
    assert [b.close for b in first] == [b.close for b in second]


async def test_fetch_price_bars_is_enough_for_technical_analysis(trading_clock):
    from jarvis.trading.technical_analysis_agent.agent import MIN_BARS, TechnicalAnalysisAgent

    provider = SimulatedMarketDataProvider(seed=4)
    bars = await fetch_price_bars(provider, now=trading_clock.now(), count=MIN_BARS)
    result = TechnicalAnalysisAgent().analyze(bars)
    assert result is not None
