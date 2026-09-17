"""Regressions for filtered event cursors and async long polling."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock

from zulipchat_mcp.tools import event_management as events


async def test_filtered_events_still_advance_cursor(monkeypatch):
    monkeypatch.setattr(events, "get_client", MagicMock())
    monkeypatch.setattr(
        events,
        "register_events",
        AsyncMock(
            return_value={
                "status": "success",
                "queue_id": "q",
                "last_event_id": 10,
            }
        ),
    )
    poll = AsyncMock(
        side_effect=[
            {"status": "success", "events": [{"id": 11, "type": "presence"}]},
            {"status": "success", "events": []},
        ]
    )
    monkeypatch.setattr(events, "get_events", poll)
    cleanup = AsyncMock()
    monkeypatch.setattr(events, "deregister_events", cleanup)
    monkeypatch.setattr(events.asyncio, "sleep", AsyncMock())
    # Patch the module's clock, not asyncio's shared time module.
    monkeypatch.setattr(
        events, "time", MagicMock(monotonic=MagicMock(side_effect=[0, 0, 1, 2, 3]))
    )
    result = await events.listen_events(
        ["message"], duration=2, filters={"type": "message"}
    )
    assert result["event_count"] == 0
    assert poll.call_args_list[1].kwargs["last_event_id"] == 11
    cleanup.assert_awaited_once_with("q")


async def test_long_poll_does_not_block_event_loop(monkeypatch):
    release = threading.Event()
    entered = threading.Event()

    def blocking_poll(**kwargs):
        entered.set()
        release.wait(timeout=2)
        return {"result": "success", "events": []}

    monkeypatch.setattr(
        events, "get_client", lambda: MagicMock(get_events=blocking_poll)
    )
    task = asyncio.create_task(events.get_events("q", 0))
    try:
        for _ in range(100):
            await asyncio.sleep(0.01)
            if entered.is_set():
                break
        assert entered.is_set()
        assert not task.done(), "Zulip long poll blocked the event loop"
    finally:
        release.set()
        await task


async def test_http_task_callback_is_rejected_before_queue_registration(monkeypatch):
    from zulipchat_mcp.core import security

    monkeypatch.setattr(
        security, "get_http_headers", lambda **kwargs: {"host": "mcp.example"}
    )
    register = AsyncMock()
    monkeypatch.setattr(events, "register_events", register)
    result = await events.listen_events(
        ["message"], callback_url="http://127.0.0.1/private"
    )
    assert result["status"] == "error"
    register.assert_not_called()
