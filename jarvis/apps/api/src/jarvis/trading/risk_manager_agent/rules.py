"""Individual risk rules. Each is a pure function from state to a
:class:`~jarvis.trading.models.RiskCheck` — no rule can see another's
result, which is what keeps "why was this rejected" a simple list rather
than a chain of reasoning to untangle."""

from __future__ import annotations

from jarvis.trading.models import (
    MarketSnapshot,
    OptionsAnalysis,
    RiskCheck,
    Strategy,
    VolatilityState,
)


def check_probability_of_profit(strategy: Strategy, *, minimum: float) -> RiskCheck:
    passed = strategy.probability_of_profit >= minimum
    return RiskCheck(
        rule="probability_of_profit",
        passed=passed,
        detail=f"{strategy.probability_of_profit:.1f}% (minimum {minimum:.1f}%)",
    )


def check_risk_per_trade(
    strategy: Strategy, *, contracts: int, account_size_usd: float, max_risk_pct: float
) -> RiskCheck:
    if account_size_usd <= 0:
        return RiskCheck(
            rule="risk_per_trade", passed=False, detail="account size is not configured"
        )
    risk_pct = strategy.max_loss * contracts / account_size_usd * 100
    passed = risk_pct <= max_risk_pct
    return RiskCheck(
        rule="risk_per_trade",
        passed=passed,
        detail=f"{risk_pct:.2f}% of account (maximum {max_risk_pct:.2f}%)",
    )


def check_daily_signal_limit(*, signals_today: int, max_daily_signals: int) -> RiskCheck:
    passed = signals_today < max_daily_signals
    return RiskCheck(
        rule="daily_signal_limit",
        passed=passed,
        detail=f"{signals_today} signals already issued today (maximum {max_daily_signals})",
    )


def check_consecutive_losses(*, consecutive_losses: int, max_consecutive_losses: int) -> RiskCheck:
    passed = consecutive_losses < max_consecutive_losses
    return RiskCheck(
        rule="consecutive_losses",
        passed=passed,
        detail=f"{consecutive_losses} consecutive losses (halts at {max_consecutive_losses})",
    )


def check_economic_event_blackout(market: MarketSnapshot) -> RiskCheck:
    passed = not market.economic_events
    detail = (
        "no major economic event flagged"
        if passed
        else f"blackout: {', '.join(market.economic_events)}"
    )
    return RiskCheck(rule="economic_event_blackout", passed=passed, detail=detail)


def check_volatility(options_analysis: OptionsAnalysis, *, max_iv_rank: float) -> RiskCheck:
    extreme = options_analysis.volatility_state == VolatilityState.EXTREME
    over_rank = options_analysis.iv_rank > max_iv_rank
    passed = not (extreme or over_rank)
    detail = (
        f"iv_rank {options_analysis.iv_rank:.1f} ({options_analysis.volatility_state.value}), "
        f"maximum {max_iv_rank:.1f}"
    )
    return RiskCheck(rule="volatility", passed=passed, detail=detail)


def check_risk_reward(strategy: Strategy, *, minimum_ratio: float) -> RiskCheck:
    passed = strategy.risk_reward_ratio >= minimum_ratio
    return RiskCheck(
        rule="risk_reward_ratio",
        passed=passed,
        detail=f"{strategy.risk_reward_ratio:.3f} (minimum {minimum_ratio:.3f})",
    )
