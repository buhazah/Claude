"""Assembles a price-bar history for the Technical Analysis Agent from a
:class:`~jarvis.trading.market_data_agent.provider.MarketDataProvider`.

This replays the live-quote endpoint at each of the last ``count`` minutes,
which is exactly right for :class:`SimulatedMarketDataProvider` — its reading
is a pure function of the timestamp, so replaying it *is* history. A real
vendor integration should back this with a dedicated historical-bars
endpoint instead of calling a live-quote endpoint hundreds of times; this
helper is deliberately provider-agnostic so swapping that in later is a
different function, not a different call site.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from jarvis.trading.market_data_agent.provider import MarketDataProvider
from jarvis.trading.technical_analysis_agent.indicators import PriceBar


async def fetch_price_bars(
    provider: MarketDataProvider, *, now: datetime, count: int = 200, interval_minutes: int = 1
) -> list[PriceBar]:
    """The last ``count`` bars up to and including ``now``, oldest first."""
    bars: list[PriceBar] = []
    for offset in range(count - 1, -1, -1):
        timestamp = now - timedelta(minutes=offset * interval_minutes)
        raw = await provider.fetch(now=timestamp)
        bars.append(
            PriceBar(
                timestamp=timestamp,
                open=raw.spx_price,
                high=raw.spx_price,
                low=raw.spx_price,
                close=raw.spx_price,
                volume=raw.volume,
            )
        )
    return bars
