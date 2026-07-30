from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jarvis.trading.models import Trend
from jarvis.trading.technical_analysis_agent.agent import MIN_BARS, TechnicalAnalysisAgent
from jarvis.trading.technical_analysis_agent.indicators import PriceBar


def make_bars(closes: list[float]) -> list[PriceBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        PriceBar(
            timestamp=start + timedelta(minutes=i),
            open=c,
            high=c + 1.5,
            low=c - 1.5,
            close=c,
            volume=1_000_000 + i,
        )
        for i, c in enumerate(closes)
    ]


def uptrend_bars(n: int = 260) -> list[PriceBar]:
    return make_bars([5000.0 + i * 1.5 for i in range(n)])


def downtrend_bars(n: int = 260) -> list[PriceBar]:
    return make_bars([5500.0 - i * 1.5 for i in range(n)])


def flat_bars(n: int = 260) -> list[PriceBar]:
    return make_bars([5300.0 for _ in range(n)])


def test_analyze_requires_minimum_history():
    agent = TechnicalAnalysisAgent()
    with pytest.raises(ValueError, match=str(MIN_BARS)):
        agent.analyze(make_bars([5000.0] * (MIN_BARS - 1)))


def test_sustained_uptrend_is_classified_bullish():
    agent = TechnicalAnalysisAgent()
    result = agent.analyze(uptrend_bars())
    assert result.trend == Trend.BULLISH
    assert result.strength > 0
    assert "uptrend" in result.market_structure


def test_sustained_downtrend_is_classified_bearish():
    agent = TechnicalAnalysisAgent()
    result = agent.analyze(downtrend_bars())
    assert result.trend == Trend.BEARISH
    assert "downtrend" in result.market_structure


def test_flat_market_is_classified_neutral():
    agent = TechnicalAnalysisAgent()
    result = agent.analyze(flat_bars())
    assert result.trend == Trend.NEUTRAL


def test_scores_are_within_documented_bounds():
    agent = TechnicalAnalysisAgent()
    for bars in (uptrend_bars(), downtrend_bars(), flat_bars()):
        result = agent.analyze(bars)
        assert 0 <= result.strength <= 100
        assert 0 <= result.confidence_score <= 100
        assert 0 <= result.rsi <= 100


def test_moving_averages_are_populated():
    agent = TechnicalAnalysisAgent()
    result = agent.analyze(uptrend_bars())
    mas = result.moving_averages
    assert mas.sma_200 < mas.sma_50 < mas.sma_20  # rising series: shorter MA is higher


def test_vwap_is_close_to_recent_price_level():
    agent = TechnicalAnalysisAgent()
    bars = flat_bars()
    result = agent.analyze(bars)
    assert result.vwap == pytest.approx(5300.0, abs=2.0)


def test_support_and_resistance_levels_are_sorted_lists():
    agent = TechnicalAnalysisAgent()
    closes = [5300 + (10 if i % 20 < 10 else -10) for i in range(260)]
    result = agent.analyze(make_bars(closes))
    assert result.support_levels == sorted(result.support_levels)
    assert result.resistance_levels == sorted(result.resistance_levels)
