"""Boundary regressions from the full source audit."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp import claude_hooks
from zulipchat_mcp.tools import event_management


def test_generated_topics_are_bounded_and_keep_distinct_session_ids():
    from zulipchat_mcp.core.agent_protocol import make_session_topic

    topics = {
        make_session_topic(
            "long-project-name" * 5,
            "agent" * 10,
            external_session_id=f"shared-prefix-{'x' * 60}-{i}",
        )
        for i in range(10)
    }
    assert len(topics) == 10
    assert all(len(topic) <= 60 for topic in topics)


def test_metrics_exposition_escapes_labels_and_declares_each_family_once():
    from zulipchat_mcp.utils.metrics import get_metrics_text, metrics

    metrics.reset()
    metrics.increment_counter("calls", labels={"tool": 'quote" slash\\ line\n'})
    metrics.increment_counter("calls", labels={"tool": "other"})
    metrics.record_histogram("duration", 1.5, labels={"tool": "other"})
    metrics.record_histogram("duration", 2.5, labels={"tool": "second"})
    text = get_metrics_text()
    assert text.count("# TYPE calls counter") == 1
    assert 'calls{tool="quote\\" slash\\\\ line\\n"} 1' in text
    assert "# TYPE duration_count gauge" in text
    assert 'duration_count{tool="other"} 1' in text
    assert 'duration_count{tool="other"} 1\nduration_count{tool="second"} 1\n' in text
    assert "}_" not in text
    metrics.reset()


def test_setup_uvx_command_matches_generated_arguments(monkeypatch):
    from zulipchat_mcp import setup_wizard

    monkeypatch.setattr(setup_wizard.shutil, "which", lambda command: f"/bin/{command}")
    config = setup_wizard.generate_mcp_config(
        {"path": "/tmp/user.zuliprc"}, use_uvx=True
    )
    assert config["command"] == "/bin/uvx"
    assert config["args"][0] == "zulipchat-mcp"


def test_service_replacement_is_refused_while_previous_listener_is_stopping(
    monkeypatch,
):
    from zulipchat_mcp.core import service_manager

    previous = MagicMock()
    previous.stop.return_value = False
    monkeypatch.setattr(service_manager, "_instance", previous)
    with pytest.raises(RuntimeError, match="still stopping"):
        service_manager.init_service_manager(MagicMock())
    service_manager.shutdown_service_manager()
    assert service_manager._instance is previous


@pytest.mark.asyncio
async def test_event_page_limit_preserves_unconsumed_events(monkeypatch):
    monkeypatch.setattr(event_management, "get_client", MagicMock())
    monkeypatch.setattr(
        event_management,
        "register_events",
        AsyncMock(
            return_value={"status": "success", "queue_id": "q", "last_event_id": 0}
        ),
    )
    all_events = [{"id": 1}, {"id": 2, "type": "message"}, {"id": 3, "type": "message"}]

    async def poll(**kwargs):
        assert kwargs["dont_block"] is True
        return {
            "status": "success",
            "events": [
                event for event in all_events if event["id"] > kwargs["last_event_id"]
            ],
        }

    fetch = AsyncMock(side_effect=poll)
    monkeypatch.setattr(event_management, "get_events", fetch)
    monkeypatch.setattr(event_management, "deregister_events", AsyncMock())
    monkeypatch.setattr(event_management.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        event_management,
        "time",
        MagicMock(monotonic=MagicMock(side_effect=[0, 0, 1, 2, 3])),
    )
    result = await event_management.listen_events(
        ["message"], duration=2, filters={"type": "message"}, max_events_per_poll=2
    )
    assert [event["id"] for event in result["collected_events"]] == [2, 3]
    assert fetch.call_args_list[1].kwargs["last_event_id"] == 2


@pytest.mark.parametrize(
    "persisted",
    [
        None,
        {"status": "cancelled", "response": "approve"},
        {"status": "answered", "response": "deny"},
    ],
)
def test_hook_cannot_override_stored_denial_or_missing_approval(monkeypatch, persisted):
    coordinator = MagicMock()
    coordinator.create_request.return_value = {
        "status": "success",
        "request_id": "request",
        "message_id": 10,
    }
    coordinator.db.update_agent_request.return_value = {"status": "success"}
    coordinator.db.get_agent_request.return_value = persisted
    monkeypatch.setattr(
        claude_hooks,
        "_wait_for_topic_decision",
        lambda *a, **kw: {"decision": "approve"},
    )
    result = claude_hooks._handle_permission_request(
        coordinator,
        {
            "session_id": "session",
            "stream_name": "agents",
            "topic_name": "session",
            "owner_email": "owner@example.com",
        },
        {},
        1,
    )
    assert result["hookSpecificOutput"]["decision"]["behavior"] == "deny"


@pytest.mark.asyncio
async def test_listen_events_waits_out_server_retry_after(monkeypatch):
    monkeypatch.setattr(
        event_management,
        "register_events",
        AsyncMock(
            return_value={"status": "success", "queue_id": "q", "last_event_id": 0}
        ),
    )
    client = MagicMock()
    client.get_events.side_effect = [
        {"result": "error", "code": "RATE_LIMIT_HIT", "msg": "slow", "retry-after": 7},
        {"result": "success", "events": [{"id": 1, "type": "message"}]},
    ]
    monkeypatch.setattr(event_management, "get_client", lambda: client)
    monkeypatch.setattr(event_management, "deregister_events", AsyncMock())
    sleep = AsyncMock()
    monkeypatch.setattr(event_management.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        event_management,
        "time",
        MagicMock(monotonic=MagicMock(side_effect=[0, 0, 1, 30, 31])),
    )
    result = await event_management.listen_events(["message"], duration=30)
    assert sleep.await_args_list[0].args[0] == 7
    assert result["polling_errors"][0]["retry_after_seconds"] == 7
    assert result["event_count"] == 1
