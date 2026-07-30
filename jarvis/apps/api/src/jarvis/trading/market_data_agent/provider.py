"""Market data sources.

``MarketDataProvider`` is the seam between the agent and wherever prices
actually come from. Two implementations ship: :class:`SimulatedMarketDataProvider`,
a deterministic synthetic feed used by default and by every test, and
:class:`HttpMarketDataProvider`, a thin adapter for a real REST vendor
(Polygon.io, Tradier, CBOE) configured entirely through
:class:`~jarvis.trading.config.TradingSettings` — no vendor-specific code
needs to change to point it at a different feed, only the field mapping.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import httpx


@dataclass(slots=True)
class RawMarketData:
    """Everything the market data agent asked for, before it is summarised
    into a :class:`~jarvis.trading.models.MarketSnapshot`."""

    timestamp: datetime
    spx_price: float
    spy_price: float
    vix: float
    volume: float
    futures_price: float
    futures_symbol: str
    market_breadth: float
    economic_events: list[str] = field(default_factory=list)
    news_sentiment: float = 0.0


class MarketDataProvider(Protocol):
    async def fetch(self, *, now: datetime) -> RawMarketData: ...


class SimulatedMarketDataProvider:
    """A deterministic synthetic feed.

    Deterministic in the sense that matters for a trading system under
    test: the same ``now`` always produces the same reading. The value moves
    with a smooth diurnal-looking wave plus bounded pseudo-random noise seeded
    from the minute, so a market-scan workflow polled every five minutes sees
    a plausibly evolving tape rather than white noise or a flat line.
    """

    def __init__(
        self,
        *,
        base_price: float = 5_500.0,
        base_vix: float = 15.0,
        seed: int = 0,
    ) -> None:
        self._base_price = base_price
        self._base_vix = base_vix
        self._seed = seed

    async def fetch(self, *, now: datetime) -> RawMarketData:
        minute_bucket = int(now.timestamp() // 60)
        rng = random.Random((minute_bucket * 2654435761 + self._seed) & 0xFFFFFFFF)

        wave = math.sin(minute_bucket / 180.0) * 25.0
        drift = rng.uniform(-4.0, 4.0)
        spx = round(self._base_price + wave + drift, 2)
        spy = round(spx / 10.0, 2)

        vix_wave = math.sin(minute_bucket / 240.0 + 1.0) * 3.0
        vix = round(max(9.0, self._base_vix + vix_wave + rng.uniform(-1.0, 1.0)), 2)

        futures = round(spx - rng.uniform(-2.0, 2.0), 2)
        breadth = round(max(-1.0, min(1.0, math.sin(minute_bucket / 150.0))), 3)
        volume = round(1_800_000_000 + rng.uniform(-2e8, 2e8), 0)
        sentiment = round(max(-1.0, min(1.0, math.sin(minute_bucket / 300.0 + 0.5))), 3)

        events: list[str] = []
        if now.hour == 14 and now.minute < 5:
            events.append("FOMC Rate Decision")
        if now.weekday() == 4 and now.hour == 12 and now.minute < 5:
            events.append("Non-Farm Payrolls")

        return RawMarketData(
            timestamp=now,
            spx_price=spx,
            spy_price=spy,
            vix=vix,
            volume=volume,
            futures_price=futures,
            futures_symbol="ES",
            market_breadth=breadth,
            economic_events=events,
            news_sentiment=sentiment,
        )


class HttpMarketDataProvider:
    """A generic REST adapter for a real market-data vendor.

    ``field_map`` translates the vendor's JSON keys into the ``RawMarketData``
    fields this system needs, so pointing this at Polygon, Tradier or another
    vendor is configuration (base URL, headers, field map) rather than a new
    class. Nothing here is called unless ``TRADING_MARKET_DATA_PROVIDER`` is
    set to something other than ``simulated`` *and* an API key is configured.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        field_map: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._field_map = field_map or {
            "spx_price": "spx_price",
            "spy_price": "spy_price",
            "vix": "vix",
            "volume": "volume",
            "futures_price": "futures_price",
            "market_breadth": "market_breadth",
            "news_sentiment": "news_sentiment",
        }
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=10.0)

    async def fetch(self, *, now: datetime) -> RawMarketData:
        response = await self._client.get(
            "/snapshot", headers={"Authorization": f"Bearer {self._api_key}"}
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()

        def get(key: str, default: float = 0.0) -> float:
            return float(payload.get(self._field_map.get(key, key), default))

        return RawMarketData(
            timestamp=now,
            spx_price=get("spx_price"),
            spy_price=get("spy_price"),
            vix=get("vix"),
            volume=get("volume"),
            futures_price=get("futures_price", get("spx_price")),
            futures_symbol=str(payload.get("futures_symbol", "ES")),
            market_breadth=get("market_breadth"),
            economic_events=list(payload.get("economic_events", [])),
            news_sentiment=get("news_sentiment"),
        )
