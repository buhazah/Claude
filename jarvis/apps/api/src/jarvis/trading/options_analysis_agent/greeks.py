"""Black-Scholes greeks, IV rank and expected move.

SPX options are European-style and cash-settled, which is exactly the case
Black-Scholes was built for — no early-exercise adjustment needed, unlike
single-stock American options.
"""

from __future__ import annotations

import math

from jarvis.trading.models import OptionGreeks

_SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-(x**2) / 2.0) / _SQRT_2PI


def black_scholes_greeks(
    *,
    spot: float,
    strike: float,
    days_to_expiration: int,
    volatility: float,
    option_type: str,
    risk_free_rate: float = 0.05,
) -> OptionGreeks:
    """Delta, gamma, theta (per day) and vega (per 1 vol point) for one leg."""
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if volatility <= 0:
        raise ValueError("volatility must be positive")
    if days_to_expiration <= 0:
        raise ValueError("days_to_expiration must be positive")
    if option_type not in ("call", "put"):
        raise ValueError(f"unknown option_type: {option_type}")

    t = days_to_expiration / 365.0
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (risk_free_rate + volatility**2 / 2) * t) / (
        volatility * sqrt_t
    )
    d2 = d1 - volatility * sqrt_t

    gamma = _norm_pdf(d1) / (spot * volatility * sqrt_t)
    vega = spot * _norm_pdf(d1) * sqrt_t / 100.0  # per 1 percentage point of IV

    if option_type == "call":
        delta = _norm_cdf(d1)
        theta = (
            -spot * _norm_pdf(d1) * volatility / (2 * sqrt_t)
            - risk_free_rate * strike * math.exp(-risk_free_rate * t) * _norm_cdf(d2)
        ) / 365.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -spot * _norm_pdf(d1) * volatility / (2 * sqrt_t)
            + risk_free_rate * strike * math.exp(-risk_free_rate * t) * _norm_cdf(-d2)
        ) / 365.0

    return OptionGreeks(delta=delta, gamma=gamma, theta=theta, vega=vega)


def iv_rank(current_iv: float, history: list[float]) -> float:
    """Where ``current_iv`` sits in its trailing range, 0-100.

    A flat history (every reading identical, including a single-point one)
    has no range to rank against, so it is reported as the midpoint rather
    than an undefined or arbitrary extreme.
    """
    if not history:
        return 50.0
    lowest, highest = min(history), max(history)
    if highest == lowest:
        return 50.0
    rank = (current_iv - lowest) / (highest - lowest) * 100.0
    return max(0.0, min(100.0, rank))


def expected_move(
    *, spot: float, volatility: float, days_to_expiration: int
) -> tuple[float, float]:
    """One-standard-deviation expected move over the period, as ``(points, pct)``."""
    if days_to_expiration <= 0:
        raise ValueError("days_to_expiration must be positive")
    move = spot * volatility * math.sqrt(days_to_expiration / 365.0)
    return move, (move / spot * 100.0 if spot else 0.0)
