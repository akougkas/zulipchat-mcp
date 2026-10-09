"""Fake-only durable snapshots, delta ingestion, and MCP mention contracts."""

import threading
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP

from zulipchat_mcp.core.process_lease import ProcessLease
from zulipchat_mcp.core.tool_contract import ToolContractMiddleware
from zulipchat_mcp.services import bot_mentions
from zulipchat_mcp.services.bot_mentions import BotMentionInbox
from zulipchat_mcp.tools import agents


def message(message_id=11, **changes):
    return {
        "id": message_id,
        "type": "stream",
        "stream_id": 42,
        "display_recipient": "Agents-Channel",
        "subject": "Demo",
        "sender_id": 7,
        "sender_email": "owner@example.com",
        "timestamp": 1700000000,
        "content": "@**Clio** summarize this",
        "flags": ["mentioned"],
        **changes,
    }


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    client = MagicMock()
    client.client.get_profile.return_value = {
        "result": "success",
        "is_bot": True,
        "bot_type": 1,
        "user_id": 9,
    }
    client.register.return_value = {
        "result": "success",
        "queue_id": "queue",
        "last_event_id": -1,
    }
    client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [message()],
        "found_newest": True,
    }
    value = BotMentionInbox(
        client, tmp_path / "cache.sqlite3", "account-a", "Agents-Channel"
    )
    monkeypatch.setattr(value, "start", lambda: None)
    return value


def test_snapshot_registers_before_history_and_reuses_it_without_upstream_calls(inbox):
    inbox._bootstrap()
    inbox._ready = True
    assert [call[0] for call in inbox.client.mock_calls].index("register") < [
        call[0] for call in inbox.client.mock_calls
    ].index("get_messages_raw")
    for _ in range(25):
        assert inbox.poll(0, 20)["messages"][0]["id"] == 11
        inbox._bootstrap()
    assert inbox.client.get_messages_raw.call_count == 1
    assert inbox.client.register.call_count == 1
    assert inbox.client.client.get_profile.call_count == 1
    assert inbox.client.get_messages_raw.call_args.kwargs["use_cache"] is False


def test_overlap_replay_deduplicates_and_commits_message_and_event_watermarks(inbox):
    inbox._bootstrap()
    event = {"id": 4, "type": "message", "message": message(), "flags": ["mentioned"]}
    inbox._ingest_events([event, event])
    inbox._ready = True
    page = inbox.poll(0, 20)
    assert [item["id"] for item in page["messages"]] == [11]
    assert inbox._state("last_event_id") == 4
    assert inbox._state("message_cursor") == 11
    assert inbox.poll(11, 20)["messages"] == []


def test_event_level_flags_are_authoritative_and_wildcards_do_not_wake(inbox):
    inbox._ingest_events(
        [
            {"id": 1, "type": "message", "message": message(12), "flags": []},
            {
                "id": 2,
                "type": "message",
                "message": message(13),
                "flags": ["stream_wildcard_mentioned"],
            },
            {
                "id": 3,
                "type": "message",
                "message": message(14),
                "flags": ["mentioned"],
            },
        ]
    )
    inbox._ready = True
    assert [item["id"] for item in inbox.poll(0, 20)["messages"]] == [14]
    assert inbox._state("message_cursor") == 14


@pytest.mark.parametrize("event_type", ["delete_message", "update_message"])
def test_changed_or_deleted_input_is_removed_and_cursor_still_advances(
    inbox, event_type
):
    inbox._commit([message()], {})
    inbox._ingest_events([{"id": 7, "type": event_type, "message_ids": [11]}])
    inbox._ready = True
    page = inbox.poll(0, 20)
    assert page["messages"] == []
    assert page["next_after_message_id"] == 11
    with inbox._connect() as db:
        assert (
            db.execute("SELECT payload FROM messages WHERE id=11").fetchone()[0] == "{}"
        )


def test_persistence_failure_does_not_acknowledge_unprocessed_input(inbox):
    inbox._commit([], {"last_event_id": 1})
    with pytest.raises(ValueError, match="message ID"):
        inbox._ingest_events(
            [
                {
                    "id": 2,
                    "type": "message",
                    "message": message(0),
                    "flags": ["mentioned"],
                }
            ]
        )
    assert inbox._state("last_event_id") == 1


def test_expired_queue_recovery_uses_saved_message_id_and_deduplicates(inbox):
    inbox._bootstrap()
    inbox._ingest_events(
        [{"id": 3, "type": "message", "message": message(15), "flags": ["mentioned"]}]
    )
    inbox._commit([], {"queue_id": None})
    inbox.client.get_messages_raw.return_value["messages"] = [message(15), message(16)]
    inbox._bootstrap()
    assert inbox.client.get_messages_raw.call_args.kwargs["anchor"] == "15"
    assert inbox.client.get_messages_raw.call_args.kwargs["include_anchor"] is False
    inbox._ready = True
    assert [item["id"] for item in inbox.poll(0, 20)["messages"]] == [11, 15, 16]


def test_account_binding_and_symlink_are_rejected(inbox, tmp_path):
    with pytest.raises(ValueError, match="account mismatch"):
        BotMentionInbox(inbox.client, inbox.path, "account-b", "Agents-Channel")
    alias = tmp_path / "alias.sqlite3"
    alias.symlink_to(inbox.path)
    with pytest.raises(ValueError, match="symlink"):
        BotMentionInbox(inbox.client, alias, "account-a", "Agents-Channel")


def test_cached_messages_remain_readable_with_explicit_outage_health(inbox):
    inbox._commit([message()], {"bot_user_id": 9})
    inbox._error = "RATE_LIMIT_HIT"
    inbox._retry_after = 29.2
    page = inbox.poll(0, 20)
    assert page["status"] == "partial"
    assert page["messages"][0]["id"] == 11
    assert page["listener"]["retry_after_seconds"] == 30


def test_webhook_bot_is_rejected_before_queue_registration(inbox):
    inbox.client.client.get_profile.return_value["bot_type"] = 2
    with pytest.raises(RuntimeError, match="Generic bot"):
        inbox._bootstrap()
    inbox.client.register.assert_not_called()


def test_restart_verifies_bot_id_even_when_email_and_queue_are_unchanged(inbox):
    inbox._bootstrap()
    restarted = BotMentionInbox(inbox.client, inbox.path, "account-a", "Agents-Channel")
    inbox.client.client.get_profile.return_value["user_id"] = 999
    with pytest.raises(RuntimeError, match="Bot account ID changed"):
        restarted._bootstrap()
    assert inbox.client.client.get_profile.call_count == 2


def test_second_producer_is_rejected_before_any_api_call_and_lease_is_reusable(inbox):
    path = inbox.path.with_suffix(".lock")
    with ProcessLease(path):
        inbox._run()
        assert inbox._error.startswith("INBOX_ALREADY_OWNED")
        assert inbox._ready is False
        inbox.client.assert_not_called()
        assert not inbox.client.mock_calls
    with ProcessLease(path):
        assert path.stat().st_mode & 0o777 == 0o600


def test_producer_lock_symlink_is_rejected_without_api_calls(inbox, tmp_path):
    inbox.path.with_suffix(".lock").symlink_to(tmp_path / "another.lock")
    inbox._run()
    assert "symlink" in inbox._error
    assert not inbox.client.mock_calls


def test_one_background_queue_serves_many_local_polls(inbox, monkeypatch):
    release = threading.Event()
    polled = threading.Event()

    def long_poll(**kwargs):
        assert kwargs["dont_block"] is False
        polled.set()
        release.wait(2)
        return {"result": "success", "events": []}

    inbox.client.get_events.side_effect = long_poll
    monkeypatch.setattr(inbox, "start", BotMentionInbox.start.__get__(inbox))
    try:
        assert inbox.poll(0, 20)["messages"]
        assert polled.wait(1)
        for _ in range(25):
            assert inbox.poll(0, 20)["messages"]
        assert inbox.client.get_events.call_count == 1
        assert inbox.client.get_messages_raw.call_count == 1
    finally:
        inbox.stop()
        release.set()
        inbox._thread.join(2)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_registered_mention_contract_has_numeric_bot_provenance_and_raw_task_data(
    mode, inbox, monkeypatch
):
    inbox._bootstrap()
    inbox._ready = True
    config = MagicMock()
    config.has_bot_credentials.return_value = True
    coordinator = MagicMock()
    coordinator.default_owner_email.return_value = "owner@example.com"
    monkeypatch.setattr(agents, "get_config_manager", lambda: config)
    monkeypatch.setattr(agents, "_get_coordinator", lambda: coordinator)
    monkeypatch.setattr(bot_mentions, "get_mention_inbox", lambda *args: inbox)
    server = FastMCP("mention-contract")
    server.tool(agents.poll_agent_events)
    server.add_middleware(ToolContractMiddleware())
    async with Client(server, mode=mode) as client:
        result = (
            await client.call_tool(
                "poll_agent_events",
                {
                    "mentions_stream": "Agents-Channel",
                    "after_message_id": 0,
                    "auto_ack": False,
                    "wait_seconds": 0,
                },
            )
        ).data
        assert result["events"][0]["content"] == message()["content"]
        assert result["events"][0]["is_configured_owner"] is True
        assert result["bot_user_id"] == 9
        assert result["next_after_message_id"] == 11
        assert result["cache"]["source"] == "local_snapshot_and_event_deltas"
        invalid = await client.call_tool(
            "poll_agent_events",
            {"mentions_stream": "Agents-Channel", "session_id": "other"},
            raise_on_error=False,
        )
        assert invalid.is_error and invalid.structured_content["retryable"] is False


@pytest.mark.parametrize(
    "arguments",
    [
        {"mentions_stream": " "},
        {"mentions_stream": "Agents", "limit": 51},
        {"mentions_stream": "Agents", "after_message_id": -1},
        {"mentions_stream": "Agents", "wait_seconds": 26},
        {"after_message_id": 1},
    ],
)
def test_invalid_mention_poll_never_touches_upstream(arguments, monkeypatch):
    coordinator = MagicMock()
    monkeypatch.setattr(agents, "_get_coordinator", lambda: coordinator)
    assert agents.poll_agent_events(**arguments)["status"] == "error"
    coordinator.assert_not_called()
