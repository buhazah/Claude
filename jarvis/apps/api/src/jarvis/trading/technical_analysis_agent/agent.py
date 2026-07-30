"""Technical Analysis Agent: turns a price history into a directional read."""

from __future__ import annotations

from jarvis.trading.models import MovingAverages, TechnicalAnalysis, Trend
from jarvis.trading.technical_analysis_agent import indicators as ind
from jarvis.trading.technical_analysis_agent.indicators import PriceBar

MIN_BARS = 200  # enough for a 200-period SMA, the longest indicator here

BULLISH_THRESHOLD = 0.15
BEARISH_THRESHOLD = -0.15


def _score(value: float, *, scale: float) -> float:
    """Clip a raw indicator reading to ``[-1, 1]``."""
    return max(-1.0, min(1.0, value / scale))


class TechnicalAnalysisAgent:
    """Computes moving averages, RSI, MACD, VWAP, support/resistance and a
    blended trend/strength/confidence read from a price history."""

    def analyze(self, bars: list[PriceBar]) -> TechnicalAnalysis:
        if len(bars) < MIN_BARS:
            raise ValueError(f"technical analysis needs at least {MIN_BARS} bars, got {len(bars)}")

        closes = [b.close for b in bars]
        price = closes[-1]

        mas = MovingAverages(
            sma_20=ind.sma(closes, 20),
            sma_50=ind.sma(closes, 50),
            sma_200=ind.sma(closes, 200),
            ema_12=ind.ema(closes, 12),
            ema_26=ind.ema(closes, 26),
        )
        rsi_value = ind.rsi(closes)
        macd_value, macd_signal, macd_hist = ind.macd(closes)
        vwap_value = ind.vwap(bars)
        momentum_value = ind.momentum(closes)
        supports, resistances = ind.support_resistance(bars)

        ma_alignment = _score(
            ((price - mas.sma_20) / mas.sma_20 + (mas.sma_20 - mas.sma_50) / mas.sma_50) / 2,
            scale=0.02,
        )
        macd_score = _score(macd_hist, scale=max(abs(macd_value), 1.0) * 0.5 or 1.0)
        rsi_score = (rsi_value - 50.0) / 50.0
        momentum_score = _score(momentum_value, scale=3.0)

        weights = {"ma": 0.35, "macd": 0.25, "rsi": 0.2, "momentum": 0.2}
        components = {
            "ma": ma_alignment,
            "macd": macd_score,
            "rsi": rsi_score,
            "momentum": momentum_score,
        }
        overall = sum(components[k] * weights[k] for k in weights)

        if overall > BULLISH_THRESHOLD:
            trend = Trend.BULLISH
        elif overall < BEARISH_THRESHOLD:
            trend = Trend.BEARISH
        else:
            trend = Trend.NEUTRAL

        strength = round(min(100.0, abs(overall) * 100.0), 2)

        agreeing = sum(
            1
            for value in components.values()
            if (value > 0 and overall > 0) or (value < 0 and overall < 0) or abs(value) < 0.05
        )
        confidence = round(min(100.0, (agreeing / len(components)) * 100.0), 2)

        if mas.sma_20 > mas.sma_50 > mas.sma_200:
            structure = "uptrend: 20 > 50 > 200"
        elif mas.sma_20 < mas.sma_50 < mas.sma_200:
            structure = "downtrend: 20 < 50 < 200"
        else:
            structure = "mixed / consolidating"

        return TechnicalAnalysis(
            trend=trend,
            strength=strength,
            support_levels=supports,
            resistance_levels=resistances,
            confidence_score=confidence,
            moving_averages=mas,
            rsi=round(rsi_value, 2),
            macd=round(macd_value, 4),
            macd_signal=round(macd_signal, 4),
            macd_histogram=round(macd_hist, 4),
            vwap=round(vwap_value, 2),
            momentum=round(momentum_value, 3),
            market_structure=structure,
        )
