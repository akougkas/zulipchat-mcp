"""Exercise persisted session and approval behavior, not just mocked SQL calls."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.claude_hooks import _wait_for_topic_decision
from zulipchat_mcp.core.agent_control import AgentCoordinator
from zulipchat_mcp.core.agent_protocol import make_session_topic, parse_control_message
from zulipchat_mcp.utils import database, database_manager


@pytest.fixture
def coordinator(tmp_path, monkeypatch):
    monkeypatch.setattr(database.DatabaseManager, "_instance", None)
    storage = database.DatabaseManager(str(tmp_path / "state.duckdb"))
    monkeypatch.setattr(database_manager, "get_database", lambda: storage)
    bot = MagicMock(current_email="bot@example.com")
    bot.send_message.return_value = {"result": "success", "id": 10}
    result = AgentCoordinator(db=database_manager.DatabaseManager(), bot_client=bot)
    return result


def bind_session(coordinator, name="agent", external="external-1"):
    agent = coordinator.register_agent(
        agent_name=name, owner_email="owner@example.com", stream_name="Agents-Channel"
    )["agent"]
    return coordinator.ensure_session(
        agent_id=agent["agent_id"],
        external_session_id=external,
        project_dir="/work/MyProject",
    )["session"]


def inbound(session, content, message_id=11):
    return {
        "id": message_id,
        "sender_email": "owner@example.com",
        "type": "stream",
        "display_recipient": session["stream_name"],
        "subject": session["topic_name"],
        "content": content,
    }


def test_approval_is_bound_to_one_request_and_terminal_decision(coordinator):
    session = bind_session(coordinator)
    first = coordinator.create_request(
        session_id=session["session_id"], prompt="One?", request_type="approval"
    )["request_id"]
    second = coordinator.create_request(
        session_id=session["session_id"], prompt="Two?", request_type="approval"
    )["request_id"]
    coordinator.record_inbound_message(inbound(session, "approve"))
    assert coordinator.db.get_agent_request(first)["status"] == "pending"
    assert coordinator.db.get_agent_request(second)["status"] == "pending"
    reply = inbound(session, f"/approve {first}", 12)
    coordinator.record_inbound_message(reply)
    coordinator.record_inbound_message(reply)  # Retry the same delivered event.
    assert coordinator.db.get_agent_request(first)["response"] == "approve"
    assert coordinator.db.get_agent_request(second)["status"] == "pending"
    coordinator.db.update_agent_request(first, status="timeout", response="timeout")
    assert coordinator.db.get_agent_request(first)["status"] == "answered"
    events = coordinator.db.get_unacked_session_events(session_id=session["session_id"])
    assert len([event for event in events if event["direction"] == "inbound"]) == 1


def test_poll_timeout_does_not_cancel_other_waiters(coordinator):
    session = bind_session(coordinator)
    request = coordinator.create_request(
        session_id=session["session_id"], prompt="Question?"
    )["request_id"]
    assert coordinator.wait_for_request(request, timeout_seconds=0)["status"] == "error"
    assert coordinator.db.get_agent_request(request)["status"] == "pending"


def test_failed_announcement_cancels_request(coordinator):
    session = bind_session(coordinator)
    coordinator.bot_client.send_message.return_value = {
        "result": "error",
        "msg": "unavailable",
    }
    assert (
        coordinator.create_request(
            session_id=session["session_id"], prompt="Proceed?", request_type="approval"
        )["status"]
        == "error"
    )
    assert coordinator.db.get_latest_pending_request(session["session_id"]) is None


def test_ensuring_session_preserves_topic_and_project(coordinator):
    session = bind_session(coordinator)
    updated = coordinator.ensure_session(
        agent_id=session["agent_id"], external_session_id="external-1"
    )["session"]
    assert updated["topic_name"] == session["topic_name"]
    assert updated["project_name"] == session["project_name"]
    assert updated["project_dir"] == session["project_dir"]


def test_session_topic_cannot_be_taken_by_another_agent(coordinator):
    first = bind_session(coordinator)
    second = bind_session(coordinator, name="second")
    result = coordinator.ensure_session(
        agent_id=second["agent_id"], topic_name=first["topic_name"]
    )
    assert result["status"] == "error"
    assert (
        coordinator.db.get_agent_session(first["session_id"])["agent_id"]
        == first["agent_id"]
    )


def test_concurrent_sessions_cannot_claim_the_same_topic(coordinator):
    agents = [
        coordinator.register_agent(
            agent_name=f"agent-{i}",
            owner_email="owner@example.com",
            stream_name="Agents-Channel",
        )["agent"]
        for i in range(2)
    ]
    start = Barrier(2)

    def bind(agent):
        start.wait(timeout=5)
        return coordinator.ensure_session(
            agent_id=agent["agent_id"],
            external_session_id=agent["agent_id"],
            topic_name="shared-topic",
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(bind, agents))
    assert sorted(result["status"] for result in results) == ["error", "success"]


def test_topics_disambiguate_long_external_session_ids():
    prefix = "common-prefix-" * 4
    assert make_session_topic("project", "agent", prefix + "1") != make_session_topic(
        "project", "agent", prefix + "2"
    )


def test_commands_preserve_argument_case_and_require_complete_approvals():
    assert parse_control_message("/run Tests/MyCase.py").arguments == "Tests/MyCase.py"
    assert parse_control_message("/approve req-123 but skip tests").decision is None
    assert parse_control_message("approve ID: Req-123").request_id == "Req-123"


def test_hook_skips_decisions_for_other_requests_and_senders():
    coordinator = MagicMock()
    session = {"stream_name": "Agents-Channel", "topic_name": "topic"}
    replies = [
        inbound(session, "/approve other-request"),
        inbound(session, "approve"),
        inbound(session, "/approve request-123"),
        inbound(session, "/deny request-123", 12),
    ]
    replies[2]["sender_email"] = "stranger@example.com"
    coordinator.bot_client.get_messages_raw.return_value = {
        "result": "success",
        "messages": replies,
    }
    decision = _wait_for_topic_decision(
        coordinator,
        stream_name="Agents-Channel",
        topic_name="topic",
        owner_email="owner@example.com",
        request_id="request-123",
        min_message_id=10,
        timeout_seconds=1,
    )
    assert decision["decision"] == "deny"
