"""Signal monitoring: settling an expired position and deciding whether an
open one has hit its target or its stop.

Both are price-only rules. Settlement uses intrinsic value at expiration —
Black-Scholes has nothing left to say once time value is gone. Early
management (target/stop) is a systematic fraction-of-width rule rather than
a re-priced mark-to-market, which keeps it deterministic and testable
without needing a fresh IV read for every open position on every tick.
"""

from __future__ import annotations

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.trading.models import (
    SignalStatus,
    Strategy,
    StrategyLeg,
    StrategyType,
    TradeOutcome,
    TradeResult,
)

CREDIT_VERTICALS = (StrategyType.BULL_PUT_SPREAD, StrategyType.BEAR_CALL_SPREAD)
DEBIT_VERTICALS = (StrategyType.BULL_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD)

_EXPIRATION_STATUS = {
    TradeOutcome.WIN: SignalStatus.EXPIRED_WIN,
    TradeOutcome.LOSS: SignalStatus.EXPIRED_LOSS,
    TradeOutcome.BREAKEVEN: SignalStatus.CLOSED,
}


def expiration_status(outcome: TradeOutcome) -> SignalStatus:
    return _EXPIRATION_STATUS[outcome]


def settle_at_expiration(
    strategy: Strategy, *, signal_id: str, spot_at_expiration: float, clock: Clock = SYSTEM_CLOCK
) -> TradeResult:
    """The exact P&L of a strategy settled at expiration, from intrinsic
    value alone. A short leg owes its intrinsic value; a long leg is owed it."""
    settlement_value = 0.0
    for leg in strategy.legs:
        intrinsic = (
            max(spot_at_expiration - leg.strike, 0.0)
            if leg.option_type == "call"
            else max(leg.strike - spot_at_expiration, 0.0)
        )
        sign = 1.0 if leg.action == "buy" else -1.0
        settlement_value += sign * intrinsic * leg.quantity

    pnl_usd = round(settlement_value * 100 + strategy.credit * 100 - strategy.debit * 100, 2)
    basis = strategy.max_loss if strategy.max_loss > 0 else 1.0
    pnl_pct = round(pnl_usd / basis * 100, 2)

    if pnl_usd > 0.01:
        outcome = TradeOutcome.WIN
    elif pnl_usd < -0.01:
        outcome = TradeOutcome.LOSS
    else:
        outcome = TradeOutcome.BREAKEVEN

    return TradeResult(
        signal_id=signal_id,
        outcome=outcome,
        pnl_usd=pnl_usd,
        pnl_pct=pnl_pct,
        closed_at=clock.now(),
    )


def _leg(strategy: Strategy, *, action: str, option_type: str | None = None) -> StrategyLeg:
    for leg in strategy.legs:
        if leg.action == action and (option_type is None or leg.option_type == option_type):
            return leg
    raise ValueError(
        f"strategy has no {action} leg" + (f" of type {option_type}" if option_type else "")
    )


def evaluate_open_position(
    strategy: Strategy,
    *,
    spot: float,
    target_fraction: float = 0.5,
    stop_fraction: float = 0.5,
) -> SignalStatus | None:
    """``TARGET_HIT``, ``STOPPED_OUT``, or ``None`` if still within normal range."""
    if strategy.strategy_type in CREDIT_VERTICALS:
        short_leg = _leg(strategy, action="sell")
        long_leg = _leg(strategy, action="buy")
        width = abs(short_leg.strike - long_leg.strike)
        bullish = strategy.strategy_type == StrategyType.BULL_PUT_SPREAD
        direction = 1.0 if bullish else -1.0
        target_level = short_leg.strike + direction * width * target_fraction
        stop_level = short_leg.strike - direction * width * stop_fraction
        if (spot - target_level) * direction >= 0:
            return SignalStatus.TARGET_HIT
        if (stop_level - spot) * direction >= 0:
            return SignalStatus.STOPPED_OUT
        return None

    if strategy.strategy_type == StrategyType.IRON_CONDOR:
        put_short = _leg(strategy, action="sell", option_type="put")
        put_long = _leg(strategy, action="buy", option_type="put")
        call_short = _leg(strategy, action="sell", option_type="call")
        call_long = _leg(strategy, action="buy", option_type="call")
        put_width = abs(put_short.strike - put_long.strike)
        call_width = abs(call_short.strike - call_long.strike)
        put_target = put_short.strike + put_width * target_fraction
        call_target = call_short.strike - call_width * target_fraction
        put_stop = put_short.strike - put_width * stop_fraction
        call_stop = call_short.strike + call_width * stop_fraction
        if put_target <= spot <= call_target:
            return SignalStatus.TARGET_HIT
        if spot <= put_stop or spot >= call_stop:
            return SignalStatus.STOPPED_OUT
        return None

    if strategy.strategy_type in DEBIT_VERTICALS:
        # Risk is already capped at the debit paid, so there is no early
        # stop to manage — only whether the max-profit zone has been reached.
        short_leg = _leg(strategy, action="sell")
        bullish = strategy.strategy_type == StrategyType.BULL_CALL_SPREAD
        if (spot - short_leg.strike) * (1.0 if bullish else -1.0) >= 0:
            return SignalStatus.TARGET_HIT
        return None

    if strategy.strategy_type == StrategyType.BUTTERFLY:
        body = _leg(strategy, action="sell")
        wings = [leg for leg in strategy.legs if leg.action == "buy"]
        width = min(abs(body.strike - wing.strike) for wing in wings)
        distance = abs(spot - body.strike)
        if distance <= width * 0.15:
            return SignalStatus.TARGET_HIT
        if distance >= width * 0.9:
            return SignalStatus.STOPPED_OUT
        return None

    return None
