"""Tests for add_reaction and remove_reaction in messaging_v25."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_add_reaction_success_and_remove_invalid(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import add_reaction, remove_reaction

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    class Client:
        def add_reaction(self, message_id, emoji_name):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await add_reaction(1, "thumbs_up")
    assert ok["status"] == "success"

    bad = await remove_reaction(1, "bad-emoji")
    assert bad["status"] == "error" and "emoji" in bad["error"].lower()


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.messaging_v25._get_managers")
async def test_remove_reaction_success(mock_managers) -> None:
    from zulipchat_mcp.tools.messaging_v25 import remove_reaction

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)

    class Client:
        def remove_reaction(self, message_id, emoji_name):  # type: ignore[no-redef]
            return {"result": "success"}

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    ok = await remove_reaction(5, "thumbs_up")
    assert ok["status"] == "success" and ok["message_id"] == 5
