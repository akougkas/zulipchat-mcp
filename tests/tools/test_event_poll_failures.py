"""Polling failures must not masquerade as successful empty observations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp.tools import event_management as events


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
    poll, cleanup = listener(
        [{"status": "error", "error": "queue expired", "code": "BAD_EVENT_QUEUE_ID"}]
    )
    result = await events.listen_events(["message"])
    assert result["status"] == "error"
    assert result["error"] == "queue expired"
    assert result["code"] == "BAD_EVENT_QUEUE_ID"
    assert result["event_count"] == 0
    assert poll.await_count == 1
    cleanup.assert_awaited_once_with("q")


async def test_backend_failures_stop_after_three_attempts(listener):
    failure = {"status": "error", "error": "unavailable", "code": "SERVER_ERROR"}
    poll, cleanup = listener([failure] * 3)
    result = await events.listen_events(["message"])
    assert result["status"] == "error"
    assert result["poll_failure_count"] == 3
    assert result["code"] == "SERVER_ERROR"
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
    assert result["polling_errors"][0]["error"] == "connection interrupted"
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
            {"status": "error", "error": "queue expired", "code": "BAD_EVENT_QUEUE_ID"},
        ]
    )
    cleanup.return_value = {"status": "error", "error": "cleanup unavailable"}
    result = await events.listen_events(["message"])
    assert result["status"] == "partial"
    assert result["collected_events"] == [{"id": 11}]
    assert result["code"] == "BAD_EVENT_QUEUE_ID"
    assert result["cleanup_error"]["error"] == "cleanup unavailable"
    assert poll.await_count == 2
    cleanup.assert_awaited_once_with("q")


async def test_duration_expiry_does_not_hide_unrecovered_failure(listener):
    poll, cleanup = listener([{"status": "error", "error": "unavailable"}])
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
    assert result["code"] == "BAD_EVENT_QUEUE_ID"


async def test_cancelled_listener_still_cleans_up_queue(listener):
    poll, cleanup = listener([asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await events.listen_events(["message"])
    assert poll.await_count == 1
    cleanup.assert_awaited_once_with("q")
