"""Performance Agent: turns closed trades into a track record."""

from __future__ import annotations

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.trading.database.store import TradingStore
from jarvis.trading.models import (
    PerformanceMetrics,
    StrategyPerformance,
    StrategyType,
    TradeOutcome,
)


class PerformanceAgent:
    def __init__(self, *, account_size_usd: float, clock: Clock = SYSTEM_CLOCK) -> None:
        self._account_size_usd = account_size_usd
        self._clock = clock

    async def compute(self, store: TradingStore, *, limit: int = 5000) -> PerformanceMetrics:
        results = await store.list_trade_results(limit=limit)
        results = sorted(results, key=lambda r: r.closed_at)  # oldest first for the equity curve

        total = len(results)
        wins = sum(1 for r in results if r.outcome == TradeOutcome.WIN)
        losses = sum(1 for r in results if r.outcome == TradeOutcome.LOSS)
        win_rate = round(wins / total * 100, 2) if total else 0.0
        average_return_pct = round(sum(r.pnl_pct for r in results) / total, 2) if total else 0.0

        max_drawdown_pct = 0.0
        if total and self._account_size_usd > 0:
            cumulative = 0.0
            peak = 0.0
            for result in results:
                cumulative += result.pnl_usd
                peak = max(peak, cumulative)
                drawdown = (peak - cumulative) / self._account_size_usd * 100
                max_drawdown_pct = max(max_drawdown_pct, drawdown)
        max_drawdown_pct = round(max_drawdown_pct, 2)

        strategy_totals: dict[StrategyType, dict[str, float]] = {}
        for result in results:
            signal = await store.get_signal(result.signal_id)
            if signal is None:
                continue
            strategy_type = signal.strategy.strategy_type
            bucket = strategy_totals.setdefault(
                strategy_type, {"total": 0, "wins": 0, "losses": 0, "pnl_pct_sum": 0.0}
            )
            bucket["total"] += 1
            bucket["pnl_pct_sum"] += result.pnl_pct
            if result.outcome == TradeOutcome.WIN:
                bucket["wins"] += 1
            elif result.outcome == TradeOutcome.LOSS:
                bucket["losses"] += 1

        strategy_performance = [
            StrategyPerformance(
                strategy_type=strategy_type,
                total=int(bucket["total"]),
                wins=int(bucket["wins"]),
                losses=int(bucket["losses"]),
                win_rate=round(bucket["wins"] / bucket["total"] * 100, 2)
                if bucket["total"]
                else 0.0,
                average_return_pct=(
                    round(bucket["pnl_pct_sum"] / bucket["total"], 2) if bucket["total"] else 0.0
                ),
            )
            for strategy_type, bucket in strategy_totals.items()
        ]

        return PerformanceMetrics(
            total_signals=total,
            winning_signals=wins,
            losing_signals=losses,
            win_rate=win_rate,
            average_return_pct=average_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            strategy_performance=strategy_performance,
            computed_at=self._clock.now(),
        )
