"""Plain async endpoint functions with a mocked client wrapper."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.tools import (
    mark_messaging,
    schedule_messaging,
    topic_management,
    users,
)

OK = {"result": "success"}


@pytest.fixture
def client(monkeypatch):
    client = MagicMock()
    client.supports.return_value = True
    client.get_stream_id.return_value = {**OK, "stream_id": 9}
    client.get_users.return_value = {
        **OK,
        "members": [{"user_id": 1, "full_name": "Ada"}],
    }
    for module in (topic_management, schedule_messaging, users, mark_messaging):
        monkeypatch.setattr(module, "get_client", lambda: client)
    return client


def _topic_messages(topics):
    def fetch(**kwargs):
        topic = kwargs["narrow"][1]["operand"]
        ids = topics.get(topic, [])
        return {**OK, "messages": [{"id": i} for i in ids]}

    return fetch


async def test_resolve_topic_renames_latest_message_with_change_all(client):
    client.get_messages_raw.side_effect = _topic_messages({"bug": [5, 8]})
    client.edit_message.return_value = OK

    result = await topic_management.resolve_topic("eng", "bug")

    assert result == {"status": "success", "topic": "✔ bug", "changed": True}
    client.get_stream_id.assert_called_once_with("eng")
    client.edit_message.assert_called_once_with(
        message_id=8, topic="✔ bug", propagate_mode="change_all"
    )
    narrow = client.get_messages_raw.call_args.kwargs["narrow"]
    assert narrow[0] == {"operator": "channel", "operand": 9}


async def test_resolve_topic_unresolves_and_is_idempotent(client):
    client.get_messages_raw.side_effect = _topic_messages({"✔ bug": [3]})
    client.edit_message.return_value = OK

    result = await topic_management.resolve_topic(9, "✔ bug", resolved=False)
    assert result["topic"] == "bug" and result["changed"] is True

    client.edit_message.reset_mock()
    result = await topic_management.resolve_topic(9, "bug", resolved=True)
    assert result == {"status": "success", "topic": "✔ bug", "changed": False}
    client.edit_message.assert_not_called()


async def test_resolve_topic_reports_missing_topic_and_api_errors(client):
    client.get_messages_raw.side_effect = _topic_messages({})
    assert (await topic_management.resolve_topic(9, "nope"))["status"] == "error"

    client.get_messages_raw.side_effect = _topic_messages({"bug": [1]})
    client.edit_message.return_value = {
        "result": "error",
        "code": "BAD_REQUEST",
        "msg": "no permission",
    }
    result = await topic_management.resolve_topic(9, "bug")
    assert result["error"] == "no permission"
    assert result["error_code"] == "BAD_REQUEST"


@pytest.mark.parametrize(
    "policy,value", [("inherit", 0), ("muted", 1), ("unmuted", 2), ("followed", 3)]
)
async def test_set_topic_visibility_maps_policy(client, policy, value):
    client.set_topic_visibility.return_value = OK
    result = await topic_management.set_topic_visibility("eng", "t", policy)
    assert result["status"] == "success" and result["stream_id"] == 9
    client.set_topic_visibility.assert_called_once_with(9, "t", value)


async def test_set_topic_visibility_unknown_stream(client):
    client.get_stream_id.return_value = {"result": "error", "msg": "Invalid stream"}
    result = await topic_management.set_topic_visibility("x", "t", "muted")
    assert result == {"status": "error", "error": "Invalid stream"}


async def test_message_history_is_compact(client):
    client.client.call_endpoint.return_value = {
        **OK,
        "message_history": [
            {"timestamp": 1, "user_id": 1, "topic": "a", "content": "one\ntwo"},
            {
                "timestamp": 2,
                "user_id": 1,
                "topic": "b",
                "prev_topic": "a",
                "content": "one\nTWO",
                "prev_content": "one\ntwo",
                "rendered_content": "<p>x</p>",
            },
        ],
    }
    result = await topic_management.get_message_history(42)

    client.client.call_endpoint.assert_called_once_with(
        "messages/42/history", method="GET", request={}
    )
    original, edit = result["history"]
    assert original == {
        "timestamp": 1,
        "user_id": 1,
        "user": "Ada",
        "content": "one\ntwo",
        "topic": "a",
    }
    assert edit["topic"] == ["a", "b"]
    assert edit["diff"] == "-two\n+TWO"
    assert "rendered_content" not in edit
    assert result["edit_count"] == 1


async def test_reminders_list_create_delete(client):
    call = client.client.call_endpoint
    call.return_value = {
        **OK,
        "reminders": [
            {
                "reminder_id": 4,
                "reminder_target_message_id": 42,
                "scheduled_delivery_timestamp": 0,
                "content": "long generated text",
            }
        ],
    }
    listed = await schedule_messaging.manage_reminders("list")
    assert listed["reminders"] == [
        {
            "reminder_id": 4,
            "message_id": 42,
            "deliver_at": "1970-01-01T00:00:00+00:00",
            "failed": False,
        }
    ]
    call.assert_called_with("reminders", method="GET", request={})

    call.return_value = {**OK, "reminder_id": 5}
    created = await schedule_messaging.manage_reminders(
        "create", message_id=42, deliver_at="2030-01-01T00:00:00", note="ship"
    )
    expected_ts = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
    call.assert_called_with(
        "reminders",
        method="POST",
        request={
            "message_id": 42,
            "scheduled_delivery_timestamp": expected_ts,
            "note": "ship",
        },
    )
    assert created["reminder_id"] == 5

    call.return_value = OK
    deleted = await schedule_messaging.manage_reminders("delete", reminder_id=5)
    call.assert_called_with("reminders/5", method="DELETE", request={})
    assert deleted["deleted"] is True


async def test_reminders_validate_and_surface_errors(client):
    assert (await schedule_messaging.manage_reminders("create"))["status"] == "error"
    assert (await schedule_messaging.manage_reminders("delete"))["status"] == "error"
    client.client.call_endpoint.return_value = {
        "result": "error",
        "code": "RATE_LIMIT_HIT",
        "msg": "slow",
        "retry-after": 3,
    }
    result = await schedule_messaging.manage_reminders("list")
    assert result["retry_after_seconds"] == 3 and result["retryable"] is True


@pytest.mark.parametrize("modern", [True, False])
async def test_set_typing_direct_and_channel(client, modern):
    client.supports.return_value = modern
    client.client.call_endpoint.return_value = OK

    assert (await users.set_typing("start", to=[1, 2]))["status"] == "success"
    client.client.call_endpoint.assert_called_with(
        "typing",
        method="POST",
        request={
            "op": "start",
            "type": "direct" if modern else "private",
            "to": [1, 2],
        },
    )

    await users.set_typing("stop", stream_id=9, topic="t")
    client.client.call_endpoint.assert_called_with(
        "typing",
        method="POST",
        request={
            "op": "stop",
            "type": "channel" if modern else "stream",
            "stream_id": 9,
            "topic": "t",
        },
    )


async def test_set_typing_validates_target(client):
    assert (await users.set_typing("start"))["status"] == "error"
    assert (await users.set_typing("start", to=[1], stream_id=9))["status"] == "error"
    assert (await users.set_typing("start", stream_id=9))["status"] == "error"
    client.client.call_endpoint.assert_not_called()


async def test_read_receipts_resolve_names(client):
    client.client.call_endpoint.return_value = {**OK, "user_ids": [1, 7]}
    result = await mark_messaging.get_read_receipts(42)
    client.client.call_endpoint.assert_called_once_with(
        "messages/42/read_receipts", method="GET", request={}
    )
    assert result["readers"] == [
        {"user_id": 1, "name": "Ada"},
        {"user_id": 7, "name": None},
    ]
    assert result["count"] == 2


async def test_read_receipts_error(client):
    client.client.call_endpoint.return_value = {
        "result": "error",
        "code": "BAD_REQUEST",
        "msg": "Invalid message(s)",
    }
    result = await mark_messaging.get_read_receipts(42)
    assert result["status"] == "error" and result["error"] == "Invalid message(s)"
