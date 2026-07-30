"""Trading department tables.

Shares :class:`jarvis.persistence.models.Base` — one metadata object, one
Alembic history, one ``create_all`` — rather than a second engine or schema
namespace. The trading department is optional, but its durability is not a
different kind of durability from the rest of Jarvis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jarvis.persistence.models import Base, JsonColumn


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TradingUserRow(Base):
    __tablename__ = "trading_users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, unique=True)
    username: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="subscriber")
    settings: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SubscriptionRow(Base):
    __tablename__ = "trading_subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("trading_users.id", ondelete="CASCADE"), index=True
    )
    tier: Mapped[str] = mapped_column(String(32), default="free")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketSnapshotRow(Base):
    __tablename__ = "trading_market_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    symbol: Mapped[str] = mapped_column(String(16), default="SPX")
    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    vix: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[str] = mapped_column(String(16), nullable=False)
    market_condition: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)


class OptionsSnapshotRow(Base):
    __tablename__ = "trading_options_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    underlying: Mapped[str] = mapped_column(String(16), default="SPX")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)


class SignalRow(Base):
    __tablename__ = "trading_signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    result: Mapped[str | None] = mapped_column(String(16))
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)


class TradeResultRow(Base):
    __tablename__ = "trading_trade_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("trading_signals.id", ondelete="CASCADE"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PerformanceMetricRow(Base):
    __tablename__ = "trading_performance_metrics"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonColumn, default=dict)
