"""Risk Manager Agent: veto power over every signal.

Every rule here is a hard threshold from :class:`~jarvis.trading.config.TradingSettings`,
not a model's judgement — a trading system that can talk itself past its own
risk limits does not have risk limits.
"""

from __future__ import annotations

import structlog

from jarvis.trading.config import TradingSettings
from jarvis.trading.models import MarketSnapshot, OptionsAnalysis, RiskDecision, Strategy
from jarvis.trading.risk_manager_agent import rules

log = structlog.get_logger(__name__)


class RiskManagerAgent:
    def __init__(self, settings: TradingSettings | None = None) -> None:
        self._settings = settings or TradingSettings()

    def evaluate(
        self,
        *,
        strategy: Strategy,
        market: MarketSnapshot,
        options_analysis: OptionsAnalysis,
        signals_today: int,
        consecutive_losses: int,
        contracts: int = 1,
    ) -> RiskDecision:
        settings = self._settings
        checks = [
            rules.check_probability_of_profit(strategy, minimum=settings.min_probability_of_profit),
            rules.check_risk_per_trade(
                strategy,
                contracts=contracts,
                account_size_usd=settings.account_size_usd,
                max_risk_pct=settings.max_risk_per_trade_pct,
            ),
            rules.check_daily_signal_limit(
                signals_today=signals_today, max_daily_signals=settings.max_daily_signals
            ),
            rules.check_consecutive_losses(
                consecutive_losses=consecutive_losses,
                max_consecutive_losses=settings.max_consecutive_losses,
            ),
            rules.check_economic_event_blackout(market),
            rules.check_volatility(options_analysis, max_iv_rank=settings.max_iv_rank_for_entry),
            rules.check_risk_reward(strategy, minimum_ratio=settings.min_risk_reward_ratio),
        ]

        failed = [c for c in checks if not c.passed]
        approved = not failed
        reason = (
            "all risk checks passed"
            if approved
            else "; ".join(f"{c.rule} failed ({c.detail})" for c in failed)
        )
        decision = RiskDecision(approved=approved, reason=reason, checks=checks)
        log.info(
            "risk_decision",
            approved=approved,
            strategy=strategy.strategy_type.value,
            failed_rules=[c.rule for c in failed],
        )
        return decision

    def best_approved(
        self,
        strategies: list[Strategy],
        *,
        market: MarketSnapshot,
        options_analysis: OptionsAnalysis,
        signals_today: int,
        consecutive_losses: int,
        contracts: int = 1,
    ) -> tuple[Strategy, RiskDecision] | None:
        """Evaluate every candidate and return the highest-POP approved one.

        The strategy agent proposes more than one candidate for a given
        trend; the risk manager, not the strategy agent, decides which one
        actually goes out, because "which is safest" is a risk question.
        """
        best: tuple[Strategy, RiskDecision] | None = None
        for strategy in strategies:
            decision = self.evaluate(
                strategy=strategy,
                market=market,
                options_analysis=options_analysis,
                signals_today=signals_today,
                consecutive_losses=consecutive_losses,
                contracts=contracts,
            )
            if not decision.approved:
                continue
            if best is None or strategy.probability_of_profit > best[0].probability_of_profit:
                best = (strategy, decision)
        return best
