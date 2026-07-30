"""Telegram Agent: wires updates to command handlers and pushes signals out.

Long-polling (``getUpdates``) rather than a webhook: it needs no public
endpoint or TLS termination to run, which matches "minimal human
intervention" better than a deployment that is broken until someone points
DNS at it.
"""

from __future__ import annotations

from typing import Any

import structlog

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock
from jarvis.trading.config import TradingSettings
from jarvis.trading.database.store import TradingStore
from jarvis.trading.telegram_agent import commands
from jarvis.trading.telegram_agent.client import TelegramClient
from jarvis.trading.telegram_agent.ratelimit import RateLimiter

log = structlog.get_logger(__name__)


class TelegramBot:
    def __init__(
        self,
        *,
        client: TelegramClient,
        store: TradingStore,
        settings: TradingSettings,
        clock: Clock = SYSTEM_CLOCK,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._settings = settings
        self._clock = clock
        self._rate_limiter = rate_limiter or RateLimiter(
            max_per_minute=settings.rate_limit_per_minute, clock=clock
        )
        self._offset: int | None = None

    def _is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self._settings.telegram_admin_ids

    async def dispatch(self, command: str, args: str, *, telegram_id: int, username: str) -> str:
        is_admin = self._is_admin(telegram_id)
        match command:
            case "/start":
                return await commands.handle_start(
                    store=self._store,
                    telegram_id=telegram_id,
                    username=username,
                    is_admin=is_admin,
                    now=self._clock.now(),
                )
            case "/signal":
                return await commands.handle_signal(store=self._store)
            case "/market":
                return await commands.handle_market(store=self._store)
            case "/history":
                return await commands.handle_history(store=self._store)
            case "/performance":
                return await commands.handle_performance(store=self._store)
            case "/settings":
                return await commands.handle_settings(
                    store=self._store, telegram_id=telegram_id, args=args
                )
            case "/admin":
                return await commands.handle_admin(store=self._store, is_admin=is_admin, args=args)
            case _:
                return commands.unknown_command_reply()

    async def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        sender = message.get("from") or {}
        telegram_id = sender.get("id")
        username = sender.get("username", "") or ""
        text = (message.get("text") or "").strip()

        if not text.startswith("/") or telegram_id is None or chat_id is None:
            return

        if not self._rate_limiter.allow(telegram_id):
            await self._client.send_message(chat_id, "Rate limit exceeded — please slow down.")
            return

        command, _, args = text.partition(" ")
        command = command.split("@")[0].lower()
        reply = await self.dispatch(
            command, args.strip(), telegram_id=telegram_id, username=username
        )
        if reply:
            await self._client.send_message(chat_id, reply)

    async def poll_once(self) -> int:
        """Fetch and process one batch of pending updates. Returns how many."""
        updates = await self._client.get_updates(
            offset=self._offset, timeout=self._settings.telegram_poll_timeout_s
        )
        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                self._offset = update_id + 1
            try:
                await self.handle_update(update)
            except Exception as exc:
                log.warning("telegram_update_failed", error=str(exc))
        return len(updates)

    async def broadcast(self, text: str) -> int:
        """Send ``text`` to every subscriber who has notifications on."""
        sent = 0
        for user in await self._store.list_users():
            if not user.settings.receive_signals:
                continue
            try:
                await self._client.send_message(user.telegram_id, text)
                sent += 1
            except Exception as exc:
                log.warning(
                    "telegram_broadcast_failed", telegram_id=user.telegram_id, error=str(exc)
                )
        return sent
