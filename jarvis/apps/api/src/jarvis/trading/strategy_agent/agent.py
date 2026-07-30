"""Strategy Agent: turns a directional read and an options chain into
concrete, priced strategies for the risk manager to judge."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from jarvis.trading.models import OptionsAnalysis, Strategy, TechnicalAnalysis, Trend
from jarvis.trading.options_analysis_agent.provider import RawOptionsChain
from jarvis.trading.strategy_agent import strategies as build

log = structlog.get_logger(__name__)


class StrategyAgent:
    """Builds every strategy allowed for the current market direction.

    A bullish read tries a credit spread (bull put) and a debit spread
    (bull call) so the risk manager has a genuine choice rather than one
    strategy it can only approve or reject; bearish and neutral reads are
    symmetric. A builder that cannot price against the current chain (an
    illiquid strike, a chain too narrow for the configured width) is
    skipped rather than failing the whole request — a partial slate beats no
    signal at all.
    """

    def generate(
        self,
        *,
        spot: float,
        chain: RawOptionsChain,
        technical_analysis: TechnicalAnalysis,
        options_analysis: OptionsAnalysis,
        risk_free_rate: float = 0.05,
    ) -> list[Strategy]:
        expiration = options_analysis.best_expiration
        expected_move_points = options_analysis.expected_move

        builders: list[Callable[[], Strategy]] = []
        if technical_analysis.trend == Trend.BULLISH:
            builders = [
                lambda: build.bull_put_spread(
                    chain=chain, expiration=expiration, spot=spot, risk_free_rate=risk_free_rate
                ),
                lambda: build.bull_call_spread(
                    chain=chain,
                    expiration=expiration,
                    spot=spot,
                    expected_move_points=expected_move_points,
                    risk_free_rate=risk_free_rate,
                ),
            ]
        elif technical_analysis.trend == Trend.BEARISH:
            builders = [
                lambda: build.bear_call_spread(
                    chain=chain, expiration=expiration, spot=spot, risk_free_rate=risk_free_rate
                ),
                lambda: build.bear_put_spread(
                    chain=chain,
                    expiration=expiration,
                    spot=spot,
                    expected_move_points=expected_move_points,
                    risk_free_rate=risk_free_rate,
                ),
            ]
        else:
            builders = [
                lambda: build.iron_condor(
                    chain=chain, expiration=expiration, spot=spot, risk_free_rate=risk_free_rate
                ),
                lambda: build.butterfly(
                    chain=chain,
                    expiration=expiration,
                    spot=spot,
                    expected_move_points=expected_move_points,
                    risk_free_rate=risk_free_rate,
                ),
            ]

        candidates: list[Strategy] = []
        for builder in builders:
            try:
                candidates.append(builder())
            except ValueError as exc:
                log.debug("strategy_skipped", trend=technical_analysis.trend.value, error=str(exc))
        return candidates
