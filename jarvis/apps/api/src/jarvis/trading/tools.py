"""Wires the trading pipeline into Jarvis's tool registry.

Each method below is one workflow-step tool. They read whatever they need
from the durable :class:`~jarvis.trading.database.store.TradingStore` rather
than from a previous step's raw output, because the pipeline's intermediate
values (a :class:`TechnicalAnalysis`, a list of candidate strategies, a
:class:`RiskDecision`) are typed Python objects, and the workflow engine's
step-to-step data path is a string-templated JSON context built for chaining
LLM agent turns — not for round-tripping nested Pydantic models. A tool that
re-derives its input from durable state is also idempotent, which a
step in an automated, scheduled pipeline should be regardless.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import structlog

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.tools.registry import Permission, ToolRegistry
from jarvis.trading.config import TradingSettings
from jarvis.trading.database.store import TradingStore
from jarvis.trading.market_data_agent.agent import MarketDataAgent
from jarvis.trading.market_data_agent.history import fetch_price_bars
from jarvis.trading.market_data_agent.provider import MarketDataProvider
from jarvis.trading.models import OptionsSnapshot, SignalStatus, TradeOutcome, TradeResult
from jarvis.trading.monitoring import (
    evaluate_open_position,
    expiration_status,
    settle_at_expiration,
)
from jarvis.trading.options_analysis_agent.agent import OptionsAnalysisAgent
from jarvis.trading.options_analysis_agent.provider import OptionsDataProvider
from jarvis.trading.performance_agent.agent import PerformanceAgent
from jarvis.trading.risk_manager_agent.agent import RiskManagerAgent
from jarvis.trading.signal_generator_agent.agent import SignalGeneratorAgent
from jarvis.trading.strategy_agent.agent import StrategyAgent
from jarvis.trading.technical_analysis_agent.agent import MIN_BARS, TechnicalAnalysisAgent
from jarvis.trading.telegram_agent.bot import TelegramBot

log = structlog.get_logger(__name__)

TOOL_NAMESPACE = "trading"


@dataclass(slots=True)
class TradingTools:
    settings: TradingSettings
    store: TradingStore
    market_data_provider: MarketDataProvider
    options_data_provider: OptionsDataProvider
    market_data_agent: MarketDataAgent
    technical_agent: TechnicalAnalysisAgent
    options_agent: OptionsAnalysisAgent
    strategy_agent: StrategyAgent
    risk_agent: RiskManagerAgent
    signal_agent: SignalGeneratorAgent
    performance_agent: PerformanceAgent
    telegram_bot: TelegramBot | None = None
    clock: Clock = SYSTEM_CLOCK

    async def collect_market_data(self) -> dict[str, Any]:
        """Stage 1-2 of the market scan: collect the broad market and the
        options chain, and persist both."""
        snapshot = await self.market_data_agent.collect()
        await self.store.save_market_snapshot(snapshot)

        chain = await self.options_data_provider.fetch_chain(
            underlying=snapshot.symbol, spot=snapshot.price, now=snapshot.timestamp
        )
        analysis = self.options_agent.analyze(chain)
        await self.store.save_options_snapshot(
            OptionsSnapshot(
                timestamp=snapshot.timestamp, underlying=snapshot.symbol, analysis=analysis
            )
        )
        return {
            "price": snapshot.price,
            "vix": snapshot.vix,
            "trend": snapshot.trend.value,
            "market_condition": snapshot.market_condition.value,
            "iv_rank": analysis.iv_rank,
            "best_expiration": analysis.best_expiration,
        }

    async def generate_signal(self) -> dict[str, Any]:
        """Stage 3-6: analyse, propose strategies, apply risk, publish."""
        snapshot = await self.store.latest_market_snapshot()
        if snapshot is None:
            return {"approved": False, "reason": "no market data collected yet"}

        bars = await fetch_price_bars(
            self.market_data_provider, now=snapshot.timestamp, count=MIN_BARS
        )
        technical = self.technical_agent.analyze(bars)

        chain = await self.options_data_provider.fetch_chain(
            underlying=snapshot.symbol, spot=snapshot.price, now=snapshot.timestamp
        )
        options_analysis = self.options_agent.analyze(chain)

        candidates = self.strategy_agent.generate(
            spot=snapshot.price,
            chain=chain,
            technical_analysis=technical,
            options_analysis=options_analysis,
        )
        if not candidates:
            return {"approved": False, "reason": "no strategy could be priced against this chain"}

        signals_today = await self.store.signals_today(now=snapshot.timestamp)
        consecutive_losses = await self.store.consecutive_losses()
        best = self.risk_agent.best_approved(
            candidates,
            market=snapshot,
            options_analysis=options_analysis,
            signals_today=signals_today,
            consecutive_losses=consecutive_losses,
        )
        if best is None:
            return {"approved": False, "reason": "risk manager rejected every candidate"}

        strategy, decision = best
        signal = self.signal_agent.create(
            market=snapshot,
            technical_analysis=technical,
            options_analysis=options_analysis,
            strategy=strategy,
            risk_decision=decision,
        )
        await self.store.save_signal(signal)

        sent = 0
        if self.telegram_bot is not None:
            sent = await self.telegram_bot.broadcast(signal.message)

        return {
            "approved": True,
            "signal_id": signal.id,
            "strategy": strategy.strategy_type.value,
            "confidence": signal.confidence,
            "probability_of_profit": strategy.probability_of_profit,
            "broadcast_to": sent,
        }

    async def daily_report(self) -> dict[str, Any]:
        """A pre-open market overview, broadcast to every subscriber."""
        snapshot = await self.market_data_agent.collect()
        await self.store.save_market_snapshot(snapshot)

        chain = await self.options_data_provider.fetch_chain(
            underlying=snapshot.symbol, spot=snapshot.price, now=snapshot.timestamp
        )
        analysis = self.options_agent.analyze(chain)

        text = (
            "\U0001f4ca Hermes Daily Report\n\n"
            f"SPX: {snapshot.price:.2f}\n"
            f"VIX: {snapshot.vix:.2f} ({analysis.volatility_state.value})\n"
            f"Trend: {snapshot.trend.value}\n"
            f"Expected move ({analysis.best_expiration}): "
            f"±{analysis.expected_move:.0f} pts ({analysis.expected_move_pct:.1f}%)\n"
            f"Positioning: {analysis.market_positioning}"
        )
        sent = await self.telegram_bot.broadcast(text) if self.telegram_bot is not None else 0
        return {"sent_to": sent, "price": snapshot.price, "vix": snapshot.vix}

    async def monitor_signals(self) -> dict[str, Any]:
        """Track every open signal: expiration settlement, or an early
        target/stop against the current price."""
        active = await self.store.list_signals(status=SignalStatus.ACTIVE, limit=1000)
        if not active:
            return {"checked": 0, "closed": 0}

        snapshot = await self.market_data_agent.collect()
        await self.store.save_market_snapshot(snapshot)

        closed = 0
        for signal in active:
            expired = date.fromisoformat(signal.strategy.expiration) <= snapshot.timestamp.date()
            status: SignalStatus
            if expired:
                result = settle_at_expiration(
                    signal.strategy,
                    signal_id=signal.id,
                    spot_at_expiration=snapshot.price,
                    clock=self.clock,
                )
                status = expiration_status(result.outcome)
            else:
                open_status = evaluate_open_position(
                    signal.strategy,
                    spot=snapshot.price,
                    target_fraction=self.settings.target_profit_width_fraction,
                    stop_fraction=self.settings.stop_loss_width_fraction,
                )
                if open_status is None:
                    continue
                status = open_status
                hit_target = status == SignalStatus.TARGET_HIT
                result = TradeResult(
                    signal_id=signal.id,
                    outcome=TradeOutcome.WIN if hit_target else TradeOutcome.LOSS,
                    pnl_usd=signal.strategy.max_profit if hit_target else -signal.strategy.max_loss,
                    pnl_pct=100.0 if hit_target else -100.0,
                    closed_at=self.clock.now(),
                )

            await self.store.save_trade_result(result)
            await self.store.update_signal_status(signal.id, status=status, result=result.outcome)
            closed += 1
            if self.telegram_bot is not None:
                await self.telegram_bot.broadcast(
                    f"Signal update — {signal.strategy.strategy_type.value}: {status.value} "
                    f"({result.outcome.value}, ${result.pnl_usd:.0f})"
                )

        return {"checked": len(active), "closed": closed}

    async def compute_performance(self) -> dict[str, Any]:
        metrics = await self.performance_agent.compute(self.store)
        await self.store.save_performance_metrics(metrics)
        return {
            "total_signals": metrics.total_signals,
            "win_rate": metrics.win_rate,
            "max_drawdown_pct": metrics.max_drawdown_pct,
        }


def register_trading_tools(registry: ToolRegistry, tools: TradingTools) -> None:
    registry.register(
        "trading_collect_market_data",
        "Collect SPX market and options data and store a snapshot.",
        tools.collect_market_data,
        permission=Permission.SAFE,
        namespace=TOOL_NAMESPACE,
    )
    registry.register(
        "trading_generate_signal",
        "Analyse the latest market data, propose strategies, apply risk "
        "management, and publish an approved signal if any candidate clears every rule.",
        tools.generate_signal,
        permission=Permission.SENSITIVE,
        namespace=TOOL_NAMESPACE,
    )
    registry.register(
        "trading_daily_report",
        "Compose and broadcast a pre-open market overview.",
        tools.daily_report,
        permission=Permission.SENSITIVE,
        namespace=TOOL_NAMESPACE,
    )
    registry.register(
        "trading_monitor_signals",
        "Check every active signal for expiration, target or stop, and settle it.",
        tools.monitor_signals,
        permission=Permission.SENSITIVE,
        namespace=TOOL_NAMESPACE,
    )
    registry.register(
        "trading_compute_performance",
        "Recompute win rate, average return, drawdown and per-strategy performance.",
        tools.compute_performance,
        permission=Permission.SAFE,
        namespace=TOOL_NAMESPACE,
    )
