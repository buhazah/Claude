from __future__ import annotations

import httpx
import pytest

from jarvis.trading.telegram_agent.client import TelegramClient


async def test_send_message_posts_to_the_bot_api():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/bottest-token/sendMessage"
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    telegram = TelegramClient("test-token", client=client)
    result = await telegram.send_message(123, "hello")
    assert result["ok"] is True
    assert len(calls) == 1
    await client.aclose()


async def test_send_message_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"ok": False, "description": "forbidden"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    telegram = TelegramClient("test-token", client=client)
    with pytest.raises(httpx.HTTPStatusError):
        await telegram.send_message(123, "hello")
    await client.aclose()


async def test_get_updates_returns_the_result_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/bottest-token/getUpdates"
        return httpx.Response(
            200, json={"ok": True, "result": [{"update_id": 1}, {"update_id": 2}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    telegram = TelegramClient("test-token", client=client)
    updates = await telegram.get_updates(offset=5, timeout=1.0)
    assert len(updates) == 2
    await client.aclose()


async def test_get_updates_passes_the_offset_when_given():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["offset"] = request.url.params.get("offset")
        return httpx.Response(200, json={"ok": True, "result": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    telegram = TelegramClient("test-token", client=client)
    await telegram.get_updates(offset=42, timeout=1.0)
    assert captured["offset"] == "42"
    await client.aclose()


async def test_get_updates_omits_offset_when_not_given():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["has_offset"] = "offset" in request.url.params
        return httpx.Response(200, json={"ok": True, "result": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    telegram = TelegramClient("test-token", client=client)
    await telegram.get_updates(timeout=1.0)
    assert captured["has_offset"] is False
    await client.aclose()
