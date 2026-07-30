from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from jarvis.trading.market_data_agent.agent import MarketDataAgent
from jarvis.trading.market_data_agent.provider import (
    HttpMarketDataProvider,
    RawMarketData,
    SimulatedMarketDataProvider,
)
from jarvis.trading.models import MarketCondition, Trend


async def test_simulated_provider_is_deterministic_for_a_given_minute(trading_clock):
    provider = SimulatedMarketDataProvider(seed=7)
    first = await provider.fetch(now=trading_clock.now())
    second = await provider.fetch(now=trading_clock.now())
    assert first == second


async def test_simulated_provider_moves_between_minutes(trading_clock):
    provider = SimulatedMarketDataProvider(seed=7)
    first = await provider.fetch(now=trading_clock.now())
    trading_clock.advance(600)
    second = await provider.fetch(now=trading_clock.now())
    assert first.spx_price != second.spx_price or first.vix != second.vix


async def test_simulated_provider_prices_are_plausible(trading_clock):
    provider = SimulatedMarketDataProvider(seed=1)
    raw = await provider.fetch(now=trading_clock.now())
    assert 4_000 < raw.spx_price < 7_000
    assert raw.vix > 0
    assert raw.spy_price == round(raw.spx_price / 10.0, 2)
    assert -1.0 <= raw.market_breadth <= 1.0
    assert -1.0 <= raw.news_sentiment <= 1.0


async def test_market_data_agent_collects_a_snapshot(trading_clock):
    agent = MarketDataAgent(SimulatedMarketDataProvider(seed=3), clock=trading_clock)
    snapshot = await agent.collect()
    assert snapshot.symbol == "SPX"
    assert snapshot.timestamp == trading_clock.now()
    assert snapshot.trend in Trend
    assert snapshot.market_condition in MarketCondition
    assert snapshot.spy_price is not None
    assert snapshot.futures_symbol == "ES"


@pytest.mark.parametrize(
    ("breadth", "expected"),
    [(0.6, Trend.BULLISH), (-0.6, Trend.BEARISH), (0.05, Trend.NEUTRAL)],
)
async def test_trend_follows_market_breadth(trading_clock, breadth, expected):
    class FixedProvider:
        async def fetch(self, *, now: datetime) -> RawMarketData:
            return RawMarketData(
                timestamp=now,
                spx_price=5500,
                spy_price=550,
                vix=15,
                volume=1e9,
                futures_price=5500,
                futures_symbol="ES",
                market_breadth=breadth,
            )

    agent = MarketDataAgent(FixedProvider(), clock=trading_clock)
    snapshot = await agent.collect()
    assert snapshot.trend == expected


@pytest.mark.parametrize(
    ("vix", "breadth", "expected"),
    [
        (30.0, 0.0, MarketCondition.HIGH_VOLATILITY),
        (8.0, 0.0, MarketCondition.LOW_VOLATILITY),
        (15.0, 0.5, MarketCondition.TRENDING_UP),
        (15.0, -0.5, MarketCondition.TRENDING_DOWN),
        (15.0, 0.0, MarketCondition.RANGE_BOUND),
    ],
)
async def test_market_condition_classification(trading_clock, vix, breadth, expected):
    class FixedProvider:
        async def fetch(self, *, now: datetime) -> RawMarketData:
            return RawMarketData(
                timestamp=now,
                spx_price=5500,
                spy_price=550,
                vix=vix,
                volume=1e9,
                futures_price=5500,
                futures_symbol="ES",
                market_breadth=breadth,
            )

    agent = MarketDataAgent(FixedProvider(), clock=trading_clock)
    snapshot = await agent.collect()
    assert snapshot.market_condition == expected


async def test_http_market_data_provider_maps_vendor_fields(trading_clock):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "spx_price": 5510.25,
                "spy_price": 551.0,
                "vix": 14.2,
                "volume": 1_900_000_000,
                "futures_price": 5512.0,
                "futures_symbol": "ES",
                "market_breadth": 0.1,
                "news_sentiment": 0.2,
                "economic_events": ["CPI"],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://vendor")
    provider = HttpMarketDataProvider(base_url="https://vendor", api_key="test-key", client=client)
    raw = await provider.fetch(now=trading_clock.now())
    assert raw.spx_price == 5510.25
    assert raw.economic_events == ["CPI"]
    await client.aclose()
