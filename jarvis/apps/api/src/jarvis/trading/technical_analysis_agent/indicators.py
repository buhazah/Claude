"""Pure technical indicator math. No I/O, no state — every function is a
deterministic transform of a price history, which is what lets the agent
above it be tested against fixed, hand-checkable series."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class PriceBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _require(values: Sequence[object], minimum: int, what: str) -> None:
    if len(values) < minimum:
        raise ValueError(f"{what} needs at least {minimum} values, got {len(values)}")


def sma(values: Sequence[float], period: int) -> float:
    _require(values, period, "sma")
    return sum(values[-period:]) / period


def ema_series(values: Sequence[float], period: int) -> list[float]:
    """The full EMA series, seeded from the first value.

    Returned in full, not just the latest point, because MACD needs the
    series of an EMA to compute the signal line as an EMA of it.
    """
    if not values:
        return []
    k = 2.0 / (period + 1)
    series = [values[0]]
    for price in values[1:]:
        series.append(price * k + series[-1] * (1 - k))
    return series


def ema(values: Sequence[float], period: int) -> float:
    _require(values, period, "ema")
    return ema_series(values, period)[-1]


def rsi(values: Sequence[float], period: int = 14) -> float:
    _require(values, period + 1, "rsi")
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_gain == 0 and avg_loss == 0:
        return 50.0  # no movement at all: neither overbought nor oversold
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    values: Sequence[float], *, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float, float, float]:
    """Returns ``(macd_line, signal_line, histogram)``."""
    _require(values, slow + signal, "macd")
    fast_series = ema_series(values, fast)
    slow_series = ema_series(values, slow)
    macd_line_series = [f - s for f, s in zip(fast_series, slow_series, strict=True)]
    signal_series = ema_series(macd_line_series, signal)
    macd_value = macd_line_series[-1]
    signal_value = signal_series[-1]
    return macd_value, signal_value, macd_value - signal_value


def vwap(bars: Sequence[PriceBar]) -> float:
    _require(bars, 1, "vwap")
    cum_pv = 0.0
    cum_volume = 0.0
    for bar in bars:
        typical_price = (bar.high + bar.low + bar.close) / 3
        cum_pv += typical_price * bar.volume
        cum_volume += bar.volume
    if cum_volume == 0:
        raise ValueError("vwap needs nonzero volume")
    return cum_pv / cum_volume


def momentum(values: Sequence[float], period: int = 10) -> float:
    """Rate of change over ``period`` bars, as a percentage."""
    _require(values, period + 1, "momentum")
    reference = values[-1 - period]
    if reference == 0:
        raise ValueError("momentum needs a nonzero reference price")
    return (values[-1] - reference) / reference * 100.0


def _cluster(levels: list[float], *, tolerance: float = 0.0015) -> list[float]:
    """Merge levels within ``tolerance`` of each other into one.

    Raw pivot detection produces near-duplicate levels a few points apart —
    every bar that grazes the same zone counts as its own pivot. Clustering
    is what turns that into the handful of levels a trader would actually
    mark on a chart.
    """
    clustered: list[float] = []
    for level in sorted(levels):
        if clustered and abs(level - clustered[-1]) / clustered[-1] < tolerance:
            continue
        clustered.append(level)
    return clustered


def support_resistance(
    bars: Sequence[PriceBar], *, lookback: int = 40, window: int = 2, max_levels: int = 3
) -> tuple[list[float], list[float]]:
    """Local-pivot support and resistance levels from recent price bars.

    A bar is a pivot low/high when it is the lowest/highest in a window of
    ``2 * window + 1`` bars centred on it. Returns ``(supports, resistances)``,
    each sorted and capped at ``max_levels``, nearest to price first for
    resistance and highest-first (i.e. also nearest to price) for support.
    """
    recent = list(bars[-lookback:]) if len(bars) >= lookback else list(bars)
    supports: list[float] = []
    resistances: list[float] = []
    for i in range(window, len(recent) - window):
        segment = recent[i - window : i + window + 1]
        if recent[i].low == min(b.low for b in segment):
            supports.append(recent[i].low)
        if recent[i].high == max(b.high for b in segment):
            resistances.append(recent[i].high)

    clustered_supports = _cluster(supports)[-max_levels:]
    clustered_resistances = _cluster(resistances)[:max_levels]
    return clustered_supports, clustered_resistances
