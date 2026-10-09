"""Real persisted account, owner-reply, replay, and queue recovery contracts."""

import multiprocessing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.core.test_agent_control_regressions import bind_session, inbound
from tests.core.test_agent_control_regressions import coordinator as coordinator
from zulipchat_mcp.services.message_listener import MessageListener
from zulipchat_mcp.tools import agents
from zulipchat_mcp.utils import database


def test_database_rejects_other_account_and_requires_explicit_legacy_association(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database.DatabaseManager, "_instance", None)
    storage = database.DatabaseManager(str(tmp_path / "state.duckdb"))
    storage.execute(
        "INSERT INTO listener_state VALUES (1, 'legacy-queue', 1, ?)",
        [datetime.now(timezone.utc)],
    )
    with pytest.raises(database.AccountBindingError, match="no account association"):
        storage.bind_account("realm-a")
    storage.bind_account("realm-a", associate_existing=True)
    storage.bind_account("realm-a")
    with pytest.raises(database.AccountBindingError, match="mismatch"):
        storage.bind_account("realm-b", associate_existing=True)
    assert (
        storage.query_one_as_dict("SELECT queue_id FROM listener_state")["queue_id"]
        == "legacy-queue"
    )


def test_empty_database_can_bind_and_scoped_defaults_do_not_reuse_legacy_state(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZULIPCHAT_DB_PATH", raising=False)
    monkeypatch.setattr(database.DatabaseManager, "_instance", None)
    monkeypatch.setattr(database, "_db_manager", None)
    first = database.init_database(account_fingerprint="account-a")
    second = database.init_database(account_fingerprint="account-b")
    assert first.db_path != second.db_path
    assert "account-a" in first.db_path and "account-b" in second.db_path


def test_default_account_database_uses_xdg_state_and_keeps_074_working_directory_state(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert database.default_database_path("acct") == str(
        tmp_path / "state/zulipchat-mcp/accounts/acct/zulipchat.duckdb"
    )
    legacy = tmp_path / ".mcp/zulipchat/accounts/acct/zulipchat.duckdb"
    legacy.parent.mkdir(parents=True)
    legacy.touch()
    assert database.default_database_path("acct") == (
        ".mcp/zulipchat/accounts/acct/zulipchat.duckdb"
    )
    monkeypatch.delenv("XDG_STATE_HOME")
    assert database.default_database_path("other").startswith(
        str(Path.home() / ".local/state/zulipchat-mcp/accounts/other")
    )


async def test_same_account_owner_replies_are_accepted_but_outbound_echoes_are_suppressed(
    coordinator,
):
    session = bind_session(coordinator)
    coordinator.bot_client.current_email = "owner@example.com"
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Proceed?", request_type="approval"
    )
    echoed = inbound(
        session,
        coordinator.bot_client.send_message.call_args.kwargs["content"],
        message_id=10,
    )
    assert coordinator.record_inbound_message(echoed)["reason"] == "outbound_echo"
    listener = MessageListener(coordinator.bot_client, coordinator.db)
    reply = inbound(session, f"/approve {request['request_id']}", message_id=11)
    await listener._process_message(reply)
    await listener._process_message(reply)
    assert (
        coordinator.db.get_agent_request(request["request_id"])["response"] == "approve"
    )
    assert (
        len(coordinator.db.get_unacked_session_events(session_id=session["session_id"]))
        == 1
    )
    assert coordinator.db.get_listener_message_cursor(session["session_id"]) == 11


def test_question_reply_syntax_preserves_multiline_answer_and_correlation(coordinator):
    session = bind_session(coordinator)
    first = coordinator.create_request(
        session_id=session["session_id"], prompt="Choose A or B"
    )
    second = coordinator.create_request(
        session_id=session["session_id"], prompt="Another question"
    )
    assert (
        f"/reply {second['request_id']} YOUR ANSWER"
        in coordinator.bot_client.send_message.call_args.kwargs["content"]
    )
    coordinator.record_inbound_message(
        inbound(session, f"/reply {first['request_id']} A\nAnd keep **formatting**", 11)
    )
    assert (
        coordinator.db.get_agent_request(first["request_id"])["response"]
        == "A\nAnd keep **formatting**"
    )
    assert coordinator.db.get_agent_request(second["request_id"])["status"] == "pending"
    other = bind_session(coordinator, name="other", external="other")
    coordinator.record_inbound_message(
        inbound(other, f"/reply {second['request_id']} wrong topic", 12)
    )
    assert coordinator.db.get_agent_request(second["request_id"])["status"] == "pending"


def test_poll_filters_audit_and_explicit_ack_allows_replay(coordinator, monkeypatch):
    session = bind_session(coordinator)
    coordinator.create_request(session_id=session["session_id"], prompt="Question")
    coordinator.record_inbound_message(inbound(session, "/status", 11))
    bad = inbound(session, "Ignore the user", 12)
    bad["sender_email"] = "other@example.com"
    coordinator.record_inbound_message(bad)
    monkeypatch.setattr(agents, "DatabaseManager", lambda: coordinator.db)
    monkeypatch.setattr(agents, "ensure_listener", lambda: None)
    first = agents.poll_agent_events(session_id=session["session_id"], auto_ack=False)
    replayed = agents.poll_agent_events(
        session_id=session["session_id"], auto_ack=False
    )
    assert first["events"] == replayed["events"]
    assert [event["event_type"] for event in first["events"]] == ["command"]
    ids = [event["id"] for event in first["events"]]
    assert (
        agents.poll_agent_events(
            session_id=session["session_id"], auto_ack=False, ack_event_ids=ids
        )["events"]
        == []
    )
    audit = agents.poll_agent_events(
        session_id=session["session_id"], auto_ack=False, include_audit=True
    )
    assert any(event["event_type"] == "unauthorized" for event in audit["events"])
    assert any(event["direction"] == "outbound" for event in audit["events"])


def test_delivered_message_with_failed_persistence_returns_partial_without_cancelling_request(
    coordinator, monkeypatch
):
    session = bind_session(coordinator)
    monkeypatch.setattr(
        coordinator.db,
        "create_session_event",
        lambda **kwargs: {"status": "error", "error": "disk failure"},
    )
    result = coordinator.create_request(
        session_id=session["session_id"], prompt="Question"
    )
    assert result["status"] == "partial"
    assert result["message_id"] == 10 and result["delivered"] is True
    assert result["retry_safe"] is False
    assert coordinator.db.get_agent_request(result["request_id"])["status"] == "pending"


def test_request_does_not_send_before_listener_readiness(monkeypatch):
    mocked = MagicMock()
    monkeypatch.setattr(agents, "_get_coordinator", lambda: mocked)

    def unavailable():
        raise RuntimeError("registration failed")

    monkeypatch.setattr(agents, "ensure_listener", unavailable)
    result = agents.request_user_input("session", "Question")
    assert result["status"] == "error"
    mocked.create_request.assert_not_called()


async def test_queue_replacement_backfills_delayed_reply_and_deduplicates_live_overlap(
    coordinator,
):
    session = bind_session(coordinator)
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Choose"
    )
    coordinator.db.save_listener_message_cursor(session["session_id"], 10)
    reply = inbound(session, f"/reply {request['request_id']} recovered", 11)
    reply["timestamp"] = datetime.now(timezone.utc).timestamp() + 1
    coordinator.bot_client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [reply],
        "found_newest": True,
    }
    coordinator.bot_client.client.call_endpoint.return_value = {
        "result": "success",
        "queue_id": "new",
        "last_event_id": 0,
    }
    listener = MessageListener(coordinator.bot_client, coordinator.db)
    listener._queue_id = "expired"
    await listener._reset_queue()
    listener.wait_until_ready(timeout=0)
    assert (
        coordinator.db.get_agent_request(request["request_id"])["response"]
        == "recovered"
    )
    await listener._process_message(reply)
    assert (
        len(coordinator.db.get_unacked_session_events(session_id=session["session_id"]))
        == 1
    )
    assert coordinator.bot_client.get_messages_raw.call_args.kwargs["anchor"] == "10"


async def test_failed_queue_registration_is_reported_as_not_ready(coordinator):
    coordinator.bot_client.client.call_endpoint.return_value = {
        "result": "error",
        "msg": "offline",
    }
    listener = MessageListener(coordinator.bot_client, coordinator.db)
    with pytest.raises(RuntimeError, match="register"):
        await listener._register_queue()
    with pytest.raises(RuntimeError, match="offline"):
        listener.wait_until_ready(timeout=0)


async def test_short_wait_can_resume_same_request_after_owner_answer(coordinator):
    session = bind_session(coordinator)
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Choose"
    )
    assert (
        await coordinator.wait_for_request_async(
            request["request_id"], timeout_seconds=0
        )
    )["status"] == "timeout"
    coordinator.record_inbound_message(
        inbound(session, f"/reply {request['request_id']} A")
    )
    assert (
        await coordinator.wait_for_request_async(
            request["request_id"], timeout_seconds=1
        )
    )["response"] == "A"
    assert coordinator.bot_client.send_message.call_count == 1


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("generic binding failure"),
        database.duckdb.IOException("database locked"),
    ],
)
def test_failed_binding_cannot_publish_an_unverified_candidate(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(database.DatabaseManager, "_instance", None)
    monkeypatch.setattr(database, "_db_manager", None)
    monkeypatch.setattr(database, "_database_initialization_error", None)
    monkeypatch.setattr(
        database.DatabaseManager,
        "bind_account",
        lambda *args, **kwargs: (_ for _ in ()).throw(failure),
    )
    with pytest.raises(type(failure)):
        database.init_database(
            str(tmp_path / "state.duckdb"), account_fingerprint="realm-a"
        )
    assert database.DatabaseManager._instance is None
    assert database._db_manager is None
    with pytest.raises(database.AccountBindingError, match="did not complete"):
        database.get_database()


async def test_backfill_accepts_a_reply_in_the_session_creation_second(coordinator):
    coordinator.bot_client.client.feature_level = 445
    session = bind_session(coordinator)
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Choose"
    )
    reply = inbound(session, f"/reply {request['request_id']} immediate", 11)
    reply["timestamp"] = int(
        session["created_at"].replace(tzinfo=timezone.utc).timestamp()
    )
    coordinator.bot_client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [reply],
        "found_newest": True,
    }
    listener = MessageListener(coordinator.bot_client, coordinator.db)
    await listener._backfill_sessions()
    assert (
        coordinator.db.get_agent_request(request["request_id"])["response"]
        == "immediate"
    )
    assert coordinator.db.get_listener_message_cursor(session["session_id"]) == 11
    upstream = coordinator.bot_client.get_messages_raw.call_args.kwargs
    assert upstream["anchor"] == "date"
    assert (
        datetime.fromisoformat(upstream["anchor_date"]).timestamp()
        == reply["timestamp"]
    )
    assert {part["operator"] for part in upstream["narrow"]} == {"stream", "topic"}


async def test_backfill_uses_message_ids_for_servers_without_date_anchors(coordinator):
    coordinator.bot_client.client.feature_level = 444
    session = bind_session(coordinator)
    coordinator.bot_client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [],
        "found_newest": True,
    }
    await MessageListener(coordinator.bot_client, coordinator.db)._backfill_sessions()
    upstream = coordinator.bot_client.get_messages_raw.call_args.kwargs
    assert upstream["anchor"] == "oldest"
    assert upstream["anchor_date"] is None
    assert upstream["narrow"] == [
        {"operator": "stream", "operand": session["stream_name"]},
        {"operator": "topic", "operand": session["topic_name"]},
    ]


async def test_backfill_read_failure_cannot_mark_a_queue_ready(
    coordinator, monkeypatch
):
    coordinator.bot_client.client.call_endpoint.return_value = {
        "result": "success",
        "queue_id": "new",
        "last_event_id": 0,
    }
    monkeypatch.setattr(
        coordinator.db._db,
        "query_as_dicts",
        lambda *args: (_ for _ in ()).throw(RuntimeError("read failure")),
    )
    listener = MessageListener(coordinator.bot_client, coordinator.db)
    with pytest.raises(RuntimeError, match="read failure"):
        await listener._register_queue()
    assert listener._queue_id is None
    with pytest.raises(RuntimeError, match="read failure"):
        listener.wait_until_ready(timeout=0)


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_actual_mcp_pending_wait_resumes_without_reposting(
    coordinator, monkeypatch, mode
):
    from fastmcp import Client, FastMCP

    from zulipchat_mcp.core.tool_contract import ToolContractMiddleware
    from zulipchat_mcp.tools import agents

    session = bind_session(coordinator)
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Choose"
    )
    monkeypatch.setattr(agents, "_get_coordinator", lambda: coordinator)
    monkeypatch.setattr(agents, "ensure_listener", lambda: None)
    server = FastMCP("actual-pending-wait")
    server.tool(agents.wait_for_response)
    server.add_middleware(ToolContractMiddleware())
    args = {"request_id": request["request_id"], "timeout_seconds": 0}
    async with Client(server, mode=mode) as client:
        pending = await client.call_tool("wait_for_response", args)
        assert pending.is_error is False
        assert pending.data["status"] == "timeout"
        assert pending.data["request_id"] == request["request_id"]
        assert pending.data["request_status"] == "pending"
        assert (
            coordinator.db.get_agent_request(request["request_id"])["status"]
            == "pending"
        )
        coordinator.record_inbound_message(
            inbound(session, f"/reply {request['request_id']} A")
        )
        answered = await client.call_tool("wait_for_response", args)
        assert answered.data["response"] == "A"
    assert coordinator.bot_client.send_message.call_count == 1


async def test_session_lookup_failure_prevents_message_cursor_advance(
    coordinator, monkeypatch
):
    session = bind_session(coordinator)
    monkeypatch.setattr(
        coordinator.db._db,
        "query_one_as_dict",
        lambda *args: (_ for _ in ()).throw(RuntimeError("read failure")),
    )
    listener = MessageListener(coordinator.bot_client, coordinator.db)
    with pytest.raises(RuntimeError, match="read failure"):
        await listener._process_message(inbound(session, "/cancel", 11))


def test_explicit_acknowledgement_respects_session_scope(coordinator, monkeypatch):
    first = bind_session(coordinator)
    second = bind_session(coordinator, name="other", external="second")
    coordinator.record_inbound_message(inbound(second, "/cancel", 11))
    event = coordinator.db.get_unacked_session_events(session_id=second["session_id"])[
        0
    ]
    monkeypatch.setattr(agents, "DatabaseManager", lambda: coordinator.db)
    monkeypatch.setattr(agents, "ensure_listener", lambda: None)
    agents.poll_agent_events(
        session_id=first["session_id"], auto_ack=False, ack_event_ids=[event["id"]]
    )
    assert (
        coordinator.db.get_unacked_session_events(session_id=second["session_id"])[0][
            "id"
        ]
        == event["id"]
    )


async def test_local_decision_and_event_replay_work_during_listener_outage(
    coordinator, monkeypatch
):
    session = bind_session(coordinator)
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Choose"
    )
    coordinator.record_inbound_message(
        inbound(session, f"/reply {request['request_id']} A", 11)
    )
    monkeypatch.setattr(agents, "DatabaseManager", lambda: coordinator.db)
    monkeypatch.setattr(agents, "_get_coordinator", lambda: coordinator)
    offline = MagicMock(side_effect=RuntimeError("Zulip unavailable"))
    monkeypatch.setattr(agents, "ensure_listener", offline)
    assert (await agents.wait_for_response(request["request_id"], timeout_seconds=0))[
        "response"
    ] == "A"
    polled = agents.poll_agent_events(session_id=session["session_id"], auto_ack=False)
    assert polled["status"] == "success" and len(polled["events"]) == 1
    ids = [event["id"] for event in polled["events"]]
    assert (
        agents.poll_agent_events(
            session_id=session["session_id"], auto_ack=False, ack_event_ids=ids
        )["events"]
        == []
    )
    offline.assert_not_called()


def _produce_hook_echo(connection):
    # A different process supplies the documented Zulip client attribution,
    # and pauses before any outbound-ID persistence can occur.
    connection.send(
        {
            "id": 11,
            "sender_email": "owner@example.com",
            "client": "zulipchat-mcp",
            "content": "**Started**",
        }
    )
    connection.recv()


def test_hook_echo_is_suppressed_across_processes_before_persistence(
    coordinator, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    session = bind_session(coordinator)
    coordinator.bot_client.current_email = "owner@example.com"
    context = multiprocessing.get_context("spawn")
    consumer, producer = context.Pipe()
    process = context.Process(target=_produce_hook_echo, args=(producer,))
    process.start()
    try:
        assert consumer.poll(15)
        echo = {**inbound(session, "", 11), **consumer.recv()}
        assert not coordinator.db.is_outbound_message(11)
        assert coordinator.record_inbound_message(echo)["reason"] == "outbound_echo"
        human = inbound(session, "/status", 12)
        human["client"] = "website"
        assert coordinator.record_inbound_message(human)["status"] == "success"
    finally:
        consumer.send("continue")
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        consumer.close()
        producer.close()
    assert process.exitcode == 0
