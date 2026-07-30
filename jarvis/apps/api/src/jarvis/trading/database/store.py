"""Trading department storage: an in-memory store for dev/tests, and a SQL
store durable across restarts — the same split every other Jarvis store
follows (``InMemoryWorkflowStore`` / ``SqlWorkflowStore`` and friends)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import select

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.kernel.ids import new_id
from jarvis.persistence.db import Database
from jarvis.trading.database.models import (
    MarketSnapshotRow,
    OptionsSnapshotRow,
    PerformanceMetricRow,
    SignalRow,
    SubscriptionRow,
    TradeResultRow,
    TradingUserRow,
)
from jarvis.trading.models import (
    MarketSnapshot,
    OptionsSnapshot,
    PerformanceMetrics,
    Signal,
    SignalStatus,
    Subscription,
    TradeOutcome,
    TradeResult,
    User,
    UserRole,
    UserSettings,
)


class TradingStore(Protocol):
    async def save_market_snapshot(self, snapshot: MarketSnapshot) -> None: ...

    async def save_options_snapshot(self, snapshot: OptionsSnapshot) -> None: ...

    async def save_signal(self, signal: Signal) -> Signal: ...

    async def get_signal(self, signal_id: str) -> Signal | None: ...

    async def list_signals(
        self, *, limit: int = 20, status: SignalStatus | None = None
    ) -> list[Signal]: ...

    async def update_signal_status(
        self, signal_id: str, *, status: SignalStatus, result: TradeOutcome | None = None
    ) -> None: ...

    async def signals_today(self, *, now: datetime) -> int: ...

    async def consecutive_losses(self) -> int: ...

    async def save_trade_result(self, result: TradeResult) -> None: ...

    async def list_trade_results(self, *, limit: int = 200) -> list[TradeResult]: ...

    async def save_performance_metrics(self, metrics: PerformanceMetrics) -> None: ...

    async def latest_performance_metrics(self) -> PerformanceMetrics | None: ...

    async def upsert_user(self, user: User) -> User: ...

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None: ...

    async def list_users(self, *, role: UserRole | None = None) -> list[User]: ...

    async def save_subscription(self, subscription: Subscription) -> None: ...


def _is_loss(result: TradeOutcome | None) -> bool:
    return result == TradeOutcome.LOSS


class InMemoryTradingStore:
    def __init__(self, clock: Clock = SYSTEM_CLOCK) -> None:
        self._clock = clock
        self._market_snapshots: list[MarketSnapshot] = []
        self._options_snapshots: list[OptionsSnapshot] = []
        self._signals: dict[str, Signal] = {}
        self._signal_order: list[str] = []
        self._trade_results: list[TradeResult] = []
        self._performance_metrics: list[PerformanceMetrics] = []
        self._users: dict[str, User] = {}
        self._users_by_telegram_id: dict[int, str] = {}
        self._subscriptions: list[Subscription] = []

    async def save_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._market_snapshots.append(snapshot.model_copy(deep=True))

    async def save_options_snapshot(self, snapshot: OptionsSnapshot) -> None:
        self._options_snapshots.append(snapshot.model_copy(deep=True))

    async def save_signal(self, signal: Signal) -> Signal:
        self._signals[signal.id] = signal.model_copy(deep=True)
        if signal.id not in self._signal_order:
            self._signal_order.append(signal.id)
        return signal

    async def get_signal(self, signal_id: str) -> Signal | None:
        stored = self._signals.get(signal_id)
        return stored.model_copy(deep=True) if stored else None

    async def list_signals(
        self, *, limit: int = 20, status: SignalStatus | None = None
    ) -> list[Signal]:
        ordered = [self._signals[i] for i in reversed(self._signal_order)]
        if status is not None:
            ordered = [s for s in ordered if s.status == status]
        return [s.model_copy(deep=True) for s in ordered[:limit]]

    async def update_signal_status(
        self, signal_id: str, *, status: SignalStatus, result: TradeOutcome | None = None
    ) -> None:
        signal = self._signals.get(signal_id)
        if signal is None:
            return
        signal.status = status
        if result is not None:
            signal.result = result

    async def signals_today(self, *, now: datetime) -> int:
        return sum(1 for s in self._signals.values() if s.timestamp.date() == now.date())

    async def consecutive_losses(self) -> int:
        ordered = [
            self._signals[i] for i in reversed(self._signal_order) if self._signals[i].result
        ]
        streak = 0
        for signal in ordered:
            if _is_loss(signal.result):
                streak += 1
            else:
                break
        return streak

    async def save_trade_result(self, result: TradeResult) -> None:
        self._trade_results.append(result.model_copy(deep=True))

    async def list_trade_results(self, *, limit: int = 200) -> list[TradeResult]:
        ordered = list(reversed(self._trade_results))
        return [r.model_copy(deep=True) for r in ordered[:limit]]

    async def save_performance_metrics(self, metrics: PerformanceMetrics) -> None:
        self._performance_metrics.append(metrics.model_copy(deep=True))

    async def latest_performance_metrics(self) -> PerformanceMetrics | None:
        if not self._performance_metrics:
            return None
        return self._performance_metrics[-1].model_copy(deep=True)

    async def upsert_user(self, user: User) -> User:
        existing_id = self._users_by_telegram_id.get(user.telegram_id)
        if existing_id and existing_id != user.id:
            user = user.model_copy(update={"id": existing_id})
        self._users[user.id] = user.model_copy(deep=True)
        self._users_by_telegram_id[user.telegram_id] = user.id
        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        user_id = self._users_by_telegram_id.get(telegram_id)
        if user_id is None:
            return None
        stored = self._users.get(user_id)
        return stored.model_copy(deep=True) if stored else None

    async def list_users(self, *, role: UserRole | None = None) -> list[User]:
        users = list(self._users.values())
        if role is not None:
            users = [u for u in users if u.role == role]
        return [u.model_copy(deep=True) for u in users]

    async def save_subscription(self, subscription: Subscription) -> None:
        self._subscriptions.append(subscription.model_copy(deep=True))


class SqlTradingStore:
    """Durable trading data, sharing the kernel's database and session
    factory rather than opening a second connection pool."""

    def __init__(self, database: Database, clock: Clock = SYSTEM_CLOCK) -> None:
        self._db = database
        self._clock = clock

    async def save_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        async with self._db.session() as session:
            session.add(
                MarketSnapshotRow(
                    id=snapshot.id,
                    timestamp=snapshot.timestamp,
                    symbol=snapshot.symbol,
                    price=snapshot.price,
                    volume=snapshot.volume,
                    vix=snapshot.vix,
                    trend=snapshot.trend.value,
                    market_condition=snapshot.market_condition.value,
                    payload=snapshot.model_dump(mode="json"),
                )
            )
            await session.commit()

    async def save_options_snapshot(self, snapshot: OptionsSnapshot) -> None:
        async with self._db.session() as session:
            session.add(
                OptionsSnapshotRow(
                    id=snapshot.id,
                    timestamp=snapshot.timestamp,
                    underlying=snapshot.underlying,
                    payload=snapshot.model_dump(mode="json"),
                )
            )
            await session.commit()

    async def save_signal(self, signal: Signal) -> Signal:
        async with self._db.session() as session:
            row = await session.get(SignalRow, signal.id)
            payload = signal.model_dump(mode="json")
            if row is None:
                session.add(
                    SignalRow(
                        id=signal.id,
                        timestamp=signal.timestamp,
                        strategy_type=signal.strategy.strategy_type.value,
                        status=signal.status.value,
                        result=signal.result.value if signal.result else None,
                        confidence=signal.confidence,
                        message=signal.message,
                        payload=payload,
                    )
                )
            else:
                row.status = signal.status.value
                row.result = signal.result.value if signal.result else None
                row.message = signal.message
                row.payload = payload
            await session.commit()
        return signal

    async def get_signal(self, signal_id: str) -> Signal | None:
        async with self._db.session() as session:
            row = await session.get(SignalRow, signal_id)
            return Signal.model_validate(row.payload) if row else None

    async def list_signals(
        self, *, limit: int = 20, status: SignalStatus | None = None
    ) -> list[Signal]:
        statement = select(SignalRow).order_by(SignalRow.timestamp.desc()).limit(limit)
        if status is not None:
            statement = statement.where(SignalRow.status == status.value)
        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [Signal.model_validate(row.payload) for row in rows]

    async def update_signal_status(
        self, signal_id: str, *, status: SignalStatus, result: TradeOutcome | None = None
    ) -> None:
        async with self._db.session() as session:
            row = await session.get(SignalRow, signal_id)
            if row is None:
                return
            row.status = status.value
            if result is not None:
                row.result = result.value
            payload = dict(row.payload)
            payload["status"] = status.value
            if result is not None:
                payload["result"] = result.value
            row.payload = payload
            await session.commit()

    async def signals_today(self, *, now: datetime) -> int:
        async with self._db.session() as session:
            rows = (await session.execute(select(SignalRow.timestamp))).scalars().all()
        return sum(1 for ts in rows if ts.date() == now.date())

    async def consecutive_losses(self) -> int:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        select(SignalRow.result)
                        .where(SignalRow.result.is_not(None))
                        .order_by(SignalRow.timestamp.desc())
                    )
                )
                .scalars()
                .all()
            )
        streak = 0
        for result in rows:
            if result == TradeOutcome.LOSS.value:
                streak += 1
            else:
                break
        return streak

    async def save_trade_result(self, result: TradeResult) -> None:
        async with self._db.session() as session:
            session.add(
                TradeResultRow(
                    id=result.id,
                    signal_id=result.signal_id,
                    outcome=result.outcome.value,
                    pnl_usd=result.pnl_usd,
                    pnl_pct=result.pnl_pct,
                    closed_at=result.closed_at,
                )
            )
            await session.commit()

    async def list_trade_results(self, *, limit: int = 200) -> list[TradeResult]:
        statement = select(TradeResultRow).order_by(TradeResultRow.closed_at.desc()).limit(limit)
        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [
            TradeResult(
                id=row.id,
                signal_id=row.signal_id,
                outcome=TradeOutcome(row.outcome),
                pnl_usd=row.pnl_usd,
                pnl_pct=row.pnl_pct,
                closed_at=row.closed_at,
            )
            for row in rows
        ]

    async def save_performance_metrics(self, metrics: PerformanceMetrics) -> None:
        async with self._db.session() as session:
            session.add(
                PerformanceMetricRow(
                    id=new_id("prf"),
                    computed_at=metrics.computed_at,
                    payload=metrics.model_dump(mode="json"),
                )
            )
            await session.commit()

    async def latest_performance_metrics(self) -> PerformanceMetrics | None:
        statement = (
            select(PerformanceMetricRow).order_by(PerformanceMetricRow.computed_at.desc()).limit(1)
        )
        async with self._db.session() as session:
            row = (await session.execute(statement)).scalars().first()
        return PerformanceMetrics.model_validate(row.payload) if row else None

    async def upsert_user(self, user: User) -> User:
        async with self._db.session() as session:
            existing = (
                (
                    await session.execute(
                        select(TradingUserRow).where(TradingUserRow.telegram_id == user.telegram_id)
                    )
                )
                .scalars()
                .first()
            )
            if existing is None:
                session.add(
                    TradingUserRow(
                        id=user.id,
                        telegram_id=user.telegram_id,
                        username=user.username,
                        role=user.role.value,
                        settings=user.settings.model_dump(mode="json"),
                        created_at=user.created_at,
                    )
                )
            else:
                existing.username = user.username
                existing.role = user.role.value
                existing.settings = user.settings.model_dump(mode="json")
                user = user.model_copy(
                    update={"id": existing.id, "created_at": existing.created_at}
                )
            await session.commit()
        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        async with self._db.session() as session:
            row = (
                (
                    await session.execute(
                        select(TradingUserRow).where(TradingUserRow.telegram_id == telegram_id)
                    )
                )
                .scalars()
                .first()
            )
        if row is None:
            return None
        return User(
            id=row.id,
            telegram_id=row.telegram_id,
            username=row.username,
            role=UserRole(row.role),
            created_at=row.created_at,
            settings=UserSettings.model_validate(row.settings),
        )

    async def list_users(self, *, role: UserRole | None = None) -> list[User]:
        statement = select(TradingUserRow)
        if role is not None:
            statement = statement.where(TradingUserRow.role == role.value)
        async with self._db.session() as session:
            rows = (await session.execute(statement)).scalars().all()
        return [
            User(
                id=row.id,
                telegram_id=row.telegram_id,
                username=row.username,
                role=UserRole(row.role),
                created_at=row.created_at,
                settings=UserSettings.model_validate(row.settings),
            )
            for row in rows
        ]

    async def save_subscription(self, subscription: Subscription) -> None:
        async with self._db.session() as session:
            session.add(
                SubscriptionRow(
                    id=subscription.id,
                    user_id=subscription.user_id,
                    tier=subscription.tier,
                    active=subscription.active,
                    started_at=subscription.started_at,
                    expires_at=subscription.expires_at,
                )
            )
            await session.commit()
