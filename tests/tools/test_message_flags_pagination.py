"""Bulk flag contracts exercised through the registered MCP tool."""

from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp_tasks import TasksExtension

from zulipchat_mcp.tools import mark_messaging, register_core_tools


@pytest.fixture
def flag_backend(monkeypatch):
    """Simulate bounded pages with read messages before the first unread."""
    client = MagicMock()
    client.get_streams.return_value = {
        "result": "success",
        "streams": [{"stream_id": 7, "name": "engineering"}],
    }
    messages = [
        {"id": i, "flags": {"read", "starred"} if i < 3 else set()} for i in range(1, 7)
    ]
    requests = []

    def update(endpoint, *, method, request):
        assert endpoint == "messages/flags/narrow"
        assert method == "POST"
        requests.append(request)
        anchor = request["anchor"]
        if anchor == "oldest":
            start = 1
        elif anchor == "first_unread":
            start = next((m["id"] for m in messages if "read" not in m["flags"]), 7)
        else:
            start = anchor + (not request["include_anchor"])
        page = [m for m in messages if m["id"] >= start][:2]
        updated = 0
        for message in page:
            flags = message["flags"]
            if request["op"] == "add":
                updated += request["flag"] not in flags
                flags.add(request["flag"])
            else:
                updated += request["flag"] in flags
                flags.discard(request["flag"])
        return {
            "result": "success",
            "processed_count": len(page),
            "updated_count": updated,
            "first_processed_id": page[0]["id"] if page else None,
            "last_processed_id": page[-1]["id"] if page else None,
            "found_newest": not page or page[-1]["id"] == 6,
        }

    client.client.call_endpoint.side_effect = update
    monkeypatch.setattr(mark_messaging, "get_client", lambda: client)
    return client, messages, requests


async def call_registered(arguments):
    server = FastMCP("flag-pagination", tasks=False)
    server.add_extension(TasksExtension())
    register_core_tools(server)
    async with Client(server, mode="legacy") as client:
        return (await client.call_tool("manage_message_flags", arguments)).data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag,action",
    [
        ("read", "add"),
        ("read", "remove"),
        ("starred", "add"),
        ("starred", "remove"),
    ],
)
@pytest.mark.parametrize(
    "scope,extra,expected_narrow",
    [
        ("all", {}, []),
        (
            "stream",
            {"stream_id": 7},
            [{"operator": "stream", "operand": "engineering"}],
        ),
        (
            "topic",
            {"stream_id": 7, "topic_name": "deploy"},
            [
                {"operator": "stream", "operand": "engineering"},
                {"operator": "topic", "operand": "deploy"},
            ],
        ),
        (
            "narrow",
            {"narrow": [{"operator": "is", "operand": "private"}]},
            [{"operator": "is", "operand": "private"}],
        ),
    ],
)
async def test_registered_tool_updates_entire_scope(
    flag_backend, flag, action, scope, extra, expected_narrow
):
    _, messages, requests = flag_backend
    result = await call_registered(
        {"flag": flag, "action": action, "scope": scope, **extra}
    )
    assert result["status"] == "success"
    assert result["complete"] is True
    assert all((flag in m["flags"]) == (action == "add") for m in messages)
    assert result["updated_count"] == (4 if action == "add" else 2)
    starts_at_unread = flag == "read" and action == "add"
    assert result["processed_count"] == (4 if starts_at_unread else 6)
    assert result["pages_completed"] == (2 if starts_at_unread else 3)
    assert requests[0]["anchor"] == ("first_unread" if starts_at_unread else "oldest")
    assert all(r["narrow"] == expected_narrow for r in requests)
    assert all(not r["include_anchor"] for r in requests[1:])
    assert all(r["num_before"] == 0 for r in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("successful_pages", [0, 1])
async def test_registered_tool_reports_confirmed_progress_on_failure(
    flag_backend, successful_pages
):
    backend, _, requests = flag_backend
    update = backend.client.call_endpoint.side_effect

    def fail(endpoint, *, method, request):
        if len(requests) == successful_pages:
            return {"result": "error", "msg": "Rate limited"}
        return update(endpoint, method=method, request=request)

    backend.client.call_endpoint.side_effect = fail
    result = await call_registered({"flag": "read", "action": "add", "scope": "all"})
    assert result["status"] == ("partial" if successful_pages else "error")
    assert result["complete"] is False
    assert result["processed_count"] == result["updated_count"] == 2 * successful_pages
    assert result["pages_completed"] == successful_pages
    assert result["error"] == "Rate limited"


@pytest.mark.asyncio
async def test_registered_tool_stops_nonadvancing_cursor(flag_backend):
    backend, _, _ = flag_backend
    backend.client.call_endpoint.return_value = {
        "result": "success",
        "processed_count": 2,
        "updated_count": 1,
        "last_processed_id": 2,
        "found_newest": False,
    }
    backend.client.call_endpoint.side_effect = None
    result = await call_registered({"flag": "starred", "action": "add", "scope": "all"})
    assert result["status"] == "partial"
    assert result["complete"] is False
    assert "no progress" in result["error"]
    assert backend.client.call_endpoint.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "helper,flag,action",
    [
        ("mark_all_as_read", "read", "add"),
        ("mark_messages_unread", "read", "remove"),
        ("star_messages", "starred", "add"),
        ("unstar_messages", "starred", "remove"),
    ],
)
async def test_compatibility_helpers_share_complete_operation(
    flag_backend, helper, flag, action
):
    _, messages, requests = flag_backend
    args = {} if helper == "mark_all_as_read" else {"topic_name": "deploy"}
    result = await getattr(mark_messaging, helper)(**args)
    assert result["complete"] is True
    assert len(requests) > 1
    assert all((flag in m["flags"]) == (action == "add") for m in messages)
