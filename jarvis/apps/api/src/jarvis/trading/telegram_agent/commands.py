"""Command handlers: pure functions from (store, arguments) to reply text.

Kept separate from the bot's update-parsing and network I/O so every command
is testable without a Telegram payload or an HTTP mock — a handler takes
what it needs and returns a string.
"""

from __future__ import annotations

from datetime import datetime

from jarvis.trading.database.store import TradingStore
from jarvis.trading.models import SignalStatus, User, UserRole

WELCOME = (
    "\U0001f916 Welcome to the Hermes SPX AI Signal Bot.\n\n"
    "Commands:\n"
    "/signal — latest active signal\n"
    "/market — current market analysis\n"
    "/history — recent signals\n"
    "/performance — track record\n"
    "/settings — your preferences\n"
)

ADMIN_WELCOME_SUFFIX = "/admin — admin controls\n"

HISTORY_LIMIT = 5


async def handle_start(
    *, store: TradingStore, telegram_id: int, username: str, is_admin: bool, now: datetime
) -> str:
    existing = await store.get_user_by_telegram_id(telegram_id)
    role = UserRole.ADMIN if is_admin else (existing.role if existing else UserRole.SUBSCRIBER)
    await store.upsert_user(
        User(
            telegram_id=telegram_id,
            username=username,
            role=role,
            created_at=existing.created_at if existing else now,
        )
    )
    message = WELCOME
    if role == UserRole.ADMIN:
        message += ADMIN_WELCOME_SUFFIX
    return message


async def handle_signal(*, store: TradingStore) -> str:
    active = await store.list_signals(limit=1, status=SignalStatus.ACTIVE)
    if not active:
        return "No active signal right now. Check back after the next market scan."
    return active[0].message


async def handle_market(*, store: TradingStore) -> str:
    snapshot = await store.latest_market_snapshot()
    if snapshot is None:
        return "No market data yet."
    return (
        f"SPX: {snapshot.price:.2f}\n"
        f"VIX: {snapshot.vix:.2f}\n"
        f"Trend: {snapshot.trend.value}\n"
        f"Condition: {snapshot.market_condition.value}\n"
        f"As of: {snapshot.timestamp:%Y-%m-%d %H:%M UTC}"
    )


async def handle_history(*, store: TradingStore, limit: int = HISTORY_LIMIT) -> str:
    signals = await store.list_signals(limit=limit)
    if not signals:
        return "No signals yet."
    lines = [
        f"{s.timestamp:%Y-%m-%d %H:%M} — {s.strategy.strategy_type.value} — {s.status.value}"
        for s in signals
    ]
    return "\n".join(["Recent signals:", *lines])


async def handle_performance(*, store: TradingStore) -> str:
    metrics = await store.latest_performance_metrics()
    if metrics is None:
        return "No performance data yet."
    return (
        "Performance:\n"
        f"Total signals: {metrics.total_signals}\n"
        f"Win rate: {metrics.win_rate:.1f}%\n"
        f"Wins / Losses: {metrics.winning_signals} / {metrics.losing_signals}\n"
        f"Avg return: {metrics.average_return_pct:.2f}%\n"
        f"Max drawdown: {metrics.max_drawdown_pct:.2f}%"
    )


async def handle_settings(*, store: TradingStore, telegram_id: int, args: str) -> str:
    user = await store.get_user_by_telegram_id(telegram_id)
    if user is None:
        return "Send /start first."

    choice = args.strip().lower()
    if choice in ("on", "off"):
        user.settings.receive_signals = choice == "on"
        await store.upsert_user(user)
        return f"Signal notifications turned {choice}."

    return (
        "Your settings:\n"
        f"Receive signals: {'on' if user.settings.receive_signals else 'off'}\n"
        f"Max risk level: {user.settings.max_risk_level.value}\n\n"
        "Use /settings on or /settings off to toggle notifications."
    )


async def handle_admin(*, store: TradingStore, is_admin: bool, args: str) -> str:
    if not is_admin:
        return "You are not authorized to use admin commands."

    subcommand = args.strip().split()[0].lower() if args.strip() else "stats"
    if subcommand == "stats":
        users = await store.list_users()
        signals = await store.list_signals(limit=1000)
        losses = await store.consecutive_losses()
        return (
            "Admin stats:\n"
            f"Users: {len(users)}\n"
            f"Signals stored: {len(signals)}\n"
            f"Current consecutive losses: {losses}"
        )
    return "Unknown admin command. Available: stats"


COMMANDS = ("/start", "/signal", "/market", "/history", "/performance", "/settings", "/admin")


def unknown_command_reply() -> str:
    return "Unknown command. Try: " + ", ".join(COMMANDS)
