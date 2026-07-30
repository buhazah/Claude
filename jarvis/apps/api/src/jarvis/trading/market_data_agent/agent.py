"""Market Data Agent: collects the broad-market read every other agent starts from."""

from __future__ import annotations

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.trading.market_data_agent.provider import MarketDataProvider, RawMarketData
from jarvis.trading.models import MarketCondition, MarketSnapshot, Trend

HIGH_VIX = 25.0
LOW_VIX = 12.0
TRENDING_BREADTH = 0.4
DIRECTIONAL_BREADTH = 0.2


def _trend(raw: RawMarketData) -> Trend:
    if raw.market_breadth > DIRECTIONAL_BREADTH:
        return Trend.BULLISH
    if raw.market_breadth < -DIRECTIONAL_BREADTH:
        return Trend.BEARISH
    return Trend.NEUTRAL


def _market_condition(raw: RawMarketData) -> MarketCondition:
    if raw.vix >= HIGH_VIX:
        return MarketCondition.HIGH_VOLATILITY
    if raw.vix <= LOW_VIX:
        return MarketCondition.LOW_VOLATILITY
    if raw.market_breadth >= TRENDING_BREADTH:
        return MarketCondition.TRENDING_UP
    if raw.market_breadth <= -TRENDING_BREADTH:
        return MarketCondition.TRENDING_DOWN
    return MarketCondition.RANGE_BOUND


class MarketDataAgent:
    """Collects SPX/SPY/VIX/futures/breadth/calendar/sentiment and summarises
    them into a :class:`~jarvis.trading.models.MarketSnapshot`."""

    def __init__(self, provider: MarketDataProvider, *, clock: Clock = SYSTEM_CLOCK) -> None:
        self._provider = provider
        self._clock = clock

    async def collect(self) -> MarketSnapshot:
        now = self._clock.now()
        raw = await self._provider.fetch(now=now)
        return MarketSnapshot(
            timestamp=raw.timestamp,
            symbol="SPX",
            price=raw.spx_price,
            volume=raw.volume,
            vix=raw.vix,
            trend=_trend(raw),
            market_condition=_market_condition(raw),
            spy_price=raw.spy_price,
            futures_price=raw.futures_price,
            futures_symbol=raw.futures_symbol,
            market_breadth=raw.market_breadth,
            economic_events=raw.economic_events,
            news_sentiment=raw.news_sentiment,
        )
