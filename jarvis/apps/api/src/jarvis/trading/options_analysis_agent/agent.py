"""Options Analysis Agent: reads an SPX options chain and summarises it into
the shape the strategy agent builds trades from."""

from __future__ import annotations

from jarvis.trading.models import OptionsAnalysis, RiskLevel, StrikeMetrics, VolatilityState
from jarvis.trading.options_analysis_agent.greeks import (
    black_scholes_greeks,
    expected_move,
    iv_rank,
)
from jarvis.trading.options_analysis_agent.provider import RawOptionQuote, RawOptionsChain

TARGET_DTE = 21  # the sweet spot for premium-selling strategies: past the
# theta-decay knee, short of weekly gamma risk
MAX_IMPORTANT_STRIKES = 6


def _pick_expiration(chain: RawOptionsChain) -> str:
    expirations = chain.expirations()
    if not expirations:
        raise ValueError("options chain has no expirations")
    by_dte = {
        e: next(q.days_to_expiration for q in chain.quotes if q.expiration == e)
        for e in expirations
    }
    return min(expirations, key=lambda e: abs(by_dte[e] - TARGET_DTE))


def _atm_iv(quotes: list[RawOptionQuote], spot: float) -> float:
    nearest = min(quotes, key=lambda q: abs(q.strike - spot))
    at_strike = [q for q in quotes if q.strike == nearest.strike]
    return sum(q.implied_volatility for q in at_strike) / len(at_strike)


def _volatility_state(rank: float) -> VolatilityState:
    if rank < 25:
        return VolatilityState.LOW
    if rank < 50:
        return VolatilityState.NORMAL
    if rank < 80:
        return VolatilityState.ELEVATED
    return VolatilityState.EXTREME


def _risk_level(rank: float, put_call_ratio: float) -> RiskLevel:
    if rank >= 80 or put_call_ratio >= 1.5 or put_call_ratio <= 0.5:
        return RiskLevel.HIGH
    if rank >= 50:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _positioning(put_call_ratio: float) -> str:
    if put_call_ratio >= 1.2:
        return "put-heavy positioning (hedging or bearish skew)"
    if put_call_ratio <= 0.8:
        return "call-heavy positioning (bullish skew)"
    return "balanced put/call positioning"


class OptionsAnalysisAgent:
    def analyze(self, chain: RawOptionsChain) -> OptionsAnalysis:
        expiration = _pick_expiration(chain)
        quotes = chain.at_expiration(expiration)
        if not quotes:
            raise ValueError(f"no quotes for expiration {expiration}")
        dte = quotes[0].days_to_expiration

        iv = _atm_iv(quotes, chain.spot)
        rank = iv_rank(iv, chain.iv_history)

        call_volume = sum(q.volume for q in quotes if q.option_type == "call")
        put_volume = sum(q.volume for q in quotes if q.option_type == "put")
        put_call_ratio = round(put_volume / call_volume, 3) if call_volume else float("inf")

        move_points, move_pct = expected_move(
            spot=chain.spot, volatility=iv, days_to_expiration=dte
        )

        important = sorted(quotes, key=lambda q: q.open_interest, reverse=True)[
            :MAX_IMPORTANT_STRIKES
        ]
        strike_metrics = [
            StrikeMetrics(
                strike=q.strike,
                option_type=q.option_type,
                implied_volatility=q.implied_volatility,
                open_interest=q.open_interest,
                volume=q.volume,
                greeks=black_scholes_greeks(
                    spot=chain.spot,
                    strike=q.strike,
                    days_to_expiration=q.days_to_expiration,
                    volatility=q.implied_volatility,
                    option_type=q.option_type,
                    risk_free_rate=chain.risk_free_rate,
                ),
            )
            for q in important
        ]

        return OptionsAnalysis(
            volatility_state=_volatility_state(rank),
            best_expiration=expiration,
            important_strikes=strike_metrics,
            market_positioning=_positioning(put_call_ratio),
            risk_level=_risk_level(rank, put_call_ratio),
            iv=round(iv, 4),
            iv_rank=round(rank, 2),
            put_call_ratio=put_call_ratio,
            expected_move=round(move_points, 2),
            expected_move_pct=round(move_pct, 3),
        )
