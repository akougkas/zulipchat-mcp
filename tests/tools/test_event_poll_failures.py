"""Polling failures must not masquerade as successful empty observations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp.core.errors import tool_error
from zulipchat_mcp.tools import event_management as events

EXPIRED = tool_error("queue expired", "BAD_EVENT_QUEUE_ID")


@pytest.fixture
def listener(monkeypatch):
    clock = [0.0]

    async def sleep(delay):
        clock[0] += delay

    monkeypatch.setattr(events, "time", MagicMock(monotonic=lambda: clock[0]))
    monkeypatch.setattr(events.asyncio, "sleep", sleep)
    monkeypatch.setattr(events, "get_client", MagicMock())
    monkeypatch.setattr(
        events,
        "register_events",
        AsyncMock(
            return_value={"status": "success", "queue_id": "q", "last_event_id": 10}
        ),
    )
    cleanup = AsyncMock(return_value={"status": "success", "queue_id": "q"})
    monkeypatch.setattr(events, "deregister_events", cleanup)

    def install(responses):
        poll = AsyncMock(side_effect=responses)
        monkeypatch.setattr(events, "get_events", poll)
        return poll, cleanup

    return install


async def test_terminal_queue_error_stops_immediately_and_preserves_code(listener):
    poll, cleanup = listener([EXPIRED])
    result = await events.listen_events(["message"])
    assert result["status"] == "error"
    assert result["error"]["message"] == "queue expired"
    assert result["error"]["code"] == "BAD_EVENT_QUEUE_ID"
    assert result["event_count"] == 0
    assert poll.await_count == 1
    cleanup.assert_awaited_once_with("q")


async def test_backend_failures_stop_after_three_attempts(listener):
    failure = tool_error("unavailable", "SERVER_ERROR")
    poll, cleanup = listener([failure] * 3)
    result = await events.listen_events(["message"])
    assert result["status"] == "error"
    assert result["poll_failure_count"] == 3
    assert result["error"]["code"] == "SERVER_ERROR"
    assert poll.await_count == 3
    assert result["duration_seconds"] == 6
    cleanup.assert_awaited_once_with("q")


async def test_transient_failure_recovers_without_advancing_cursor(listener):
    poll, cleanup = listener(
        [
            OSError("connection interrupted"),
            {"status": "success", "events": [{"id": 11, "type": "message"}]},
            {"status": "success", "events": []},
        ]
    )
    result = await events.listen_events(["message"], duration=4)
    assert result["status"] == "success"
    assert result["event_count"] == 1
    assert result["poll_failure_count"] == 1
    assert result["polling_errors"][0]["message"] == "connection interrupted"
    assert result["polling_errors"][0]["code"] == "INTERNAL_ERROR"
    assert [call.kwargs["last_event_id"] for call in poll.await_args_list] == [
        10,
        10,
        11,
    ]
    cleanup.assert_awaited_once_with("q")


async def test_failure_after_events_returns_partial_and_reports_cleanup_failure(
    listener,
):
    poll, cleanup = listener(
        [
            {"status": "success", "events": [{"id": 11}]},
            EXPIRED,
        ]
    )
    cleanup.return_value = tool_error("cleanup unavailable", "ZULIP_ERROR")
    result = await events.listen_events(["message"])
    assert result["status"] == "partial"
    assert result["collected_events"] == [{"id": 11}]
    assert result["error"]["code"] == "BAD_EVENT_QUEUE_ID"
    assert result["cleanup_error"]["error"]["message"] == "cleanup unavailable"
    assert poll.await_count == 2
    cleanup.assert_awaited_once_with("q")


async def test_duration_expiry_does_not_hide_unrecovered_failure(listener):
    poll, cleanup = listener([tool_error("unavailable", "ZULIP_ERROR")])
    result = await events.listen_events(["message"], duration=1)
    assert result["status"] == "error"
    assert result["duration_seconds"] == 1
    assert poll.await_count == 1
    cleanup.assert_awaited_once_with("q")


async def test_get_events_preserves_backend_error_code(monkeypatch):
    client = MagicMock()
    client.get_events.return_value = {
        "result": "error",
        "msg": "queue expired",
        "code": "BAD_EVENT_QUEUE_ID",
    }
    monkeypatch.setattr(events, "get_client", lambda: client)
    result = await events.get_events("expired", 10)
    assert result["status"] == "error"
    assert result["error"]["code"] == "BAD_EVENT_QUEUE_ID"
    assert result["error"]["recovery"]["tool"] == "register_events"


async def test_cancelled_listener_still_cleans_up_queue(listener):
    poll, cleanup = listener([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await events.listen_events(["message"])
    assert poll.await_count == 1
    cleanup.assert_awaited_once_with("q")


async def test_listener_stops_at_max_events(listener):
    batch = [{"id": i, "type": "message"} for i in range(11, 16)]
    poll, cleanup = listener(
        [{"status": "success", "events": batch}, {"status": "success", "events": []}]
    )
    result = await events.listen_events(["message"], duration=60, max_events=3)
    assert result["event_count"] == 3
    assert result["reached_max_events"] is True
    assert [e["id"] for e in result["collected_events"]] == [11, 12, 13]
    assert poll.await_count == 1
    cleanup.assert_awaited_once_with("q")


async def test_get_events_bounds_one_batch(monkeypatch):
    client = MagicMock()
    client.get_events.return_value = {
        "result": "success",
        "events": [{"id": i, "type": "message"} for i in range(5, 0, -1)],
    }
    monkeypatch.setattr(events, "get_client", lambda: client)
    result = await events.get_events("q", 0, max_events=2)
    assert [e["id"] for e in result["events"]] == [1, 2]
    assert result["more_events"] is True
    assert list(result)[-1] == "events"
