"""Fake-only durable snapshots, delta ingestion, and MCP mention contracts."""

import threading
from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.core.process_lease import ProcessLease
from zulipchat_mcp.services.bot_mentions import BotMentionInbox


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


def direct(message_id=21, **changes):
    return {
        "id": message_id,
        "type": "private",
        "sender_id": 7,
        "sender_email": "owner@example.com",
        "display_recipient": [
            {"id": 7, "email": "owner@example.com", "full_name": "Owner"},
            {"id": 9, "email": "bot@example.com", "full_name": "Clio"},
        ],
        "timestamp": 1700000100,
        "content": "please look at this",
        "flags": [],
        **changes,
    }


def fake_client(history):
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
        "messages": history,
        "found_newest": True,
    }
    return client


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    value = BotMentionInbox(
        fake_client([message()]),
        tmp_path / "cache.sqlite3",
        "account-a",
        "Agents-Channel",
    )
    monkeypatch.setattr(value, "start", lambda: None)
    return value


@pytest.fixture
def dm_inbox(tmp_path, monkeypatch):
    value = BotMentionInbox(
        fake_client([direct(21), direct(22, sender_id=9, sender_email="b@e.com")]),
        tmp_path / "direct.sqlite3",
        "account-a",
        None,
    )
    monkeypatch.setattr(value, "start", lambda: None)
    return value


def test_first_start_begins_from_now_and_reuses_the_queue_without_upstream_calls(
    inbox,
):
    inbox.client.get_messages_raw.side_effect = [
        {"result": "success", "messages": [message(11)], "found_newest": True},
        {"result": "success", "messages": [], "found_newest": True},
    ]
    inbox._bootstrap()
    calls = [call[0] for call in inbox.client.mock_calls]
    assert calls.index("register") < calls.index("get_messages_raw")
    first = inbox.client.get_messages_raw.call_args_list[0].kwargs
    assert first["anchor"] == "newest" and first["num_before"] == 0
    assert inbox._state("message_cursor") == 11
    assert inbox.pending()["messages"] == []  # old messages are not work
    for _ in range(25):
        inbox._bootstrap()
    assert inbox.client.get_messages_raw.call_count == 2
    assert inbox.client.register.call_count == 1
    assert inbox.client.client.get_profile.call_count == 1
    assert inbox.client.get_messages_raw.call_args.kwargs["use_cache"] is False


def test_overlap_replay_deduplicates_and_commits_message_and_event_watermarks(inbox):
    inbox._bootstrap()
    event = {"id": 4, "type": "message", "message": message(), "flags": ["mentioned"]}
    inbox._ingest_events([event, event])
    page = inbox.pending()
    assert [item["id"] for item in page["messages"]] == [11]
    assert inbox._state("last_event_id") == 4
    assert inbox._state("message_cursor") == 11
    inbox.settle(11)
    assert inbox.pending()["messages"] == []


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
    assert [item["id"] for item in inbox.pending()["messages"]] == [14]
    assert inbox._state("message_cursor") == 14


@pytest.mark.parametrize("event_type", ["delete_message", "update_message"])
def test_changed_or_deleted_input_is_dropped_unless_already_queued(inbox, event_type):
    inbox._commit([message(11), message(12)], {})
    inbox.enqueue(message(12), "ch:42:demo")
    inbox._ingest_events([{"id": 7, "type": event_type, "message_ids": [11, 12]}])
    assert inbox.pending()["messages"] == []
    with inbox._connect() as db:
        assert db.execute("SELECT id, state FROM messages").fetchall() == [
            (12, "queued")
        ]


def test_channel_inbox_ignores_the_bots_own_self_mentions(inbox):
    inbox._bot_id = 99
    inbox._commit([message(11), message(12, sender_id=99)], {})
    page = inbox.pending()
    assert [item["id"] for item in page["messages"]] == [11]


def test_rendering_only_updates_such_as_link_previews_keep_the_input(inbox):
    inbox._commit([message()], {})
    inbox._ingest_events(
        [
            {
                "id": 7,
                "type": "update_message",
                "message_ids": [11],
                "rendering_only": True,
            }
        ]
    )
    assert [item["id"] for item in inbox.pending()["messages"]] == [11]


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
    inbox._commit([message(11)], {"message_cursor": 11})
    inbox._bootstrap()
    inbox._ingest_events(
        [{"id": 3, "type": "message", "message": message(15), "flags": ["mentioned"]}]
    )
    inbox._commit([], {"queue_id": None})
    inbox.client.get_messages_raw.return_value["messages"] = [message(15), message(16)]
    inbox._bootstrap()
    assert inbox.client.get_messages_raw.call_args.kwargs["anchor"] == "15"
    assert inbox.client.get_messages_raw.call_args.kwargs["include_anchor"] is False
    assert [item["id"] for item in inbox.pending()["messages"]] == [11, 15, 16]


def test_account_binding_and_symlink_are_rejected(inbox, tmp_path):
    with pytest.raises(ValueError, match="account mismatch"):
        BotMentionInbox(inbox.client, inbox.path, "account-b", "Agents-Channel")
    alias = tmp_path / "alias.sqlite3"
    alias.symlink_to(inbox.path)
    with pytest.raises(ValueError, match="symlink"):
        BotMentionInbox(inbox.client, alias, "account-a", "Agents-Channel")


def test_queued_messages_remain_readable_with_explicit_outage_health(inbox):
    inbox._commit([message()], {"bot_user_id": 9})
    inbox._error = "RATE_LIMIT_HIT"
    inbox._retry_after = 29.2
    page = inbox.pending()
    assert page["error"] == "RATE_LIMIT_HIT"
    assert page["messages"][0]["id"] == 11
    assert page["retry_after_seconds"] == 30


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


def test_the_bridge_lease_rejects_a_symlinked_lock(inbox, tmp_path):
    lock = inbox.path.with_suffix(".lock")
    lock.symlink_to(tmp_path / "another.lock")
    with pytest.raises(ValueError, match="symlink"):
        with ProcessLease(lock):
            pass
    assert not inbox.client.mock_calls


def test_one_background_event_queue_serves_many_local_reads(inbox, monkeypatch):
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
        inbox._commit([message()], {})
        assert inbox.pending()["messages"]
        assert polled.wait(1)
        for _ in range(25):
            assert inbox.pending()["messages"]
        assert inbox.client.get_events.call_count == 1
        assert inbox.client.get_messages_raw.call_count == 2  # newest, then after
    finally:
        inbox.stop()
        release.set()
        inbox._thread.join(2)


def test_direct_inbox_registers_dm_narrow_first_and_skips_the_bots_own_messages(
    dm_inbox,
):
    dm_inbox._bootstrap()
    calls = [call[0] for call in dm_inbox.client.mock_calls]
    assert calls.index("register") < calls.index("get_messages_raw")
    register = dm_inbox.client.register.call_args.kwargs
    assert register["narrow"] == [["is", "dm"]]
    assert register["event_types"] == ["message", "update_message", "delete_message"]
    history = dm_inbox.client.get_messages_raw.call_args.kwargs
    assert history["narrow"] == [{"operator": "is", "operand": "dm"}]
    page = dm_inbox.pending()
    assert [item["id"] for item in page["messages"]] == [21]
    # The excluded self-sent message still advances the upstream cursor.
    assert dm_inbox._state("message_cursor") == 22


@pytest.mark.parametrize(
    "level,operand", [(176, "private"), (177, "dm"), (0, "dm"), ("n/a", "dm")]
)
def test_direct_narrow_uses_is_private_only_before_feature_level_177(
    dm_inbox, level, operand
):
    dm_inbox.client.client.feature_level = level
    dm_inbox._bootstrap()
    assert dm_inbox.client.register.call_args.kwargs["narrow"] == [["is", operand]]
    history = dm_inbox.client.get_messages_raw.call_args.kwargs["narrow"]
    assert history == [{"operator": "is", "operand": operand}]


def test_direct_inbox_ingests_dms_without_mentions_and_ignores_channel_traffic(
    dm_inbox,
):
    dm_inbox._bootstrap()
    dm_inbox._ingest_events(
        [
            {"id": 1, "type": "message", "message": direct(23), "flags": ["read"]},
            {
                "id": 2,
                "type": "message",
                "message": message(24),
                "flags": ["mentioned"],
            },
            {
                "id": 3,
                "type": "message",
                "message": direct(25, sender_id=9),
                "flags": ["read"],
            },
            {"id": 4, "type": "message", "message": direct(23), "flags": ["read"]},
        ]
    )
    assert [item["id"] for item in dm_inbox.pending()["messages"]] == [21, 23]
    assert dm_inbox._state("message_cursor") == 25
    assert dm_inbox._state("last_event_id") == 4


def test_channel_inbox_still_rejects_direct_messages(inbox):
    inbox._ingest_events(
        [{"id": 1, "type": "message", "message": direct(30), "flags": ["mentioned"]}]
    )
    assert inbox.pending()["messages"] == []


def test_direct_inbox_tombstones_edits_and_recovers_after_queue_expiry(dm_inbox):
    dm_inbox._bootstrap()
    dm_inbox._ingest_events([{"id": 5, "type": "update_message", "message_ids": [21]}])
    assert dm_inbox.pending()["messages"] == []
    dm_inbox._ingest_events(
        [{"id": 6, "type": "message", "message": direct(26), "flags": []}]
    )
    dm_inbox._commit([], {"queue_id": None})
    dm_inbox.client.get_messages_raw.return_value["messages"] = [
        direct(26),
        direct(27),
    ]
    dm_inbox._bootstrap()
    kwargs = dm_inbox.client.get_messages_raw.call_args.kwargs
    assert kwargs["anchor"] == "26" and kwargs["include_anchor"] is False
    assert [item["id"] for item in dm_inbox.pending()["messages"]] == [26, 27]


def test_a_prompt_moves_new_queued_running_and_is_deleted_when_done(inbox):
    import sqlite3
    import time

    inbox._commit([message(11), message(12), message(13)], {})
    assert inbox.enqueue({**message(11), "text": "summarize"}, "ch:42:demo")
    assert not inbox.enqueue(message(11), "ch:42:demo")  # only a new row
    inbox.settle(12)  # an answer or a command: handled, nothing kept
    assert [m["id"] for m in inbox.pending()["messages"]] == [13]
    assert inbox.held("queued") == [
        ("ch:42:demo", {**message(11), "text": "summarize"})
    ]
    taken = inbox.take("ch:42:demo")
    assert [m["text"] for m in taken] == ["summarize"]
    assert inbox.take("ch:42:demo") == []
    assert [m["id"] for _, m in inbox.held("running")] == [11]
    inbox._commit([message(11, content="replayed")], {})  # never resets work
    assert inbox.held("running")[0][1]["text"] == "summarize"
    inbox.done([11])
    assert inbox.held("running") == []

    with sqlite3.connect(inbox.path) as db:
        db.execute(
            "UPDATE messages SET stored=? WHERE id=13", (time.time() - 31 * 86400,)
        )
    inbox._commit([message(14)], {})
    # Other people's text does not stay on disk.
    assert [m["id"] for m in inbox.pending()["messages"]] == [14]


def test_a_new_scope_registers_a_new_event_queue(inbox):
    inbox._commit([], {"queue_id": "old"})
    reopened = BotMentionInbox(inbox.client, inbox.path, "account-a", None)
    assert reopened._state("queue_id") is None
    again = BotMentionInbox(inbox.client, inbox.path, "account-a", None)
    again._commit([], {"queue_id": "kept"})
    assert (
        BotMentionInbox(inbox.client, inbox.path, "account-a", None)._state("queue_id")
        == "kept"
    )


def test_inbox_file_from_the_cursor_era_keeps_only_undelivered_work(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(
            "CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);"
            "CREATE TABLE messages(id INTEGER PRIMARY KEY, payload TEXT NOT NULL,"
            " deleted INTEGER NOT NULL DEFAULT 0);"
            "INSERT INTO metadata VALUES('delivered_cursor', '5');"
            "INSERT INTO messages(id, payload) VALUES(5, '{\"id\": 5}');"
            "INSERT INTO messages(id, payload) VALUES(6, '{\"id\": 6}');"
            "INSERT INTO messages(id, payload, deleted) VALUES(7, '{}', 1);"
        )
    opened = BotMentionInbox(fake_client([]), path, "account-a", "Agents-Channel")
    assert opened.pending()["messages"] == [{"id": 6}]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT stored FROM messages").fetchone()[0] > 0
