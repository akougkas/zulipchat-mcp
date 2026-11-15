"""Boundary regressions from the full source audit."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zulipchat_mcp.tools import event_management


def test_setup_uvx_command_matches_generated_arguments(monkeypatch):
    from zulipchat_mcp import __version__, setup_wizard

    monkeypatch.setattr(setup_wizard.shutil, "which", lambda command: f"/bin/{command}")
    config = setup_wizard.generate_mcp_config(
        {"path": "/tmp/user.zuliprc"}, use_uvx=True
    )
    assert config["command"] == "/bin/uvx"
    assert config["args"][0] == f"zulipchat-mcp@{__version__}"


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
