from __future__ import annotations

from datetime import UTC, datetime

from jarvis.trading.config import TradingSettings
from jarvis.trading.models import (
    MarketCondition,
    MarketSnapshot,
    OptionsAnalysis,
    RiskLevel,
    Strategy,
    StrategyLeg,
    StrategyType,
    Trend,
    VolatilityState,
)
from jarvis.trading.risk_manager_agent import rules
from jarvis.trading.risk_manager_agent.agent import RiskManagerAgent


def make_strategy(
    *,
    pop: float = 75.0,
    max_loss: float = 380.0,
    max_profit: float = 120.0,
    risk_reward: float = 0.32,
) -> Strategy:
    return Strategy(
        strategy_type=StrategyType.BULL_PUT_SPREAD,
        legs=[
            StrategyLeg(action="sell", option_type="put", strike=6100),
            StrategyLeg(action="buy", option_type="put", strike=6050),
        ],
        entry="Sell SPX 6100 Put / Buy SPX 6050 Put",
        expiration="2026-03-24",
        days_to_expiration=14,
        credit=1.20,
        max_profit=max_profit,
        max_loss=max_loss,
        probability_of_profit=pop,
        risk_reward_ratio=risk_reward,
    )


def make_market(*, economic_events: list[str] | None = None) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
        symbol="SPX",
        price=5500.0,
        volume=1_800_000_000,
        vix=15.0,
        trend=Trend.BULLISH,
        market_condition=MarketCondition.TRENDING_UP,
        economic_events=economic_events or [],
    )


def make_options_analysis(
    *, iv_rank: float = 45.0, volatility_state: VolatilityState = VolatilityState.NORMAL
) -> OptionsAnalysis:
    return OptionsAnalysis(
        volatility_state=volatility_state,
        best_expiration="2026-03-24",
        important_strikes=[],
        market_positioning="balanced put/call positioning",
        risk_level=RiskLevel.MEDIUM,
        iv=0.15,
        iv_rank=iv_rank,
        put_call_ratio=0.9,
        expected_move=120.0,
        expected_move_pct=2.2,
    )


def settings(**overrides) -> TradingSettings:
    base = dict(
        account_size_usd=38_000.0,
        max_risk_per_trade_pct=1.0,
        min_probability_of_profit=70.0,
        max_daily_signals=3,
        max_consecutive_losses=3,
        max_iv_rank_for_entry=95.0,
        min_risk_reward_ratio=0.15,
    )
    base.update(overrides)
    return TradingSettings(**base)


# ── individual rules ─────────────────────────────────────────────────────


def test_pop_rule_rejects_below_threshold():
    check = rules.check_probability_of_profit(make_strategy(pop=65.0), minimum=70.0)
    assert not check.passed


def test_pop_rule_accepts_at_threshold():
    check = rules.check_probability_of_profit(make_strategy(pop=70.0), minimum=70.0)
    assert check.passed


def test_risk_per_trade_rejects_when_loss_exceeds_account_pct():
    check = rules.check_risk_per_trade(
        make_strategy(max_loss=1000.0), contracts=1, account_size_usd=38_000.0, max_risk_pct=1.0
    )
    assert not check.passed  # 1000/38000 = 2.6% > 1%


def test_risk_per_trade_accepts_within_limit():
    check = rules.check_risk_per_trade(
        make_strategy(max_loss=380.0), contracts=1, account_size_usd=38_000.0, max_risk_pct=1.0
    )
    assert check.passed  # 380/38000 = 1.0%


def test_risk_per_trade_scales_with_contract_count():
    check = rules.check_risk_per_trade(
        make_strategy(max_loss=380.0), contracts=3, account_size_usd=38_000.0, max_risk_pct=1.0
    )
    assert not check.passed


def test_risk_per_trade_rejects_unconfigured_account_size():
    check = rules.check_risk_per_trade(
        make_strategy(), contracts=1, account_size_usd=0.0, max_risk_pct=1.0
    )
    assert not check.passed


def test_daily_signal_limit_rejects_at_cap():
    check = rules.check_daily_signal_limit(signals_today=3, max_daily_signals=3)
    assert not check.passed


def test_daily_signal_limit_accepts_below_cap():
    check = rules.check_daily_signal_limit(signals_today=2, max_daily_signals=3)
    assert check.passed


def test_consecutive_losses_rejects_at_cap():
    check = rules.check_consecutive_losses(consecutive_losses=3, max_consecutive_losses=3)
    assert not check.passed


def test_consecutive_losses_accepts_below_cap():
    check = rules.check_consecutive_losses(consecutive_losses=2, max_consecutive_losses=3)
    assert check.passed


def test_economic_event_blackout_rejects_when_events_present():
    check = rules.check_economic_event_blackout(make_market(economic_events=["FOMC Rate Decision"]))
    assert not check.passed


def test_economic_event_blackout_accepts_a_quiet_calendar():
    check = rules.check_economic_event_blackout(make_market())
    assert check.passed


def test_volatility_rule_rejects_extreme_state():
    check = rules.check_volatility(
        make_options_analysis(volatility_state=VolatilityState.EXTREME), max_iv_rank=95.0
    )
    assert not check.passed


def test_volatility_rule_rejects_iv_rank_over_ceiling():
    check = rules.check_volatility(make_options_analysis(iv_rank=98.0), max_iv_rank=95.0)
    assert not check.passed


def test_volatility_rule_accepts_normal_conditions():
    check = rules.check_volatility(make_options_analysis(), max_iv_rank=95.0)
    assert check.passed


def test_risk_reward_rule_rejects_poor_ratio():
    check = rules.check_risk_reward(make_strategy(risk_reward=0.05), minimum_ratio=0.15)
    assert not check.passed


def test_risk_reward_rule_accepts_good_ratio():
    check = rules.check_risk_reward(make_strategy(risk_reward=0.32), minimum_ratio=0.15)
    assert check.passed


# ── the agent ────────────────────────────────────────────────────────────


def test_agent_approves_a_clean_signal():
    agent = RiskManagerAgent(settings())
    decision = agent.evaluate(
        strategy=make_strategy(),
        market=make_market(),
        options_analysis=make_options_analysis(),
        signals_today=0,
        consecutive_losses=0,
    )
    assert decision.approved
    assert all(c.passed for c in decision.checks)


def test_agent_rejects_low_probability_of_profit():
    agent = RiskManagerAgent(settings())
    decision = agent.evaluate(
        strategy=make_strategy(pop=60.0),
        market=make_market(),
        options_analysis=make_options_analysis(),
        signals_today=0,
        consecutive_losses=0,
    )
    assert not decision.approved
    assert "probability_of_profit" in decision.reason


def test_agent_rejects_when_daily_signal_cap_is_reached():
    agent = RiskManagerAgent(settings(max_daily_signals=3))
    decision = agent.evaluate(
        strategy=make_strategy(),
        market=make_market(),
        options_analysis=make_options_analysis(),
        signals_today=3,
        consecutive_losses=0,
    )
    assert not decision.approved


def test_agent_rejects_after_consecutive_loss_limit():
    agent = RiskManagerAgent(settings(max_consecutive_losses=3))
    decision = agent.evaluate(
        strategy=make_strategy(),
        market=make_market(),
        options_analysis=make_options_analysis(),
        signals_today=0,
        consecutive_losses=3,
    )
    assert not decision.approved


def test_agent_rejects_during_economic_event_blackout():
    agent = RiskManagerAgent(settings())
    decision = agent.evaluate(
        strategy=make_strategy(),
        market=make_market(economic_events=["Non-Farm Payrolls"]),
        options_analysis=make_options_analysis(),
        signals_today=0,
        consecutive_losses=0,
    )
    assert not decision.approved


def test_agent_reports_every_failing_rule_not_just_the_first():
    agent = RiskManagerAgent(settings())
    decision = agent.evaluate(
        strategy=make_strategy(pop=50.0, risk_reward=0.01),
        market=make_market(economic_events=["FOMC"]),
        options_analysis=make_options_analysis(volatility_state=VolatilityState.EXTREME),
        signals_today=0,
        consecutive_losses=0,
    )
    failed_rules = {c.rule for c in decision.checks if not c.passed}
    assert failed_rules == {
        "probability_of_profit",
        "economic_event_blackout",
        "volatility",
        "risk_reward_ratio",
    }


def test_best_approved_returns_none_when_nothing_clears():
    agent = RiskManagerAgent(settings())
    result = agent.best_approved(
        [make_strategy(pop=40.0)],
        market=make_market(),
        options_analysis=make_options_analysis(),
        signals_today=0,
        consecutive_losses=0,
    )
    assert result is None


def test_best_approved_picks_the_highest_probability_candidate():
    agent = RiskManagerAgent(settings())
    weaker = make_strategy(pop=72.0)
    stronger = make_strategy(pop=80.0)
    result = agent.best_approved(
        [weaker, stronger],
        market=make_market(),
        options_analysis=make_options_analysis(),
        signals_today=0,
        consecutive_losses=0,
    )
    assert result is not None
    strategy, decision = result
    assert strategy.probability_of_profit == 80.0
    assert decision.approved
