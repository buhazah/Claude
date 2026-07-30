from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jarvis.trading.models import (
    BEARISH_STRATEGIES,
    BULLISH_STRATEGIES,
    NEUTRAL_STRATEGIES,
    MovingAverages,
    OptionsAnalysis,
    RiskLevel,
    TechnicalAnalysis,
    Trend,
    VolatilityState,
)
from jarvis.trading.options_analysis_agent.provider import RawOptionQuote, RawOptionsChain
from jarvis.trading.strategy_agent.agent import StrategyAgent

SPOT = 5500.0
NOW = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
EXPIRATION = (NOW + timedelta(days=21)).date().isoformat()


def make_chain() -> RawOptionsChain:
    quotes = []
    strike = SPOT - 500
    while strike <= SPOT + 500:
        for option_type in ("call", "put"):
            quotes.append(
                RawOptionQuote(
                    strike=strike,
                    option_type=option_type,
                    expiration=EXPIRATION,
                    days_to_expiration=21,
                    implied_volatility=0.15 + abs(strike - SPOT) / SPOT * 0.3,
                    open_interest=1000,
                    volume=500,
                )
            )
        strike += 25.0
    return RawOptionsChain(
        underlying="SPX", spot=SPOT, timestamp=NOW, quotes=quotes, iv_history=[0.15]
    )


def make_technical(trend: Trend) -> TechnicalAnalysis:
    return TechnicalAnalysis(
        trend=trend,
        strength=60.0,
        support_levels=[5400.0],
        resistance_levels=[5600.0],
        confidence_score=70.0,
        moving_averages=MovingAverages(
            sma_20=5490, sma_50=5470, sma_200=5400, ema_12=5495, ema_26=5480
        ),
        rsi=55.0,
        macd=1.2,
        macd_signal=0.8,
        macd_histogram=0.4,
        vwap=5495.0,
        momentum=1.5,
    )


def make_options_analysis() -> OptionsAnalysis:
    return OptionsAnalysis(
        volatility_state=VolatilityState.NORMAL,
        best_expiration=EXPIRATION,
        important_strikes=[],
        market_positioning="balanced put/call positioning",
        risk_level=RiskLevel.MEDIUM,
        iv=0.15,
        iv_rank=45.0,
        put_call_ratio=0.9,
        expected_move=120.0,
        expected_move_pct=2.2,
    )


@pytest.mark.parametrize(
    ("trend", "allowed"),
    [
        (Trend.BULLISH, BULLISH_STRATEGIES),
        (Trend.BEARISH, BEARISH_STRATEGIES),
        (Trend.NEUTRAL, NEUTRAL_STRATEGIES),
    ],
)
def test_generate_only_proposes_strategies_matching_the_trend(trend, allowed):
    agent = StrategyAgent()
    strategies = agent.generate(
        spot=SPOT,
        chain=make_chain(),
        technical_analysis=make_technical(trend),
        options_analysis=make_options_analysis(),
    )
    assert strategies  # the fixture chain supports every builder
    assert all(s.strategy_type in allowed for s in strategies)


def test_generate_offers_more_than_one_candidate_when_the_chain_allows_it():
    agent = StrategyAgent()
    strategies = agent.generate(
        spot=SPOT,
        chain=make_chain(),
        technical_analysis=make_technical(Trend.BULLISH),
        options_analysis=make_options_analysis(),
    )
    assert len(strategies) == 2


def test_generate_skips_builders_that_cannot_price_against_a_narrow_chain():
    chain = make_chain()
    chain.quotes = [q for q in chain.quotes if abs(q.strike - SPOT) <= 25]
    agent = StrategyAgent()
    strategies = agent.generate(
        spot=SPOT,
        chain=chain,
        technical_analysis=make_technical(Trend.BULLISH),
        options_analysis=make_options_analysis(),
    )
    assert strategies == []


def test_every_generated_strategy_targets_the_options_analysis_expiration():
    agent = StrategyAgent()
    strategies = agent.generate(
        spot=SPOT,
        chain=make_chain(),
        technical_analysis=make_technical(Trend.NEUTRAL),
        options_analysis=make_options_analysis(),
    )
    assert all(s.expiration == EXPIRATION for s in strategies)
