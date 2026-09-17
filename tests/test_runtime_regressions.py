"""Regression tests for concurrency, bounded work, and API selection."""

import asyncio
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zulipchat_mcp.core.error_handling import RateLimitConfig, RateLimiter
from zulipchat_mcp.services.message_listener import MessageListener
from zulipchat_mcp.tools import agents, mark_messaging, search, users


@pytest.mark.asyncio
@pytest.mark.parametrize("lazy_sdk", [False, True])
async def test_slow_zulip_call_does_not_block_the_event_loop(monkeypatch, lazy_sdk):
    started, release = threading.Event(), threading.Event()

    def slow_call(*args, **kwargs):
        started.set()
        release.wait(2)
        return {"result": "success", "members": []}

    class LazyClient:
        @property
        def client(self):
            slow_call()
            sdk = MagicMock()
            sdk.call_endpoint.return_value = {"result": "success", "user_id": 1}
            return sdk

    wrapper = LazyClient() if lazy_sdk else MagicMock(get_users=slow_call)
    monkeypatch.setattr(users, "get_client", lambda: wrapper)
    pending = asyncio.create_task(
        users.get_own_user() if lazy_sdk else users.get_users()
    )
    try:
        assert await asyncio.to_thread(started.wait, 1)
        assert not pending.done()
    finally:
        release.set()
    assert (await pending)["status"] == "success"


@pytest.mark.asyncio
async def test_rate_limiter_reserves_distinct_slots_for_concurrent_callers():
    with patch("zulipchat_mcp.core.error_handling.time.monotonic", return_value=10):
        limiter = RateLimiter(
            RateLimitConfig(max_requests=1, time_window=1, burst_limit=1)
        )
        delays = await asyncio.gather(*(limiter.acquire() for _ in range(4)))
    assert delays == [0, 1, 2, 3]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_listener_acknowledges_only_processed_events(fail):
    db = MagicMock()
    listener = MessageListener(MagicMock(), db)
    listener._queue_id = "queue"
    listener._last_event_id = 40
    listener._get_events = AsyncMock(
        return_value=[{"type": "message", "id": 41, "message": {"id": 10}}]
    )

    async def process(message):
        listener.request_stop()
        if fail:
            raise RuntimeError("disk failure")

    listener._process_message = process
    await listener.start()
    if fail:
        assert listener._last_event_id == 40
        db.save_listener_state.assert_not_called()
    else:
        assert listener._last_event_id == 41
        db.save_listener_state.assert_called_once_with("queue", 41)


@pytest.mark.asyncio
async def test_listener_backoff_remains_bounded_after_many_errors():
    listener = MessageListener(MagicMock(), MagicMock())
    listener._consecutive_errors = 10000

    async def unavailable():
        listener.request_stop()
        return None

    listener._get_events = unavailable
    await listener.start()
    assert listener._consecutive_errors == 10001


@pytest.mark.asyncio
async def test_mark_all_read_processes_more_than_one_page(monkeypatch):
    update = AsyncMock(
        side_effect=[
            {
                "status": "success",
                "processed_count": 1000,
                "updated_count": 900,
                "last_processed_id": 2000,
                "found_newest": False,
            },
            {
                "status": "success",
                "processed_count": 250,
                "updated_count": 200,
                "last_processed_id": 2250,
                "found_newest": True,
            },
        ]
    )
    monkeypatch.setattr(mark_messaging, "update_message_flags_for_narrow", update)
    result = await mark_messaging.mark_all_as_read()
    assert result["updated_count"] == 1100
    assert result["processed_count"] == 1250
    assert update.call_args_list[1].kwargs["anchor"] == 2000
    assert update.call_args_list[1].kwargs["include_anchor"] is False


@pytest.mark.asyncio
async def test_search_honors_upper_time_bound_sort_and_limit(monkeypatch):
    client = MagicMock()
    base = {
        "sender_full_name": "Owner",
        "sender_email": "owner@example.com",
        "content": "message",
        "type": "stream",
    }
    client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [{**base, "id": i, "timestamp": i} for i in [2, 5, 9]],
    }
    monkeypatch.setattr(search, "get_client", lambda: client)
    result = await search.search_messages(
        before_time="1970-01-01T02:00:06+02:00", sort_by="newest", limit=1
    )
    assert [message["id"] for message in result["messages"]] == [5]
    args = client.get_messages_raw.call_args.kwargs
    assert args["anchor"] == "date"
    assert datetime.fromisoformat(args["anchor_date"]) == datetime(
        1970, 1, 1, 0, 0, 6, tzinfo=timezone.utc
    )
    assert args["num_after"] == 0


@pytest.mark.asyncio
async def test_teleport_reply_is_scoped_and_newer_than_send(monkeypatch):
    client = MagicMock(identity="user", current_email="owner@example.com")
    client.send_message.return_value = {"result": "success", "id": 100}
    client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [
            {"id": 99, "sender_email": "other@example.com", "content": "old"},
            {"id": 101, "sender_email": "owner@example.com", "content": "self"},
            {"id": 102, "sender_email": "other@example.com", "content": "new reply"},
        ],
    }
    monkeypatch.setattr(agents, "get_client", lambda: client)
    monkeypatch.setattr(agents, "get_config_manager", MagicMock())
    result = await agents.teleport_chat(
        "#selected", "question", topic="specific", wait_for_reply=True
    )
    assert result["reply"] == "new reply"
    assert client.get_messages_raw.call_args.kwargs["narrow"] == [
        {"operator": "stream", "operand": "selected"},
        {"operator": "topic", "operand": "specific"},
    ]
    assert client.get_messages_raw.call_args.kwargs["anchor"] == "100"
