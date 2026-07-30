from __future__ import annotations

import pytest

from jarvis.trading.options_analysis_agent.greeks import (
    black_scholes_greeks,
    expected_move,
    iv_rank,
)


def test_atm_call_delta_is_near_half():
    greeks = black_scholes_greeks(
        spot=5000, strike=5000, days_to_expiration=30, volatility=0.15, option_type="call"
    )
    assert 0.45 < greeks.delta < 0.65


def test_atm_put_delta_is_near_negative_half():
    greeks = black_scholes_greeks(
        spot=5000, strike=5000, days_to_expiration=30, volatility=0.15, option_type="put"
    )
    assert -0.65 < greeks.delta < -0.45


def test_deep_itm_call_delta_approaches_one():
    greeks = black_scholes_greeks(
        spot=5500, strike=4000, days_to_expiration=30, volatility=0.15, option_type="call"
    )
    assert greeks.delta > 0.95


def test_deep_otm_call_delta_approaches_zero():
    greeks = black_scholes_greeks(
        spot=4000, strike=5500, days_to_expiration=30, volatility=0.15, option_type="call"
    )
    assert greeks.delta < 0.05


def test_put_call_delta_parity_at_same_strike():
    call = black_scholes_greeks(
        spot=5000, strike=5100, days_to_expiration=30, volatility=0.15, option_type="call"
    )
    put = black_scholes_greeks(
        spot=5000, strike=5100, days_to_expiration=30, volatility=0.15, option_type="put"
    )
    assert call.delta - put.delta == pytest.approx(1.0, abs=0.01)


def test_gamma_and_vega_are_positive_and_shared_across_call_and_put():
    call = black_scholes_greeks(
        spot=5000, strike=5000, days_to_expiration=30, volatility=0.15, option_type="call"
    )
    put = black_scholes_greeks(
        spot=5000, strike=5000, days_to_expiration=30, volatility=0.15, option_type="put"
    )
    assert call.gamma > 0
    assert call.vega > 0
    assert call.gamma == pytest.approx(put.gamma, rel=1e-6)
    assert call.vega == pytest.approx(put.vega, rel=1e-6)


def test_theta_is_negative_for_long_options_near_expiration():
    call = black_scholes_greeks(
        spot=5000, strike=5000, days_to_expiration=5, volatility=0.15, option_type="call"
    )
    put = black_scholes_greeks(
        spot=5000, strike=5000, days_to_expiration=5, volatility=0.15, option_type="put"
    )
    assert call.theta < 0
    assert put.theta < 0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        (
            dict(spot=0, strike=5000, days_to_expiration=30, volatility=0.15, option_type="call"),
            "positive",
        ),
        (
            dict(spot=5000, strike=5000, days_to_expiration=30, volatility=0, option_type="call"),
            "volatility",
        ),
        (
            dict(spot=5000, strike=5000, days_to_expiration=0, volatility=0.15, option_type="call"),
            "days",
        ),
        (
            dict(
                spot=5000,
                strike=5000,
                days_to_expiration=30,
                volatility=0.15,
                option_type="straddle",
            ),
            "option_type",
        ),
    ],
)
def test_black_scholes_rejects_invalid_input(kwargs, match):
    with pytest.raises(ValueError, match=match):
        black_scholes_greeks(**kwargs)


def test_iv_rank_at_the_low_of_its_range_is_zero():
    assert iv_rank(0.10, [0.10, 0.15, 0.20, 0.25]) == 0.0


def test_iv_rank_at_the_high_of_its_range_is_100():
    assert iv_rank(0.25, [0.10, 0.15, 0.20, 0.25]) == 100.0


def test_iv_rank_midpoint_is_50():
    assert iv_rank(0.175, [0.10, 0.25]) == pytest.approx(50.0)


def test_iv_rank_clamps_outside_the_observed_range():
    assert iv_rank(0.50, [0.10, 0.20]) == 100.0
    assert iv_rank(0.01, [0.10, 0.20]) == 0.0


def test_iv_rank_of_empty_history_is_midpoint():
    assert iv_rank(0.15, []) == 50.0


def test_iv_rank_of_flat_history_is_midpoint():
    assert iv_rank(0.15, [0.12, 0.12, 0.12]) == 50.0


def test_expected_move_scales_with_volatility_and_time():
    low_vol, _ = expected_move(spot=5000, volatility=0.10, days_to_expiration=30)
    high_vol, _ = expected_move(spot=5000, volatility=0.30, days_to_expiration=30)
    assert high_vol > low_vol

    short_dte, _ = expected_move(spot=5000, volatility=0.15, days_to_expiration=7)
    long_dte, _ = expected_move(spot=5000, volatility=0.15, days_to_expiration=45)
    assert long_dte > short_dte


def test_expected_move_pct_is_move_over_spot():
    move, pct = expected_move(spot=5000, volatility=0.15, days_to_expiration=30)
    assert pct == pytest.approx(move / 5000 * 100)


def test_expected_move_rejects_nonpositive_days():
    with pytest.raises(ValueError, match="days"):
        expected_move(spot=5000, volatility=0.15, days_to_expiration=0)
