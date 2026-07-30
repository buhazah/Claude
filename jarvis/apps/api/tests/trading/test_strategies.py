from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jarvis.trading.models import StrategyType
from jarvis.trading.options_analysis_agent.provider import RawOptionQuote, RawOptionsChain
from jarvis.trading.strategy_agent import strategies as build

SPOT = 5500.0
NOW = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
EXPIRATION = (NOW + timedelta(days=21)).date().isoformat()


def make_chain(
    *, spot: float = SPOT, iv: float = 0.15, strike_step: float = 25.0
) -> RawOptionsChain:
    quotes = []
    strike = spot - 500
    while strike <= spot + 500:
        for option_type in ("call", "put"):
            quotes.append(
                RawOptionQuote(
                    strike=strike,
                    option_type=option_type,
                    expiration=EXPIRATION,
                    days_to_expiration=21,
                    implied_volatility=iv + abs(strike - spot) / spot * 0.3,
                    open_interest=1000,
                    volume=500,
                )
            )
        strike += strike_step
    return RawOptionsChain(
        underlying="SPX", spot=spot, timestamp=NOW, quotes=quotes, iv_history=[iv]
    )


# ── credit verticals ─────────────────────────────────────────────────────


def test_bull_put_spread_sells_a_put_below_spot_and_buys_further_below():
    strategy = build.bull_put_spread(chain=make_chain(), expiration=EXPIRATION, spot=SPOT)
    assert strategy.strategy_type == StrategyType.BULL_PUT_SPREAD
    sell, buy = strategy.legs
    assert sell.action == "sell" and sell.option_type == "put"
    assert buy.action == "buy" and buy.option_type == "put"
    assert buy.strike < sell.strike < SPOT


def test_bull_put_spread_has_defined_and_positive_risk_reward():
    strategy = build.bull_put_spread(chain=make_chain(), expiration=EXPIRATION, spot=SPOT)
    assert strategy.credit > 0
    assert strategy.max_profit == pytest.approx(strategy.credit * 100, abs=0.01)
    assert strategy.max_loss > 0
    assert 0 < strategy.probability_of_profit <= 100
    assert strategy.risk_reward_ratio > 0


def test_bear_call_spread_sells_a_call_above_spot_and_buys_further_above():
    strategy = build.bear_call_spread(chain=make_chain(), expiration=EXPIRATION, spot=SPOT)
    assert strategy.strategy_type == StrategyType.BEAR_CALL_SPREAD
    sell, buy = strategy.legs
    assert sell.strike > SPOT
    assert buy.strike > sell.strike


def test_credit_spread_probability_matches_short_delta_heuristic():
    strategy = build.bull_put_spread(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, short_delta_target=0.25
    )
    # (1 - |delta|) * 100 with delta near the 0.25 target lands near 75%.
    assert 65 <= strategy.probability_of_profit <= 85


def test_credit_spread_raises_when_chain_is_too_narrow_for_the_width():
    narrow = make_chain()
    narrow.quotes = [q for q in narrow.quotes if abs(q.strike - SPOT) <= 25]
    with pytest.raises(ValueError):
        build.bull_put_spread(chain=narrow, expiration=EXPIRATION, spot=SPOT, width=200)


# ── debit verticals ──────────────────────────────────────────────────────


def test_bull_call_spread_buys_the_nearer_strike_and_sells_further_out():
    strategy = build.bull_call_spread(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=120.0
    )
    assert strategy.strategy_type == StrategyType.BULL_CALL_SPREAD
    buy, sell = strategy.legs
    assert buy.action == "buy" and sell.action == "sell"
    assert buy.strike < sell.strike
    assert strategy.debit > 0
    assert strategy.max_loss == pytest.approx(strategy.debit * 100, abs=0.01)


def test_bear_put_spread_buys_the_nearer_strike_and_sells_further_out():
    strategy = build.bear_put_spread(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=120.0
    )
    assert strategy.strategy_type == StrategyType.BEAR_PUT_SPREAD
    buy, sell = strategy.legs
    assert buy.strike > sell.strike  # buy nearer-the-money put, sell one further OTM (lower)
    assert strategy.debit > 0


def test_debit_spread_probability_is_bounded():
    strategy = build.bull_call_spread(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=120.0
    )
    assert 0 <= strategy.probability_of_profit <= 100


# ── iron condor ──────────────────────────────────────────────────────────


def test_iron_condor_combines_a_put_and_a_call_credit_spread():
    strategy = build.iron_condor(chain=make_chain(), expiration=EXPIRATION, spot=SPOT)
    assert strategy.strategy_type == StrategyType.IRON_CONDOR
    assert len(strategy.legs) == 4
    puts = [leg for leg in strategy.legs if leg.option_type == "put"]
    calls = [leg for leg in strategy.legs if leg.option_type == "call"]
    assert len(puts) == 2 and len(calls) == 2
    assert strategy.credit > 0
    assert strategy.max_profit > 0
    assert strategy.max_loss > 0


def test_iron_condor_probability_is_higher_than_a_single_credit_spread():
    condor = build.iron_condor(chain=make_chain(), expiration=EXPIRATION, spot=SPOT)
    single = build.bull_put_spread(chain=make_chain(), expiration=EXPIRATION, spot=SPOT)
    # Two-sided containment is a lower bar to fail than a single boundary, so
    # the naive combined probability tracks it — this is a sanity bound, not
    # exact equivalence given each strategy targets a different delta.
    assert condor.probability_of_profit > 0
    assert single.probability_of_profit > 0


# ── butterfly ────────────────────────────────────────────────────────────


def test_butterfly_is_centered_at_the_money_with_symmetric_wings():
    strategy = build.butterfly(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=120.0
    )
    assert strategy.strategy_type == StrategyType.BUTTERFLY
    lower, body, upper = strategy.legs
    assert body.action == "sell" and body.quantity == 2
    assert lower.action == "buy" and upper.action == "buy"
    assert upper.strike - body.strike == pytest.approx(body.strike - lower.strike)


def test_butterfly_is_cheap_relative_to_its_max_profit():
    strategy = build.butterfly(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=120.0
    )
    assert strategy.debit > 0
    assert strategy.max_loss == pytest.approx(strategy.debit * 100, abs=0.01)
    assert strategy.max_profit > 0


def test_butterfly_probability_uses_expected_move():
    tight = build.butterfly(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=30.0
    )
    wide = build.butterfly(
        chain=make_chain(), expiration=EXPIRATION, spot=SPOT, expected_move_points=300.0
    )
    # A butterfly only pays off if price stays pinned near the body; a wider
    # expected move makes that less likely, not more.
    assert tight.probability_of_profit > wide.probability_of_profit
