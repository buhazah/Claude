"""Signal Generator Agent: turns an approved strategy into the record and
message that actually reach a subscriber."""

from __future__ import annotations

from jarvis.trading.models import (
    BEARISH_STRATEGIES,
    BULLISH_STRATEGIES,
    MarketSnapshot,
    OptionsAnalysis,
    RiskDecision,
    Signal,
    Strategy,
    TechnicalAnalysis,
    Trend,
)
from jarvis.trading.signal_generator_agent.formatter import render_signal_message

FAVORABLE_IV_RANK_CEILING = 60.0
GOOD_RISK_REWARD = 0.20
GOOD_PROBABILITY = 70.0
STRONG_TECHNICAL_STRENGTH = 40.0


def _direction_for(strategy: Strategy) -> Trend:
    if strategy.strategy_type in BULLISH_STRATEGIES:
        return Trend.BULLISH
    if strategy.strategy_type in BEARISH_STRATEGIES:
        return Trend.BEARISH
    return Trend.NEUTRAL


def _confidence(technical: TechnicalAnalysis, strategy: Strategy) -> int:
    """Blend the technical read's confidence with the strategy's own
    probability of profit into a 1-10 scale, technical-analysis-weighted
    less heavily since it speaks to *direction*, not to this specific
    trade's odds."""
    technical_component = technical.confidence_score / 10.0
    probability_component = strategy.probability_of_profit / 10.0
    blended = technical_component * 0.4 + probability_component * 0.6
    return max(1, min(10, round(blended)))


def _reasons(
    *,
    technical: TechnicalAnalysis,
    options_analysis: OptionsAnalysis,
    strategy: Strategy,
    direction: Trend,
) -> list[str]:
    reasons: list[str] = []
    if technical.trend == direction and technical.strength >= STRONG_TECHNICAL_STRENGTH:
        reasons.append("Trend confirmation")

    if direction == Trend.BULLISH and technical.support_levels:
        reasons.append("Support holding")
    elif direction == Trend.BEARISH and technical.resistance_levels:
        reasons.append("Resistance holding")
    elif direction == Trend.NEUTRAL:
        reasons.append("Range-bound structure")

    if options_analysis.iv_rank <= FAVORABLE_IV_RANK_CEILING:
        reasons.append("Favorable IV")

    if (
        strategy.risk_reward_ratio >= GOOD_RISK_REWARD
        or strategy.probability_of_profit >= GOOD_PROBABILITY
    ):
        reasons.append("Positive risk/reward")

    if not reasons:
        reasons.append("Risk-managed setup within defined parameters")
    return reasons


class SignalGeneratorAgent:
    def create(
        self,
        *,
        market: MarketSnapshot,
        technical_analysis: TechnicalAnalysis,
        options_analysis: OptionsAnalysis,
        strategy: Strategy,
        risk_decision: RiskDecision,
    ) -> Signal:
        if not risk_decision.approved:
            raise ValueError("cannot generate a signal for a strategy the risk manager rejected")

        direction = _direction_for(strategy)
        signal = Signal(
            timestamp=market.timestamp,
            market_direction=direction,
            strategy=strategy,
            confidence=_confidence(technical_analysis, strategy),
            reasons=_reasons(
                technical=technical_analysis,
                options_analysis=options_analysis,
                strategy=strategy,
                direction=direction,
            ),
            risk_level=options_analysis.risk_level,
        )
        signal.message = render_signal_message(signal)
        return signal
