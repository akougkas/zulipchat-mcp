"""Messaging v2.5 bulk operations and edge cases to boost coverage."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_bulk_add_remove_flag_success_and_conflict_error(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import bulk_operations

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def update_message_flags(self, messages, op, flag):  # type: ignore[no-redef]
            assert messages == [1, 2]
            assert flag in ("read", "starred")
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await bulk_operations(operation="add_flag", message_ids=[1, 2], flag="starred")
    assert ok["status"] == "success"
    assert ok["affected_count"] == 2

    # conflict: both narrow and message_ids
    err = await bulk_operations(operation="remove_flag", narrow=[{"operator": "stream", "operand": "general"}], message_ids=[1], flag="starred")
    assert err["status"] == "error"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_bulk_add_remove_reaction_and_delete_success(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import bulk_operations

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def add_reaction(self, message_id, emoji_name):  # type: ignore[no-redef]
            return {"result": "success"}
        def remove_reaction(self, message_id, emoji_name):  # type: ignore[no-redef]
            return {"result": "success"}
        def delete_message(self, message_id):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok1 = await bulk_operations(operation="add_reaction", message_ids=[10, 11], emoji_name="thumbs_up")
    assert ok1["status"].startswith("success")

    ok2 = await bulk_operations(operation="remove_reaction", message_ids=[10], emoji_name="thumbs_up")
    assert ok2["status"].startswith("success")

    ok3 = await bulk_operations(operation="delete_messages", message_ids=[10, 11])
    assert ok3["status"].startswith("success")


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_bulk_narrow_paths_mark_read_flag_reaction_delete(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import bulk_operations

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": [{"id": 1}, {"id": 2}]}
        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages({"anchor": anchor, "num_before": num_before, "num_after": num_after, "narrow": narrow or []})
        def update_message_flags(self, messages, op, flag):  # type: ignore[no-redef]
            return {"result": "success"}
        def add_reaction(self, message_id, emoji_name):  # type: ignore[no-redef]
            # simulate one success and one failure
            return {"result": "success"} if message_id == 1 else {"result": "error", "msg": "nope"}
        def delete_message(self, message_id):  # type: ignore[no-redef]
            return {"result": "success" if message_id == 1 else "error"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok_read = await bulk_operations(operation="mark_read", narrow=[{"operator": "stream", "operand": "general"}])
    assert ok_read["status"] == "success"

    ok_flag = await bulk_operations(operation="add_flag", narrow=[{"operator": "stream", "operand": "general"}], flag="starred")
    assert ok_flag["status"] == "success"

    ok_react = await bulk_operations(operation="add_reaction", narrow=[{"operator": "stream", "operand": "general"}], emoji_name="thumbs_up")
    assert ok_react["status"] in ("success", "partial_success")

    ok_del = await bulk_operations(operation="delete_messages", narrow=[{"operator": "stream", "operand": "general"}])
    assert ok_del["status"] in ("success", "partial_success")


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_bulk_remove_flag_error_branch(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import bulk_operations

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def update_message_flags(self, messages, op, flag):  # type: ignore[no-redef]
            return {"result": "error", "msg": "no"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await bulk_operations(operation="remove_flag", message_ids=[1], flag="starred")
    assert res["status"] == "error"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_bulk_add_reaction_no_messages_narrow(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import bulk_operations

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    class Client:
        def get_messages(self, request):  # type: ignore[no-redef]
            return {"result": "success", "messages": []}
        def get_messages_raw(self, anchor="newest", num_before=100, num_after=0, narrow=None, include_anchor=True, client_gravatar=True, apply_markdown=True):  # type: ignore[no-redef]
            return self.get_messages({"anchor": anchor, "num_before": num_before, "num_after": num_after, "narrow": narrow or []})

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)
    res = await bulk_operations(operation="add_reaction", narrow=[{"operator": "stream", "operand": "general"}], emoji_name="thumbs_up")
    assert res["status"] == "success"
    assert res["affected_count"] == 0


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_cross_post_message_error_branches(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import cross_post_message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    # invalid id
    res_bad = await cross_post_message(0, ["dev"])
    assert res_bad["status"] == "error"

    # no targets
    res_none = await cross_post_message(1, [])
    assert res_none["status"] == "error"

    # source not found
    async def exec_nf(tool, params, func, identity=None):
        class Client:
            def get_message(self, message_id):  # type: ignore[no-redef]
                return {"result": "error", "msg": "not found"}
        return await func(Client(), params)
    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_nf)
    res_nf = await cross_post_message(1, ["dev"])
    assert res_nf["status"] == "error"

    # failed posts
    async def exec_fail(tool, params, func, identity=None):
        class Client:
            def get_message(self, message_id):  # type: ignore[no-redef]
                return {"result": "success", "message": {"content": "hi", "subject": "t", "display_recipient": "general"}}
            def send_message(self, payload):  # type: ignore[no-redef]
                return {"result": "error", "msg": "denied"}
        return await func(Client(), params)
    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_fail)
    res_fail = await cross_post_message(1, ["dev"])
    assert res_fail["status"] == "error"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_message_send_private_and_schedule_error_and_truncate(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import message

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    long_content = "x" * 51000

    class Client:
        def send_message(self, mtype, recipients, content, topic):  # type: ignore[no-redef]
            assert mtype == "private"
            assert recipients == ["user@example.com"]
            # content should be truncated
            assert content.endswith("[Content truncated]")
            return {"result": "success", "id": 5}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await message("send", "private", "user@example.com", long_content)
    assert ok["status"] == "success"

    # schedule path without schedule_at -> error
    err = await message("schedule", "stream", ["general"], "Hi", topic="t")
    assert err["status"] == "error"


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_search_messages_guards_and_history_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import search_messages, message_history

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    # history invalid id
    res_bad = await message_history(0)
    assert res_bad["status"] == "error"

    # history message not found
    async def exec_hist(tool, params, func, identity=None):
        class Client:
            def get_message(self, message_id):  # type: ignore[no-redef]
                return {"result": "error", "msg": "not found"}
        return await func(Client(), params)
    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_hist)
    res_nf = await message_history(1)
    assert res_nf["status"] == "error"

    # search guards
    res1 = await search_messages(anchor=-1)
    assert res1["status"] == "error"
    res2 = await search_messages(num_before=-1)
    assert res2["status"] == "error"
    res3 = await search_messages(num_before=4000, num_after=2000)
    assert res3["status"] == "error"
