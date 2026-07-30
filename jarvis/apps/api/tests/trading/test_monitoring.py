from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.kernel.clock import FrozenClock
from jarvis.trading.models import SignalStatus, Strategy, StrategyLeg, StrategyType, TradeOutcome
from jarvis.trading.monitoring import (
    evaluate_open_position,
    expiration_status,
    settle_at_expiration,
)

NOW = datetime(2026, 3, 24, tzinfo=UTC)


def bull_put_spread() -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BULL_PUT_SPREAD,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=5450),
            StrategyLeg(action="buy", option_type="put", strike=5400),
        ],
        entry="Sell SPX 5450 Put / Buy SPX 5400 Put",
        expiration="2026-03-24",
        days_to_expiration=14,
        credit=1.20,
        max_profit=120.0,
        max_loss=380.0,
        probability_of_profit=74.0,
        risk_reward_ratio=0.32,
    )


def bull_call_spread() -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            StrategyLeg(action="buy", option_type="call", strike=5500),
            StrategyLeg(action="sell", option_type="call", strike=5550),
        ],
        entry="Buy SPX 5500 Call / Sell SPX 5550 Call",
        expiration="2026-03-24",
        days_to_expiration=14,
        debit=15.0,
        max_profit=3500.0,
        max_loss=1500.0,
        probability_of_profit=45.0,
        risk_reward_ratio=2.33,
    )


def iron_condor() -> Strategy:
    return Strategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=5400),
            StrategyLeg(action="buy", option_type="put", strike=5350),
            StrategyLeg(action="sell", option_type="call", strike=5600),
            StrategyLeg(action="buy", option_type="call", strike=5650),
        ],
        entry="condor",
        expiration="2026-03-24",
        days_to_expiration=14,
        credit=2.0,
        max_profit=200.0,
        max_loss=2800.0,
        probability_of_profit=68.0,
        risk_reward_ratio=0.071,
    )


def butterfly() -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BUTTERFLY,
        legs=[
            StrategyLeg(action="buy", option_type="call", strike=5450),
            StrategyLeg(action="sell", option_type="call", strike=5500, quantity=2),
            StrategyLeg(action="buy", option_type="call", strike=5550),
        ],
        entry="butterfly",
        expiration="2026-03-24",
        days_to_expiration=14,
        debit=8.0,
        max_profit=4200.0,
        max_loss=800.0,
        probability_of_profit=28.0,
        risk_reward_ratio=5.25,
    )


# ── settlement ───────────────────────────────────────────────────────────


def test_settle_credit_spread_wins_when_price_stays_above_short_strike():
    result = settle_at_expiration(
        bull_put_spread(), signal_id="sig_1", spot_at_expiration=5500.0, clock=FrozenClock(NOW)
    )
    assert result.outcome == TradeOutcome.WIN
    assert result.pnl_usd == pytest.approx(120.0)  # keeps the full credit


def test_settle_credit_spread_loses_max_loss_when_price_is_below_both_strikes():
    result = settle_at_expiration(
        bull_put_spread(), signal_id="sig_1", spot_at_expiration=5300.0, clock=FrozenClock(NOW)
    )
    assert result.outcome == TradeOutcome.LOSS
    # Both legs fully ITM: settlement = -(50 wide) * 100 + credit * 100.
    assert result.pnl_usd == pytest.approx(-50 * 100 + 1.20 * 100)


def test_settle_credit_spread_partial_loss_between_strikes():
    result = settle_at_expiration(
        bull_put_spread(), signal_id="sig_1", spot_at_expiration=5425.0, clock=FrozenClock(NOW)
    )
    # short put is 25 ITM, long put worthless: settlement = -25*100 + 120 = -2380
    assert result.pnl_usd == pytest.approx(-2380.0)
    assert result.outcome == TradeOutcome.LOSS


def test_settle_debit_spread_wins_at_max_profit_above_short_strike():
    result = settle_at_expiration(
        bull_call_spread(), signal_id="sig_2", spot_at_expiration=5600.0, clock=FrozenClock(NOW)
    )
    assert result.outcome == TradeOutcome.WIN
    assert result.pnl_usd == pytest.approx(3500.0)


def test_settle_debit_spread_loses_full_debit_below_long_strike():
    result = settle_at_expiration(
        bull_call_spread(), signal_id="sig_2", spot_at_expiration=5400.0, clock=FrozenClock(NOW)
    )
    assert result.outcome == TradeOutcome.LOSS
    assert result.pnl_usd == pytest.approx(-1500.0)


def test_expiration_status_maps_outcomes():
    assert expiration_status(TradeOutcome.WIN) == SignalStatus.EXPIRED_WIN
    assert expiration_status(TradeOutcome.LOSS) == SignalStatus.EXPIRED_LOSS
    assert expiration_status(TradeOutcome.BREAKEVEN) == SignalStatus.CLOSED


# ── open position management ────────────────────────────────────────────


def test_bull_put_spread_hits_target_when_price_rallies():
    status = evaluate_open_position(
        bull_put_spread(), spot=5480.0
    )  # short 5450 + 0.5*50=25 -> 5475
    assert status == SignalStatus.TARGET_HIT


def test_bull_put_spread_stops_out_when_price_breaks_down():
    status = evaluate_open_position(bull_put_spread(), spot=5420.0)  # short 5450 - 25 = 5425
    assert status == SignalStatus.STOPPED_OUT


def test_bull_put_spread_stays_open_in_the_normal_range():
    status = evaluate_open_position(bull_put_spread(), spot=5450.0)
    assert status is None


def test_iron_condor_hits_target_when_pinned_in_the_middle():
    status = evaluate_open_position(iron_condor(), spot=5500.0)
    assert status == SignalStatus.TARGET_HIT


def test_iron_condor_stops_out_on_a_breach():
    status = evaluate_open_position(iron_condor(), spot=5630.0)  # call_stop = 5600 + 50*0.5 = 5625
    assert status == SignalStatus.STOPPED_OUT


def test_iron_condor_stays_open_near_a_short_strike():
    status = evaluate_open_position(iron_condor(), spot=5405.0)
    assert status is None


def test_debit_spread_has_no_stop_only_a_target():
    losing_but_capped = evaluate_open_position(bull_call_spread(), spot=5100.0)
    assert losing_but_capped is None  # never STOPPED_OUT: risk is already capped at the debit


def test_debit_spread_hits_target_past_the_short_strike():
    status = evaluate_open_position(bull_call_spread(), spot=5560.0)
    assert status == SignalStatus.TARGET_HIT


def test_butterfly_hits_target_when_pinned_at_the_body():
    status = evaluate_open_position(butterfly(), spot=5502.0)
    assert status == SignalStatus.TARGET_HIT


def test_butterfly_stops_out_near_the_wings():
    status = evaluate_open_position(butterfly(), spot=5548.0)
    assert status == SignalStatus.STOPPED_OUT


def test_butterfly_stays_open_between_pin_and_wing():
    status = evaluate_open_position(butterfly(), spot=5520.0)
    assert status is None
