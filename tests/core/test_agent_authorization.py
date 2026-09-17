"""Regression coverage for approval authorization before database mutation."""

from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.core.agent_control import AgentCoordinator


@pytest.mark.parametrize(
    "sender, session_id, in_topic, expected_updates",
    [
        ("stranger@example.com", "session-1", True, 0),
        ("owner@example.com", "session-other", True, 0),
        ("owner@example.com", "session-1", False, 0),
        ("owner@example.com", "session-1", True, 1),
    ],
)
def test_explicit_request_id_requires_owner_and_matching_session(
    sender, session_id, in_topic, expected_updates
):
    db = MagicMock()
    db.get_agent_request.return_value = {
        "request_id": "request-1",
        "session_id": session_id,
        "status": "pending",
    }
    db.get_agent_session_for_topic.return_value = (
        {
            "session_id": "session-1",
            "agent_id": "agent-1",
            "owner_email": "owner@example.com",
        }
        if in_topic
        else None
    )
    bot = MagicMock(current_email="bot@example.com")
    coordinator = AgentCoordinator(db=db, bot_client=bot)
    coordinator.record_inbound_message(
        {
            "sender_email": sender,
            "type": "stream",
            "display_recipient": "Agents-Channel",
            "subject": "session-topic",
            "content": "approve ID: request-1",
        }
    )
    assert db.update_agent_request.call_count == expected_updates
