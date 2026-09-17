"""Boundary regressions from the full source audit."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp import claude_hooks
from zulipchat_mcp.config import ZulipConfig
from zulipchat_mcp.core.validation import ParameterValidator
from zulipchat_mcp.services.scheduler import MessageScheduler, ScheduledMessage
from zulipchat_mcp.tools import ai_analytics, event_management, search


@pytest.mark.asyncio
async def test_temporary_identities_are_isolated_across_tasks():
    from zulipchat_mcp.config import ConfigManager
    from zulipchat_mcp.core.identity import IdentityManager, IdentityType

    config = ConfigManager()
    config.config = ZulipConfig(
        "user@example.com",
        "user-key",
        "https://example.com",
        bot_email="bot@example.com",
        bot_api_key="bot-key",
    )
    manager = IdentityManager(config)
    bot_entered, user_entered = asyncio.Event(), asyncio.Event()

    async def bot():
        async with manager.use_identity(IdentityType.BOT):
            bot_entered.set()
            await user_entered.wait()
            assert manager.get_current_identity().type == IdentityType.BOT

    async def user():
        await bot_entered.wait()
        async with manager.use_identity(IdentityType.USER):
            user_entered.set()
            await asyncio.sleep(0)
            assert manager.get_current_identity().type == IdentityType.USER

    await asyncio.gather(bot(), user())
    assert manager.get_current_identity().type == IdentityType.USER


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


@pytest.mark.asyncio
async def test_narrow_builder_does_not_substitute_text_search_for_time_filters():
    result = await search.construct_narrow(stream="private", after_time="2026-09-01")
    assert result["status"] == "error"
    assert "search_messages" in result["error"]
    assert "narrow" not in result


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
async def test_scheduler_uses_selected_realm_and_rejects_partial_recipients(
    monkeypatch,
):
    monkeypatch.setenv("ZULIP_SITE", "https://ambient.example.com")
    scheduler = MessageScheduler(
        ZulipConfig("owner@selected.com", "key", "https://selected.example.com")
    )
    assert scheduler.base_url == "https://selected.example.com/api/v1"
    assert scheduler._lookup_client.config_manager.config is scheduler.config
    scheduler._lookup_client.get_users = MagicMock(
        return_value={
            "result": "success",
            "members": [{"email": "found@example.com", "user_id": 1}],
        }
    )
    scheduler.client = AsyncMock()
    message = ScheduledMessage(
        content="private",
        message_type="private",
        recipients=["found@example.com", "missing@example.com"],
        scheduled_time=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="nothing was scheduled"):
        await scheduler.schedule_message(message)
    scheduler.client.post.assert_not_called()
    await scheduler.close()
    assert scheduler.client is None


@pytest.mark.asyncio
async def test_scheduler_bulk_retains_failed_input_positions():
    scheduler = MessageScheduler(
        ZulipConfig("owner@example.com", "key", "https://example.com")
    )
    scheduler.schedule_message = AsyncMock(
        side_effect=[
            {"result": "success", "scheduled_message_id": 1},
            RuntimeError("rejected"),
            {"result": "success", "scheduled_message_id": 3},
        ]
    )
    result = await scheduler.bulk_schedule([MagicMock(), MagicMock(), MagicMock()])
    assert len(result) == 3
    assert result[1] == {"status": "error", "error": "rejected"}
    assert result[2]["scheduled_message_id"] == 3


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


@pytest.mark.asyncio
async def test_team_analytics_does_not_report_api_failure_as_no_activity(monkeypatch):
    monkeypatch.setattr(ai_analytics, "get_client", MagicMock())
    monkeypatch.setattr(
        search,
        "search_messages",
        AsyncMock(return_value={"status": "error", "error": "permission denied"}),
    )
    generate = AsyncMock()
    monkeypatch.setattr(ai_analytics, "generate", generate)
    result = await ai_analytics.analyze_team_activity_with_llm(["private"], "progress")
    assert result["status"] == "error"
    assert "permission denied" in result["error"]
    generate.assert_not_called()


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


def test_validator_list_choices_and_defaults_are_isolated():
    validator = ParameterValidator()
    first = validator.validate_tool_params(
        "search.advanced_search",
        {"query": "test", "search_type": ["messages", "users"]},
    )
    first["narrow"].append({"operator": "stream", "operand": "private"})
    second = validator.validate_tool_params("search.advanced_search", {"query": "test"})
    assert second["narrow"] == []
