from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jarvis.trading.models import RiskLevel, VolatilityState
from jarvis.trading.options_analysis_agent.agent import OptionsAnalysisAgent
from jarvis.trading.options_analysis_agent.provider import (
    RawOptionQuote,
    RawOptionsChain,
    SimulatedOptionsDataProvider,
)


def make_chain(*, spot=5500.0, iv_history=None, quotes=None) -> RawOptionsChain:
    now = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    if quotes is None:
        quotes = []
        for dte in (7, 14, 21, 30, 45):
            expiration = (now + timedelta(days=dte)).date().isoformat()
            for strike in (spot - 100, spot - 50, spot, spot + 50, spot + 100):
                for option_type, volume, oi in (("call", 500, 4000), ("put", 300, 3000)):
                    quotes.append(
                        RawOptionQuote(
                            strike=strike,
                            option_type=option_type,
                            expiration=expiration,
                            days_to_expiration=dte,
                            implied_volatility=0.15 + abs(strike - spot) / spot * 0.5,
                            open_interest=oi - int(abs(strike - spot)),
                            volume=volume,
                        )
                    )
    return RawOptionsChain(
        underlying="SPX",
        spot=spot,
        timestamp=now,
        quotes=quotes,
        iv_history=iv_history if iv_history is not None else [0.10 + i * 0.001 for i in range(200)],
    )


def test_picks_the_expiration_closest_to_the_target_dte():
    agent = OptionsAnalysisAgent()
    result = agent.analyze(make_chain())
    assert result.best_expiration  # 21 dte exists exactly in the fixture
    dte_by_expiration = {
        (datetime(2026, 3, 10, tzinfo=UTC) + timedelta(days=d)).date().isoformat(): d
        for d in (7, 14, 21, 30, 45)
    }
    assert dte_by_expiration[result.best_expiration] == 21


def test_important_strikes_are_capped_and_sorted_by_open_interest():
    agent = OptionsAnalysisAgent()
    result = agent.analyze(make_chain())
    assert 1 <= len(result.important_strikes) <= 6
    ois = [s.open_interest for s in result.important_strikes]
    assert ois == sorted(ois, reverse=True)


def test_important_strikes_carry_computed_greeks():
    agent = OptionsAnalysisAgent()
    result = agent.analyze(make_chain())
    for strike in result.important_strikes:
        assert -1.0 <= strike.greeks.delta <= 1.0
        assert strike.greeks.gamma >= 0


def test_iv_rank_reflects_position_in_history():
    agent = OptionsAnalysisAgent()
    # Current ATM iv is ~0.15; a history entirely above that ranks it near 0.
    high_history = [0.30 + i * 0.005 for i in range(40)]
    result = agent.analyze(make_chain(iv_history=high_history))
    assert result.iv_rank < 20


def test_volatility_state_is_low_when_iv_rank_is_near_zero():
    agent = OptionsAnalysisAgent()
    high_history = [0.30 + i * 0.005 for i in range(40)]
    result = agent.analyze(make_chain(iv_history=high_history))
    assert result.volatility_state == VolatilityState.LOW


def test_volatility_state_is_extreme_when_iv_rank_is_near_100():
    agent = OptionsAnalysisAgent()
    low_history = [0.02 + i * 0.001 for i in range(40)]
    result = agent.analyze(make_chain(iv_history=low_history))
    assert result.volatility_state == VolatilityState.EXTREME


def test_expected_move_is_positive_and_scaled_by_spot():
    agent = OptionsAnalysisAgent()
    result = agent.analyze(make_chain(spot=5500.0))
    assert result.expected_move > 0
    assert result.expected_move_pct == pytest.approx(result.expected_move / 5500.0 * 100, abs=0.01)


def test_put_call_ratio_and_positioning_agree():
    agent = OptionsAnalysisAgent()
    result = agent.analyze(make_chain())
    assert result.put_call_ratio > 0
    if result.put_call_ratio <= 0.8:
        assert "call-heavy" in result.market_positioning
    elif result.put_call_ratio >= 1.2:
        assert "put-heavy" in result.market_positioning
    else:
        assert "balanced" in result.market_positioning


def test_risk_level_is_high_for_extreme_iv_rank():
    agent = OptionsAnalysisAgent()
    low_history = [0.02 + i * 0.001 for i in range(40)]  # current iv far above history -> rank 100
    result = agent.analyze(make_chain(iv_history=low_history))
    assert result.risk_level == RiskLevel.HIGH


def test_analyze_raises_on_empty_chain():
    agent = OptionsAnalysisAgent()
    with pytest.raises(ValueError):
        agent.analyze(make_chain(quotes=[]))


async def test_simulated_provider_produces_analysable_chain():
    provider = SimulatedOptionsDataProvider(seed=5)
    now = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    chain = await provider.fetch_chain(underlying="SPX", spot=5500.0, now=now)
    assert len(chain.quotes) > 0
    assert len(chain.expirations()) == 5

    result = OptionsAnalysisAgent().analyze(chain)
    assert result.iv > 0
    assert result.expected_move > 0


async def test_simulated_provider_is_deterministic_for_a_given_minute():
    provider = SimulatedOptionsDataProvider(seed=5)
    now = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    first = await provider.fetch_chain(underlying="SPX", spot=5500.0, now=now)
    second = await provider.fetch_chain(underlying="SPX", spot=5500.0, now=now)
    assert first.quotes == second.quotes
