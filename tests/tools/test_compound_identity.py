"""In-flight stdio operations keep their account when another task switches it."""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp import config
from zulipchat_mcp.tools import ai_analytics, event_management, mark_messaging, search
from zulipchat_mcp.tools.system import switch_identity


@pytest.fixture
def identities(monkeypatch):
    manager = MagicMock()
    manager.has_bot_credentials.return_value = True
    user = MagicMock(identity="user", current_email="user@example.com")
    bot = MagicMock(identity="bot", current_email="bot@example.com")
    monkeypatch.setattr(config, "_config_manager", manager)
    monkeypatch.setattr(config, "_current_identity", "user")
    monkeypatch.setattr(
        config, "_get_cached_client", lambda manager, use_bot: bot if use_bot else user
    )
    return user, bot


class BackendBarrier:
    """Pause a real to_thread call while the other asyncio task changes identity."""

    def __init__(self):
        self.entered = threading.Event()
        self.resume = threading.Event()

    def pause(self):
        self.entered.set()
        assert self.resume.wait(10), "Test did not release the backend call"

    async def switch(self, bot):
        assert await asyncio.to_thread(self.entered.wait, 10)
        switched = await switch_identity("bot")
        assert switched["status"] == "success"
        assert switched["identity"] == "bot"
        assert config.get_client() is bot


async def result_and_next_client(operation):
    result = await operation
    return result, config.get_client()


@pytest.mark.parametrize("phase", ["register", "poll"])
async def test_event_queue_lifecycle_retains_client(identities, phase):
    user, bot = identities
    barrier = BackendBarrier()

    def register(**kwargs):
        if phase == "register":
            barrier.pause()
        return {"result": "success", "queue_id": "user-queue", "last_event_id": -1}

    def poll(**kwargs):
        assert kwargs["queue_id"] == "user-queue"
        if phase == "poll":
            barrier.pause()
        # Terminal response makes the test independent of wall-clock sleeps.
        return {"result": "error", "code": "BAD_EVENT_QUEUE_ID", "msg": "expired"}

    user.register.side_effect = register
    user.get_events.side_effect = poll
    user.deregister.return_value = {"result": "success"}
    task = asyncio.create_task(
        result_and_next_client(event_management.listen_events(["message"], duration=30))
    )
    try:
        await barrier.switch(bot)
    finally:
        barrier.resume.set()
    result, next_client = await asyncio.wait_for(task, 10)
    assert result["code"] == "BAD_EVENT_QUEUE_ID"
    assert next_client is bot
    user.get_events.assert_called_once()
    user.deregister.assert_called_once_with("user-queue")
    assert bot.mock_calls == []


async def test_cancelled_listener_cleans_original_queue_and_restores_binding(
    identities,
):
    user, bot = identities
    barrier = BackendBarrier()
    user.register.return_value = {
        "result": "success",
        "queue_id": "user-queue",
        "last_event_id": -1,
    }
    user.get_events.side_effect = lambda **kwargs: barrier.pause()
    user.deregister.return_value = {"result": "success"}

    async def listen():
        with pytest.raises(asyncio.CancelledError):
            await event_management.listen_events(["message"], duration=30)
        return config.get_client()

    task = asyncio.create_task(listen())
    try:
        await barrier.switch(bot)
        task.cancel()
        assert await asyncio.wait_for(task, 10) is bot
    finally:
        barrier.resume.set()
    user.deregister.assert_called_once_with("user-queue")
    assert bot.mock_calls == []


@pytest.mark.parametrize(
    "name,arguments,phase",
    [
        ("manage_message_flags", {"scope": "all"}, "page"),
        ("manage_message_flags", {"scope": "stream", "stream_id": 7}, "resolve"),
        (
            "manage_message_flags",
            {"scope": "topic", "stream_id": 7, "topic_name": "t"},
            "page",
        ),
        ("manage_message_flags", {"scope": "narrow", "stream_id": 7}, "resolve"),
        ("mark_all_as_read", {}, "page"),
        ("mark_stream_as_read", {"stream_id": 7}, "resolve"),
        ("mark_topic_as_read", {"stream_id": 7, "topic_name": "t"}, "resolve"),
        ("mark_messages_unread", {"stream_id": 7}, "resolve"),
        ("star_messages", {"stream_id": 7}, "page"),
        ("unstar_messages", {"stream_id": 7}, "page"),
    ],
)
async def test_flag_resolution_and_all_pages_retain_client(
    identities, name, arguments, phase
):
    user, bot = identities
    barrier = BackendBarrier()

    def streams(**kwargs):
        if phase == "resolve":
            barrier.pause()
        return {
            "result": "success",
            "streams": [{"stream_id": 7, "name": "user-stream"}],
        }

    requests = []

    def update(endpoint, *, method, request):
        requests.append(request)
        if phase == "page" and len(requests) == 1:
            barrier.pause()
        return {
            "result": "success",
            "processed_count": 1,
            "updated_count": 1,
            "last_processed_id": 10 + len(requests),
            "found_newest": len(requests) == 2,
        }

    user.get_streams.side_effect = streams
    user.client.call_endpoint.side_effect = update
    bot.client.call_endpoint.return_value = {"result": "success", "found_newest": True}
    if name == "manage_message_flags":
        arguments = {**arguments, "flag": "starred", "action": "remove"}
    task = asyncio.create_task(
        result_and_next_client(getattr(mark_messaging, name)(**arguments))
    )
    try:
        await barrier.switch(bot)
        # A concurrent operation must use the newly selected identity.
        assert (
            await mark_messaging.update_message_flags_for_narrow([], "add", "read")
        )["status"] == "success"
    finally:
        barrier.resume.set()
    result, next_client = await asyncio.wait_for(task, 10)
    assert result["status"] == "success" and result["updated_count"] == 2
    assert next_client is bot
    assert len(requests) == 2 and requests[1]["anchor"] == 11
    if arguments.get("stream_id"):
        assert requests[0]["narrow"][0] == {
            "operator": "stream",
            "operand": "user-stream",
        }
    bot.client.call_endpoint.assert_called_once()
    bot.get_streams.assert_not_called()


@pytest.mark.parametrize("report", [False, True])
async def test_analytics_searches_keep_one_client_across_streams(
    identities, monkeypatch, report
):
    user, bot = identities
    barrier = BackendBarrier()
    streams = []

    def messages(**kwargs):
        streams.append(
            next(
                part["operand"]
                for part in kwargs["narrow"]
                if part["operator"] == "stream"
            )
        )
        if len(streams) == 1:
            barrier.pause()
        return {
            "result": "success",
            "messages": [
                {
                    "id": len(streams),
                    "timestamp": int(time.time()),
                    "sender_full_name": "Owner",
                    "sender_email": "user@example.com",
                    "content": "progress",
                    "type": "stream",
                }
            ],
        }

    user.get_messages_raw.side_effect = messages
    bot.get_messages_raw.return_value = {"result": "success", "messages": []}
    monkeypatch.setattr(ai_analytics, "generate", AsyncMock(return_value="analysis"))
    operation = (
        ai_analytics.intelligent_report_generator("weekly", ["one", "two"])
        if report
        else ai_analytics.analyze_team_activity_with_llm(["one", "two"], "progress")
    )
    task = asyncio.create_task(result_and_next_client(operation))
    try:
        await barrier.switch(bot)
        assert (await search.search_messages(stream="bot-stream"))[
            "status"
        ] == "success"
    finally:
        barrier.resume.set()
    result, next_client = await asyncio.wait_for(task, 10)
    assert result["status"] == "success"
    assert streams == ["one", "two"]
    assert next_client is bot
    bot.get_messages_raw.assert_called_once()


async def test_binding_restores_nested_context_and_exception(identities):
    user, bot = identities
    with config.bind_client(user):
        with pytest.raises(RuntimeError), config.bind_client(bot):
            assert await asyncio.to_thread(config.get_client) is bot
            raise RuntimeError("failure")
        assert config.get_client() is user
    assert config.get_client() is user
