"""Strategy builders.

Each function takes an options chain and a target expiration and returns one
priced :class:`~jarvis.trading.models.Strategy`. All strike selection is by
delta (the standard way premium sellers pick strikes) and all pricing is
Black-Scholes off the chain's own per-strike implied volatility, so two
builders never disagree about what the same chain is worth.
"""

from __future__ import annotations

from jarvis.trading.models import Strategy, StrategyLeg, StrategyType
from jarvis.trading.options_analysis_agent.greeks import (
    black_scholes_greeks,
    black_scholes_price,
    probability_above,
    probability_price_within,
)
from jarvis.trading.options_analysis_agent.provider import RawOptionQuote, RawOptionsChain

DEFAULT_WIDTH = 50.0
CREDIT_SHORT_DELTA_TARGET = 0.25
CONDOR_SHORT_DELTA_TARGET = 0.16
DEBIT_LONG_DELTA_TARGET = 0.45
DEBIT_SHORT_DELTA_TARGET = 0.20


def _quotes_for(chain: RawOptionsChain, expiration: str, option_type: str) -> list[RawOptionQuote]:
    quotes = [q for q in chain.at_expiration(expiration) if q.option_type == option_type]
    if not quotes:
        raise ValueError(f"no {option_type} quotes for expiration {expiration}")
    return sorted(quotes, key=lambda q: q.strike)


def _price(quote: RawOptionQuote, *, spot: float, risk_free_rate: float) -> float:
    return black_scholes_price(
        spot=spot,
        strike=quote.strike,
        days_to_expiration=quote.days_to_expiration,
        volatility=quote.implied_volatility,
        option_type=quote.option_type,
        risk_free_rate=risk_free_rate,
    )


def _delta(quote: RawOptionQuote, *, spot: float, risk_free_rate: float) -> float:
    return black_scholes_greeks(
        spot=spot,
        strike=quote.strike,
        days_to_expiration=quote.days_to_expiration,
        volatility=quote.implied_volatility,
        option_type=quote.option_type,
        risk_free_rate=risk_free_rate,
    ).delta


def _nearest_by_delta(
    quotes: list[RawOptionQuote], *, spot: float, target_abs_delta: float, risk_free_rate: float
) -> RawOptionQuote:
    return min(
        quotes,
        key=lambda q: abs(
            abs(_delta(q, spot=spot, risk_free_rate=risk_free_rate)) - target_abs_delta
        ),
    )


def _nearest_by_strike(quotes: list[RawOptionQuote], *, target_strike: float) -> RawOptionQuote:
    return min(quotes, key=lambda q: abs(q.strike - target_strike))


def _credit_vertical(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    option_type: str,
    strategy_type: StrategyType,
    short_is_below_spot: bool,
    width: float,
    short_delta_target: float,
    risk_free_rate: float,
) -> Strategy:
    """A short vertical for premium: sell the near strike, buy further OTM
    for defined risk. Bull put spread and bear call spread are the same
    shape, mirrored — a bull put spread sells a put below spot; a bear call
    spread sells a call above spot.
    """
    quotes = _quotes_for(chain, expiration, option_type)
    short = _nearest_by_delta(
        quotes, spot=spot, target_abs_delta=short_delta_target, risk_free_rate=risk_free_rate
    )
    target_long_strike = short.strike - width if short_is_below_spot else short.strike + width
    long_leg = _nearest_by_strike(quotes, target_strike=target_long_strike)
    if long_leg.strike == short.strike:
        raise ValueError("not enough distinct strikes in the chain for this spread width")

    short_price = _price(short, spot=spot, risk_free_rate=risk_free_rate)
    long_price = _price(long_leg, spot=spot, risk_free_rate=risk_free_rate)
    credit = round(short_price - long_price, 2)
    if credit <= 0:
        raise ValueError("credit spread priced non-positive; strikes may be too close or inverted")

    actual_width = abs(short.strike - long_leg.strike)
    max_profit = round(credit * 100, 2)
    max_loss = round((actual_width - credit) * 100, 2)
    short_delta = _delta(short, spot=spot, risk_free_rate=risk_free_rate)
    probability_of_profit = round((1 - abs(short_delta)) * 100, 2)
    risk_reward = round(max_profit / max_loss, 4) if max_loss > 0 else 0.0

    label = "Put" if option_type == "put" else "Call"
    entry = f"Sell SPX {short.strike:.0f} {label} / Buy SPX {long_leg.strike:.0f} {label}"
    legs = [
        StrategyLeg(action="sell", option_type=option_type, strike=short.strike),
        StrategyLeg(action="buy", option_type=option_type, strike=long_leg.strike),
    ]
    return Strategy(
        strategy_type=strategy_type,
        legs=legs,
        entry=entry,
        expiration=expiration,
        days_to_expiration=short.days_to_expiration,
        credit=credit,
        max_profit=max_profit,
        max_loss=max_loss,
        probability_of_profit=probability_of_profit,
        risk_reward_ratio=risk_reward,
    )


def bull_put_spread(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    width: float = DEFAULT_WIDTH,
    short_delta_target: float = CREDIT_SHORT_DELTA_TARGET,
    risk_free_rate: float = 0.05,
) -> Strategy:
    return _credit_vertical(
        chain=chain,
        expiration=expiration,
        spot=spot,
        option_type="put",
        strategy_type=StrategyType.BULL_PUT_SPREAD,
        short_is_below_spot=True,
        width=width,
        short_delta_target=short_delta_target,
        risk_free_rate=risk_free_rate,
    )


def bear_call_spread(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    width: float = DEFAULT_WIDTH,
    short_delta_target: float = CREDIT_SHORT_DELTA_TARGET,
    risk_free_rate: float = 0.05,
) -> Strategy:
    return _credit_vertical(
        chain=chain,
        expiration=expiration,
        spot=spot,
        option_type="call",
        strategy_type=StrategyType.BEAR_CALL_SPREAD,
        short_is_below_spot=False,
        width=width,
        short_delta_target=short_delta_target,
        risk_free_rate=risk_free_rate,
    )


def _debit_vertical(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    option_type: str,
    strategy_type: StrategyType,
    short_direction: float,
    width: float,
    long_delta_target: float,
    short_delta_target: float,
    expected_move_points: float,
    risk_free_rate: float,
) -> Strategy:
    """A long vertical paid for with debit: buy the closer-to-the-money
    strike, sell the further one to offset cost. Bull call spread and bear
    put spread are this shape, mirrored — but "further OTM" points in
    opposite strike directions for a call (up) and a put (down), which is
    what ``short_direction`` (``+1.0`` or ``-1.0``) encodes.
    """
    quotes = _quotes_for(chain, expiration, option_type)
    long_leg = _nearest_by_delta(
        quotes, spot=spot, target_abs_delta=long_delta_target, risk_free_rate=risk_free_rate
    )
    target_short_strike = long_leg.strike + short_direction * width
    short = _nearest_by_strike(quotes, target_strike=target_short_strike)
    if short.strike == long_leg.strike:
        raise ValueError("not enough distinct strikes in the chain for this spread width")

    long_price = _price(long_leg, spot=spot, risk_free_rate=risk_free_rate)
    short_price = _price(short, spot=spot, risk_free_rate=risk_free_rate)
    debit = round(long_price - short_price, 2)
    if debit <= 0:
        raise ValueError("debit spread priced non-positive; strikes may be inverted")

    actual_width = abs(short.strike - long_leg.strike)
    max_profit = round((actual_width - debit) * 100, 2)
    max_loss = round(debit * 100, 2)

    breakeven = long_leg.strike + debit if option_type == "call" else long_leg.strike - debit
    distance = (breakeven - spot) if option_type == "call" else (spot - breakeven)
    probability_of_profit = round(
        probability_above(distance=distance, std_dev=expected_move_points), 2
    )
    risk_reward = round(max_profit / max_loss, 4) if max_loss > 0 else 0.0

    label = "Call" if option_type == "call" else "Put"
    entry = f"Buy SPX {long_leg.strike:.0f} {label} / Sell SPX {short.strike:.0f} {label}"
    legs = [
        StrategyLeg(action="buy", option_type=option_type, strike=long_leg.strike),
        StrategyLeg(action="sell", option_type=option_type, strike=short.strike),
    ]
    return Strategy(
        strategy_type=strategy_type,
        legs=legs,
        entry=entry,
        expiration=expiration,
        days_to_expiration=long_leg.days_to_expiration,
        debit=debit,
        max_profit=max_profit,
        max_loss=max_loss,
        probability_of_profit=probability_of_profit,
        risk_reward_ratio=risk_reward,
    )


def bull_call_spread(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    expected_move_points: float,
    width: float = DEFAULT_WIDTH,
    long_delta_target: float = DEBIT_LONG_DELTA_TARGET,
    short_delta_target: float = DEBIT_SHORT_DELTA_TARGET,
    risk_free_rate: float = 0.05,
) -> Strategy:
    return _debit_vertical(
        chain=chain,
        expiration=expiration,
        spot=spot,
        option_type="call",
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        short_direction=1.0,
        width=width,
        long_delta_target=long_delta_target,
        short_delta_target=short_delta_target,
        expected_move_points=expected_move_points,
        risk_free_rate=risk_free_rate,
    )


def bear_put_spread(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    expected_move_points: float,
    width: float = DEFAULT_WIDTH,
    long_delta_target: float = DEBIT_LONG_DELTA_TARGET,
    short_delta_target: float = DEBIT_SHORT_DELTA_TARGET,
    risk_free_rate: float = 0.05,
) -> Strategy:
    return _debit_vertical(
        chain=chain,
        expiration=expiration,
        spot=spot,
        option_type="put",
        strategy_type=StrategyType.BEAR_PUT_SPREAD,
        short_direction=-1.0,
        width=width,
        long_delta_target=long_delta_target,
        short_delta_target=short_delta_target,
        expected_move_points=expected_move_points,
        risk_free_rate=risk_free_rate,
    )


def iron_condor(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    width: float = DEFAULT_WIDTH,
    short_delta_target: float = CONDOR_SHORT_DELTA_TARGET,
    risk_free_rate: float = 0.05,
) -> Strategy:
    """A put credit spread and a call credit spread sold together: profits
    if price stays between the two short strikes through expiration."""
    put_side = _credit_vertical(
        chain=chain,
        expiration=expiration,
        spot=spot,
        option_type="put",
        strategy_type=StrategyType.IRON_CONDOR,
        short_is_below_spot=True,
        width=width,
        short_delta_target=short_delta_target,
        risk_free_rate=risk_free_rate,
    )
    call_side = _credit_vertical(
        chain=chain,
        expiration=expiration,
        spot=spot,
        option_type="call",
        strategy_type=StrategyType.IRON_CONDOR,
        short_is_below_spot=False,
        width=width,
        short_delta_target=short_delta_target,
        risk_free_rate=risk_free_rate,
    )
    credit = round(put_side.credit + call_side.credit, 2)
    max_profit = round(credit * 100, 2)
    # Only one side is ever breached at expiration, so the worst case is the
    # wider wing's width minus the *combined* credit from both sides.
    put_width = abs(put_side.legs[0].strike - put_side.legs[1].strike)
    call_width = abs(call_side.legs[0].strike - call_side.legs[1].strike)
    max_loss = round((max(put_width, call_width) - credit) * 100, 2)
    probability_of_profit = round(
        put_side.probability_of_profit + call_side.probability_of_profit - 100.0, 2
    )
    probability_of_profit = max(0.0, min(100.0, probability_of_profit))
    risk_reward = round(max_profit / max_loss, 4) if max_loss > 0 else 0.0

    return Strategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[*put_side.legs, *call_side.legs],
        entry=f"{put_side.entry} + {call_side.entry}",
        expiration=expiration,
        days_to_expiration=put_side.days_to_expiration,
        credit=credit,
        max_profit=max_profit,
        max_loss=max_loss,
        probability_of_profit=probability_of_profit,
        risk_reward_ratio=risk_reward,
    )


def butterfly(
    *,
    chain: RawOptionsChain,
    expiration: str,
    spot: float,
    expected_move_points: float,
    wing_width: float = DEFAULT_WIDTH,
    risk_free_rate: float = 0.05,
) -> Strategy:
    """A long call butterfly centred at-the-money: buy one wing below, sell
    two at the body, buy one wing above. Cheap, defined-risk, and pays out
    only if price pins near the body."""
    calls = _quotes_for(chain, expiration, "call")
    body = _nearest_by_strike(calls, target_strike=spot)
    lower = _nearest_by_strike(calls, target_strike=body.strike - wing_width)
    upper = _nearest_by_strike(calls, target_strike=body.strike + wing_width)
    if lower.strike == body.strike or upper.strike == body.strike:
        raise ValueError("not enough distinct strikes in the chain for this wing width")

    lower_price = _price(lower, spot=spot, risk_free_rate=risk_free_rate)
    body_price = _price(body, spot=spot, risk_free_rate=risk_free_rate)
    upper_price = _price(upper, spot=spot, risk_free_rate=risk_free_rate)
    debit = round(lower_price + upper_price - 2 * body_price, 2)
    if debit <= 0:
        raise ValueError("butterfly priced non-positive; strikes may be malformed")

    actual_width = min(body.strike - lower.strike, upper.strike - body.strike)
    max_profit = round((actual_width - debit) * 100, 2)
    max_loss = round(debit * 100, 2)
    probability_of_profit = round(
        probability_price_within(distance=actual_width / 2, std_dev=expected_move_points), 2
    )
    risk_reward = round(max_profit / max_loss, 4) if max_loss > 0 else 0.0

    legs = [
        StrategyLeg(action="buy", option_type="call", strike=lower.strike),
        StrategyLeg(action="sell", option_type="call", strike=body.strike, quantity=2),
        StrategyLeg(action="buy", option_type="call", strike=upper.strike),
    ]
    entry = (
        f"Buy SPX {lower.strike:.0f} Call / Sell 2x SPX {body.strike:.0f} Call / "
        f"Buy SPX {upper.strike:.0f} Call"
    )
    return Strategy(
        strategy_type=StrategyType.BUTTERFLY,
        legs=legs,
        entry=entry,
        expiration=expiration,
        days_to_expiration=body.days_to_expiration,
        debit=debit,
        max_profit=max_profit,
        max_loss=max_loss,
        probability_of_profit=probability_of_profit,
        risk_reward_ratio=risk_reward,
    )
