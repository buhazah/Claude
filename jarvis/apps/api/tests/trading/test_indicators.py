from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jarvis.trading.technical_analysis_agent.indicators import (
    PriceBar,
    ema,
    ema_series,
    macd,
    momentum,
    rsi,
    sma,
    support_resistance,
    vwap,
)


def bar(
    i: int,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000,
) -> PriceBar:
    return PriceBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
        open=close,
        high=high if high is not None else close + 1,
        low=low if low is not None else close - 1,
        close=close,
        volume=volume,
    )


# ── sma ──────────────────────────────────────────────────────────────────


def test_sma_averages_the_trailing_window():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0


def test_sma_uses_only_the_trailing_window():
    assert sma([100, 100, 1, 2, 3], 3) == 2.0


def test_sma_raises_on_insufficient_data():
    with pytest.raises(ValueError, match="sma"):
        sma([1, 2], 5)


# ── ema ──────────────────────────────────────────────────────────────────


def test_ema_of_constant_series_equals_the_constant():
    assert ema([5.0] * 10, 3) == pytest.approx(5.0)


def test_ema_series_seeds_from_first_value():
    series = ema_series([10.0, 20.0], 2)
    assert series[0] == 10.0
    k = 2 / 3
    assert series[1] == pytest.approx(20.0 * k + 10.0 * (1 - k))


def test_ema_raises_on_insufficient_data():
    with pytest.raises(ValueError, match="ema"):
        ema([1.0], 5)


def test_ema_series_of_empty_input_is_empty():
    assert ema_series([], 5) == []


# ── rsi ──────────────────────────────────────────────────────────────────


def test_rsi_is_100_when_every_bar_gains():
    closes = [100 + i for i in range(20)]
    assert rsi(closes) == 100.0


def test_rsi_is_0_when_every_bar_loses():
    closes = [100 - i for i in range(20)]
    assert rsi(closes) == 0.0


def test_rsi_is_50_for_alternating_equal_moves():
    closes = [100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100]
    assert rsi(closes, period=14) == pytest.approx(50.0, abs=1.0)


def test_rsi_is_50_for_a_perfectly_flat_series():
    assert rsi([100.0] * 20) == 50.0


def test_rsi_raises_on_insufficient_data():
    with pytest.raises(ValueError, match="rsi"):
        rsi([1.0, 2.0], period=14)


# ── macd ─────────────────────────────────────────────────────────────────


def test_macd_histogram_is_zero_for_a_flat_series():
    closes = [100.0] * 40
    macd_line, signal_line, histogram = macd(closes)
    assert macd_line == pytest.approx(0.0)
    assert signal_line == pytest.approx(0.0)
    assert histogram == pytest.approx(0.0)


def test_macd_is_positive_for_a_sustained_uptrend():
    closes = [100.0 + i * 0.5 for i in range(60)]
    macd_line, _, _ = macd(closes)
    assert macd_line > 0


def test_macd_is_negative_for_a_sustained_downtrend():
    closes = [100.0 - i * 0.5 for i in range(60)]
    macd_line, _, _ = macd(closes)
    assert macd_line < 0


def test_macd_raises_on_insufficient_data():
    with pytest.raises(ValueError, match="macd"):
        macd([1.0] * 10)


# ── vwap ─────────────────────────────────────────────────────────────────


def test_vwap_is_the_volume_weighted_typical_price():
    bars = [
        PriceBar(datetime(2026, 1, 1, tzinfo=UTC), open=10, high=12, low=8, close=10, volume=100),
        PriceBar(datetime(2026, 1, 1, tzinfo=UTC), open=20, high=22, low=18, close=20, volume=300),
    ]
    typical_1 = (12 + 8 + 10) / 3
    typical_2 = (22 + 18 + 20) / 3
    expected = (typical_1 * 100 + typical_2 * 300) / 400
    assert vwap(bars) == pytest.approx(expected)


def test_vwap_raises_with_no_bars():
    with pytest.raises(ValueError):
        vwap([])


def test_vwap_raises_with_zero_volume():
    bars = [PriceBar(datetime(2026, 1, 1, tzinfo=UTC), 10, 11, 9, 10, 0)]
    with pytest.raises(ValueError, match="volume"):
        vwap(bars)


# ── momentum ─────────────────────────────────────────────────────────────


def test_momentum_is_the_percent_change_over_the_period():
    closes = [100.0] * 5 + [110.0]
    assert momentum(closes, period=5) == pytest.approx(10.0)


def test_momentum_raises_on_insufficient_data():
    with pytest.raises(ValueError, match="momentum"):
        momentum([1.0, 2.0], period=10)


# ── support / resistance ────────────────────────────────────────────────


def test_support_resistance_finds_an_obvious_pivot_low_and_high():
    closes = [100, 99, 98, 90, 98, 99, 100, 101, 102, 110, 102, 101, 100]
    bars = [bar(i, close=c) for i, c in enumerate(closes)]
    supports, resistances = support_resistance(bars, lookback=len(bars), window=2)
    assert any(abs(s - 89.0) < 2.0 for s in supports)
    assert any(abs(r - 111.0) < 2.0 for r in resistances)


def test_support_resistance_caps_at_max_levels():
    closes = [100 + (i % 2) * (-1 if i % 4 == 0 else 1) * 5 for i in range(60)]
    bars = [bar(i, close=c) for i, c in enumerate(closes)]
    supports, resistances = support_resistance(bars, max_levels=2)
    assert len(supports) <= 2
    assert len(resistances) <= 2


def test_support_resistance_handles_short_history_without_raising():
    bars = [bar(i, close=100 + i) for i in range(3)]
    supports, resistances = support_resistance(bars)
    assert supports == []
    assert resistances == []
