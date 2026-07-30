"""A thin wrapper over the Telegram Bot HTTP API.

No bot framework dependency: the surface this system needs — send a
message, long-poll for updates — is two endpoints, and ``httpx`` is already
a Jarvis dependency. Keeping it this small also keeps it trivially mockable
in tests via ``httpx.MockTransport``.
"""

from __future__ import annotations

from typing import Any

import httpx


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.telegram.org",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_root = f"{base_url}/bot{token}"
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        response = await self._client.post(
            f"{self._api_root}/sendMessage", json={"chat_id": chat_id, "text": text}
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    async def get_updates(
        self, *, offset: int | None = None, timeout: float = 30.0
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": int(timeout)}
        if offset is not None:
            params["offset"] = offset
        response = await self._client.get(
            f"{self._api_root}/getUpdates", params=params, timeout=timeout + 10
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        updates: list[dict[str, Any]] = payload.get("result", [])
        return updates

    async def aclose(self) -> None:
        await self._client.aclose()
