"""Domain models for the SPX options signal pipeline.

These are plain data, like an :class:`~jarvis.agents.spec.AgentSpec` or a
:class:`~jarvis.workflows.models.Workflow` — every stage of the pipeline
takes one of these in and hands the next one a new one out, so the pipeline
is a chain of pure transformations that can each be unit-tested without a
market open anywhere.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from jarvis.kernel.ids import new_id


class Trend(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketCondition(StrEnum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class VolatilityState(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    EXTREME = "extreme"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyType(StrEnum):
    BULL_CALL_SPREAD = "bull_call_spread"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    IRON_CONDOR = "iron_condor"
    BUTTERFLY = "butterfly"


BULLISH_STRATEGIES = (StrategyType.BULL_CALL_SPREAD, StrategyType.BULL_PUT_SPREAD)
BEARISH_STRATEGIES = (StrategyType.BEAR_PUT_SPREAD, StrategyType.BEAR_CALL_SPREAD)
NEUTRAL_STRATEGIES = (StrategyType.IRON_CONDOR, StrategyType.BUTTERFLY)


class SignalStatus(StrEnum):
    ACTIVE = "active"
    TARGET_HIT = "target_hit"
    STOPPED_OUT = "stopped_out"
    EXPIRED_WIN = "expired_win"
    EXPIRED_LOSS = "expired_loss"
    CLOSED = "closed"


class TradeOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class UserRole(StrEnum):
    SUBSCRIBER = "subscriber"
    ADMIN = "admin"


# ── Market data ─────────────────────────────────────────────────────────────


class MarketSnapshot(BaseModel):
    """A single point-in-time read of the broad market, as specified by the
    signal-bot brief: id, timestamp, symbol, price, volume, vix, trend,
    market_condition — plus the wider context the market data agent also
    collects (SPY, futures, breadth, calendar, sentiment) so downstream
    agents are not starved of it.
    """

    id: str = Field(default_factory=lambda: new_id("mkt"))
    timestamp: datetime
    symbol: str = "SPX"
    price: float
    volume: float = 0.0
    vix: float
    trend: Trend
    market_condition: MarketCondition

    spy_price: float | None = None
    futures_price: float | None = None
    futures_symbol: str = "ES"
    market_breadth: float | None = None  # advancers/decliners ratio, -1..1
    economic_events: list[str] = Field(default_factory=list)
    news_sentiment: float | None = None  # -1 (bearish) .. 1 (bullish)


# ── Technical analysis ──────────────────────────────────────────────────────


class MovingAverages(BaseModel):
    sma_20: float
    sma_50: float
    sma_200: float
    ema_12: float
    ema_26: float


class TechnicalAnalysis(BaseModel):
    trend: Trend
    strength: float  # 0-100
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    confidence_score: float  # 0-100

    moving_averages: MovingAverages
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    vwap: float
    momentum: float
    market_structure: str = ""


# ── Options analysis ────────────────────────────────────────────────────────


class OptionGreeks(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float


class StrikeMetrics(BaseModel):
    strike: float
    option_type: str  # "call" | "put"
    implied_volatility: float
    open_interest: int
    volume: int
    greeks: OptionGreeks


class OptionsAnalysis(BaseModel):
    volatility_state: VolatilityState
    best_expiration: str  # ISO date
    important_strikes: list[StrikeMetrics] = Field(default_factory=list)
    market_positioning: str
    risk_level: RiskLevel

    iv: float
    iv_rank: float  # 0-100
    put_call_ratio: float
    expected_move: float
    expected_move_pct: float


# ── Strategy ─────────────────────────────────────────────────────────────


class StrategyLeg(BaseModel):
    action: str  # "sell" | "buy"
    option_type: str  # "call" | "put"
    strike: float
    quantity: int = 1


class Strategy(BaseModel):
    id: str = Field(default_factory=lambda: new_id("stg"))
    strategy_type: StrategyType
    underlying: str = "SPX"
    legs: list[StrategyLeg]
    entry: str  # human-readable entry description
    expiration: str  # ISO date
    days_to_expiration: int
    credit: float = 0.0  # premium received (credit spreads)
    debit: float = 0.0  # premium paid (debit spreads)
    max_profit: float
    max_loss: float
    probability_of_profit: float  # 0-100
    risk_reward_ratio: float

    @property
    def strike_prices(self) -> list[float]:
        return [leg.strike for leg in self.legs]

    @property
    def is_credit(self) -> bool:
        return self.credit > 0


# ── Risk management ─────────────────────────────────────────────────────


class RiskCheck(BaseModel):
    rule: str
    passed: bool
    detail: str = ""


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    checks: list[RiskCheck] = Field(default_factory=list)


# ── Signal ───────────────────────────────────────────────────────────────


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sig"))
    timestamp: datetime
    market_direction: Trend
    strategy: Strategy
    confidence: int  # 1-10
    reasons: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    status: SignalStatus = SignalStatus.ACTIVE
    result: TradeOutcome | None = None
    message: str = ""  # rendered Telegram text

    @property
    def entry(self) -> str:
        return self.strategy.entry

    @property
    def expiration(self) -> str:
        return self.strategy.expiration

    @property
    def strike_prices(self) -> list[float]:
        return self.strategy.strike_prices


# ── Performance ──────────────────────────────────────────────────────────


class TradeResult(BaseModel):
    id: str = Field(default_factory=lambda: new_id("trd"))
    signal_id: str
    outcome: TradeOutcome
    pnl_usd: float
    pnl_pct: float
    closed_at: datetime


class StrategyPerformance(BaseModel):
    strategy_type: StrategyType
    total: int
    wins: int
    losses: int
    win_rate: float
    average_return_pct: float


class PerformanceMetrics(BaseModel):
    total_signals: int
    winning_signals: int
    losing_signals: int
    win_rate: float
    average_return_pct: float
    max_drawdown_pct: float
    strategy_performance: list[StrategyPerformance] = Field(default_factory=list)
    computed_at: datetime


# ── Users & subscriptions ───────────────────────────────────────────────


class UserSettings(BaseModel):
    receive_signals: bool = True
    max_risk_level: RiskLevel = RiskLevel.HIGH
    quiet_hours_start: int | None = None  # hour, 0-23, local
    quiet_hours_end: int | None = None


class User(BaseModel):
    id: str = Field(default_factory=lambda: new_id("usr"))
    telegram_id: int
    username: str = ""
    role: UserRole = UserRole.SUBSCRIBER
    created_at: datetime
    settings: UserSettings = Field(default_factory=UserSettings)


class Subscription(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sub"))
    user_id: str
    tier: str = "free"
    active: bool = True
    started_at: datetime
    expires_at: datetime | None = None


class OptionsSnapshot(BaseModel):
    """A stored options-chain read, one row per analysed expiration."""

    id: str = Field(default_factory=lambda: new_id("opt"))
    timestamp: datetime
    underlying: str = "SPX"
    analysis: OptionsAnalysis
    raw: dict[str, Any] = Field(default_factory=dict)
