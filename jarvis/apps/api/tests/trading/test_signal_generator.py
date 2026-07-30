from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.trading.models import (
    MarketCondition,
    MarketSnapshot,
    MovingAverages,
    OptionsAnalysis,
    RiskCheck,
    RiskDecision,
    RiskLevel,
    Strategy,
    StrategyLeg,
    StrategyType,
    TechnicalAnalysis,
    Trend,
    VolatilityState,
)
from jarvis.trading.signal_generator_agent.agent import SignalGeneratorAgent
from jarvis.trading.signal_generator_agent.formatter import render_signal_message


def make_market() -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=datetime(2026, 8, 14, 15, 0, tzinfo=UTC),
        symbol="SPX",
        price=6120.0,
        volume=1_800_000_000,
        vix=14.0,
        trend=Trend.BULLISH,
        market_condition=MarketCondition.TRENDING_UP,
    )


def make_technical(*, trend: Trend = Trend.BULLISH, strength: float = 60.0) -> TechnicalAnalysis:
    return TechnicalAnalysis(
        trend=trend,
        strength=strength,
        support_levels=[6080.0],
        resistance_levels=[6180.0],
        confidence_score=75.0,
        moving_averages=MovingAverages(
            sma_20=6100, sma_50=6060, sma_200=5950, ema_12=6110, ema_26=6090
        ),
        rsi=58.0,
        macd=2.1,
        macd_signal=1.5,
        macd_histogram=0.6,
        vwap=6110.0,
        momentum=1.2,
    )


def make_options_analysis(*, iv_rank: float = 40.0) -> OptionsAnalysis:
    return OptionsAnalysis(
        volatility_state=VolatilityState.NORMAL,
        best_expiration="2026-08-28",
        important_strikes=[],
        market_positioning="balanced put/call positioning",
        risk_level=RiskLevel.MEDIUM,
        iv=0.14,
        iv_rank=iv_rank,
        put_call_ratio=0.9,
        expected_move=110.0,
        expected_move_pct=1.8,
    )


def make_strategy(*, pop: float = 74.0, risk_reward: float = 0.32) -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BULL_PUT_SPREAD,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=6100),
            StrategyLeg(action="buy", option_type="put", strike=6050),
        ],
        entry="Sell SPX 6100 Put / Buy SPX 6050 Put",
        expiration="2026-08-14",
        days_to_expiration=14,
        credit=1.20,
        max_profit=120.0,
        max_loss=380.0,
        probability_of_profit=pop,
        risk_reward_ratio=risk_reward,
    )


def approved(strategy: Strategy) -> RiskDecision:
    return RiskDecision(
        approved=True, reason="all risk checks passed", checks=[RiskCheck(rule="x", passed=True)]
    )


def rejected() -> RiskDecision:
    return RiskDecision(approved=False, reason="probability_of_profit failed", checks=[])


# ── agent ────────────────────────────────────────────────────────────────


def test_create_raises_for_a_rejected_strategy():
    agent = SignalGeneratorAgent()
    with pytest.raises(ValueError, match="rejected"):
        agent.create(
            market=make_market(),
            technical_analysis=make_technical(),
            options_analysis=make_options_analysis(),
            strategy=make_strategy(),
            risk_decision=rejected(),
        )


def test_create_derives_direction_from_the_strategy_type():
    agent = SignalGeneratorAgent()
    strategy = make_strategy()
    signal = agent.create(
        market=make_market(),
        technical_analysis=make_technical(),
        options_analysis=make_options_analysis(),
        strategy=strategy,
        risk_decision=approved(strategy),
    )
    assert signal.market_direction == Trend.BULLISH


def test_confidence_is_within_bounds():
    agent = SignalGeneratorAgent()
    for pop in (10.0, 50.0, 99.0):
        strategy = make_strategy(pop=pop)
        signal = agent.create(
            market=make_market(),
            technical_analysis=make_technical(),
            options_analysis=make_options_analysis(),
            strategy=strategy,
            risk_decision=approved(strategy),
        )
        assert 1 <= signal.confidence <= 10


def test_higher_probability_of_profit_yields_higher_or_equal_confidence():
    agent = SignalGeneratorAgent()
    low = make_strategy(pop=55.0)
    high = make_strategy(pop=90.0)
    low_signal = agent.create(
        market=make_market(),
        technical_analysis=make_technical(),
        options_analysis=make_options_analysis(),
        strategy=low,
        risk_decision=approved(low),
    )
    high_signal = agent.create(
        market=make_market(),
        technical_analysis=make_technical(),
        options_analysis=make_options_analysis(),
        strategy=high,
        risk_decision=approved(high),
    )
    assert high_signal.confidence >= low_signal.confidence


def test_reasons_include_trend_confirmation_when_aligned():
    agent = SignalGeneratorAgent()
    strategy = make_strategy()
    signal = agent.create(
        market=make_market(),
        technical_analysis=make_technical(trend=Trend.BULLISH, strength=70.0),
        options_analysis=make_options_analysis(),
        strategy=strategy,
        risk_decision=approved(strategy),
    )
    assert "Trend confirmation" in signal.reasons


def test_reasons_are_never_empty():
    agent = SignalGeneratorAgent()
    strategy = make_strategy(risk_reward=0.01, pop=55.0)
    signal = agent.create(
        market=make_market(),
        technical_analysis=make_technical(trend=Trend.NEUTRAL, strength=5.0),
        options_analysis=make_options_analysis(iv_rank=90.0),
        strategy=strategy,
        risk_decision=approved(strategy),
    )
    assert signal.reasons


def test_message_is_populated_and_matches_the_formatter():
    agent = SignalGeneratorAgent()
    strategy = make_strategy()
    signal = agent.create(
        market=make_market(),
        technical_analysis=make_technical(),
        options_analysis=make_options_analysis(),
        strategy=strategy,
        risk_decision=approved(strategy),
    )
    assert signal.message == render_signal_message(signal)


# ── formatter ────────────────────────────────────────────────────────────


def test_formatter_renders_the_expected_layout():
    strategy = make_strategy()
    signal_kwargs = dict(
        timestamp=datetime(2026, 8, 14, tzinfo=UTC),
        market_direction=Trend.BULLISH,
        strategy=strategy,
        confidence=8,
        reasons=["Trend confirmation", "Support holding", "Favorable IV", "Positive risk/reward"],
        risk_level=RiskLevel.MEDIUM,
    )
    from jarvis.trading.models import Signal

    signal = Signal(**signal_kwargs)
    message = render_signal_message(signal)

    assert "HERMES SPX AI SIGNAL" in message
    assert "🟢 Bullish" in message
    assert "Bull Put Spread" in message
    assert "SELL:" in message and "SPX 6100 Put" in message
    assert "BUY:" in message and "SPX 6050 Put" in message
    assert "14 AUG" in message
    assert "Credit:" in message and "$1.20" in message
    assert "Max Risk:" in message and "$380" in message
    assert "Probability:" in message and "74%" in message
    assert "Confidence:" in message and "8/10" in message
    assert "- Trend confirmation" in message
    assert "Risk Level:" in message and "Medium" in message
    assert message.count("================================") == 2


def test_formatter_shows_debit_for_debit_strategies():
    strategy = Strategy(
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        legs=[
            StrategyLeg(action="buy", option_type="call", strike=6100),
            StrategyLeg(action="sell", option_type="call", strike=6150),
        ],
        entry="Buy SPX 6100 Call / Sell SPX 6150 Call",
        expiration="2026-08-28",
        days_to_expiration=14,
        debit=8.5,
        max_profit=1650.0,
        max_loss=850.0,
        probability_of_profit=45.0,
        risk_reward_ratio=1.94,
    )
    from jarvis.trading.models import Signal

    signal = Signal(
        timestamp=datetime(2026, 8, 14, tzinfo=UTC),
        market_direction=Trend.BULLISH,
        strategy=strategy,
        confidence=6,
        reasons=["Trend confirmation"],
        risk_level=RiskLevel.LOW,
    )
    message = render_signal_message(signal)
    assert "Debit:" in message
    assert "$8.50" in message
    assert "Credit:" not in message


def test_formatter_handles_multi_leg_iron_condor():
    strategy = Strategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=6000),
            StrategyLeg(action="buy", option_type="put", strike=5950),
            StrategyLeg(action="sell", option_type="call", strike=6250),
            StrategyLeg(action="buy", option_type="call", strike=6300),
        ],
        entry="Sell 6000P/Buy 5950P + Sell 6250C/Buy 6300C",
        expiration="2026-08-28",
        days_to_expiration=14,
        credit=2.10,
        max_profit=210.0,
        max_loss=2900.0,
        probability_of_profit=68.0,
        risk_reward_ratio=0.072,
    )
    from jarvis.trading.models import Signal

    signal = Signal(
        timestamp=datetime(2026, 8, 14, tzinfo=UTC),
        market_direction=Trend.NEUTRAL,
        strategy=strategy,
        confidence=5,
        reasons=["Range-bound structure"],
        risk_level=RiskLevel.MEDIUM,
    )
    message = render_signal_message(signal)
    assert message.count("SELL:") == 2
    assert message.count("BUY:") == 2
    assert "⚪ Neutral" in message


def test_formatter_shows_quantity_for_multi_contract_legs():
    strategy = Strategy(
        strategy_type=StrategyType.BUTTERFLY,
        legs=[
            StrategyLeg(action="buy", option_type="call", strike=6050),
            StrategyLeg(action="sell", option_type="call", strike=6100, quantity=2),
            StrategyLeg(action="buy", option_type="call", strike=6150),
        ],
        entry="Butterfly",
        expiration="2026-08-28",
        days_to_expiration=14,
        debit=5.0,
        max_profit=4500.0,
        max_loss=500.0,
        probability_of_profit=30.0,
        risk_reward_ratio=9.0,
    )
    from jarvis.trading.models import Signal

    signal = Signal(
        timestamp=datetime(2026, 8, 14, tzinfo=UTC),
        market_direction=Trend.NEUTRAL,
        strategy=strategy,
        confidence=4,
        reasons=["Range-bound structure"],
        risk_level=RiskLevel.HIGH,
    )
    message = render_signal_message(signal)
    assert "SPX 6100 Call x2" in message
