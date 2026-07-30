from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from jarvis.kernel.clock import FrozenClock
from jarvis.trading.config import TradingSettings
from jarvis.trading.database.store import InMemoryTradingStore
from jarvis.trading.models import User, UserRole
from jarvis.trading.telegram_agent.bot import TelegramBot

NOW = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)


@dataclass
class FakeTelegramClient:
    sent: list[tuple[int, str]] = field(default_factory=list)
    updates: list[dict] = field(default_factory=list)

    async def send_message(self, chat_id: int, text: str) -> dict:
        self.sent.append((chat_id, text))
        return {"ok": True}

    async def get_updates(self, *, offset: int | None = None, timeout: float = 30.0) -> list[dict]:
        batch = self.updates
        self.updates = []
        return batch


def make_update(*, update_id: int, telegram_id: int, text: str, username: str = "trader") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": telegram_id},
            "from": {"id": telegram_id, "username": username},
            "text": text,
        },
    }


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def store() -> InMemoryTradingStore:
    return InMemoryTradingStore()


def make_bot(
    *, client: FakeTelegramClient, store: InMemoryTradingStore, clock: FrozenClock, admin_ids=None
) -> TelegramBot:
    settings = TradingSettings(telegram_admin_ids=admin_ids or [], rate_limit_per_minute=3)
    return TelegramBot(client=client, store=store, settings=settings, clock=clock)  # type: ignore[arg-type]


async def test_handle_update_dispatches_a_known_command(store, clock):
    client = FakeTelegramClient()
    bot = make_bot(client=client, store=store, clock=clock)
    await bot.handle_update(make_update(update_id=1, telegram_id=111, text="/start"))
    assert len(client.sent) == 1
    chat_id, text = client.sent[0]
    assert chat_id == 111
    assert "Welcome" in text


async def test_handle_update_ignores_non_command_text(store, clock):
    client = FakeTelegramClient()
    bot = make_bot(client=client, store=store, clock=clock)
    await bot.handle_update(make_update(update_id=1, telegram_id=111, text="just chatting"))
    assert client.sent == []


async def test_handle_update_replies_for_unknown_commands(store, clock):
    client = FakeTelegramClient()
    bot = make_bot(client=client, store=store, clock=clock)
    await bot.handle_update(make_update(update_id=1, telegram_id=111, text="/nonsense"))
    assert "Unknown command" in client.sent[0][1]


async def test_admin_id_grants_admin_role_on_start(store, clock):
    client = FakeTelegramClient()
    bot = make_bot(client=client, store=store, clock=clock, admin_ids=[111])
    await bot.handle_update(make_update(update_id=1, telegram_id=111, text="/start"))
    user = await store.get_user_by_telegram_id(111)
    assert user is not None
    assert user.role == UserRole.ADMIN


async def test_rate_limiter_blocks_after_the_configured_number_of_commands(store, clock):
    client = FakeTelegramClient()
    bot = make_bot(client=client, store=store, clock=clock)  # limit is 3/minute
    for _ in range(3):
        await bot.handle_update(make_update(update_id=1, telegram_id=111, text="/market"))
    await bot.handle_update(make_update(update_id=1, telegram_id=111, text="/market"))
    assert "Rate limit" in client.sent[-1][1]


async def test_poll_once_processes_queued_updates_and_advances_offset(store, clock):
    client = FakeTelegramClient(
        updates=[
            make_update(update_id=5, telegram_id=111, text="/start"),
            make_update(update_id=6, telegram_id=111, text="/market"),
        ]
    )
    bot = make_bot(client=client, store=store, clock=clock)
    processed = await bot.poll_once()
    assert processed == 2
    assert len(client.sent) == 2


async def test_broadcast_sends_only_to_subscribers_with_notifications_on(store, clock):
    await store.upsert_user(User(telegram_id=1, username="on", created_at=NOW))
    off_user = User(telegram_id=2, username="off", created_at=NOW)
    off_user.settings.receive_signals = False
    await store.upsert_user(off_user)

    client = FakeTelegramClient()
    bot = make_bot(client=client, store=store, clock=clock)
    sent = await bot.broadcast("new signal!")
    assert sent == 1
    assert client.sent == [(1, "new signal!")]
