"""Direct test for events_v25._send_webhook with stubbed aiohttp."""

from __future__ import annotations

import sys

import pytest

from zulipchat_mcp.tools import events_v25 as ev


class _Resp:
    def __init__(self, status: int = 200):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json, headers, timeout):  # type: ignore[override]
        return _Resp(200)


class _AiohttpStub:
    class ClientTimeout:  # noqa: N801
        def __init__(self, total: int):
            self.total = total

    def ClientSession(self):  # type: ignore[override]
        return _Session()


@pytest.mark.asyncio
async def test_send_webhook_stubbed_aiohttp(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "aiohttp", _AiohttpStub())
    await ev._send_webhook("http://example", {"a": 1})
    # No assertion needed; the function should complete without error
