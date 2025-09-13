"""Structured error checks for required parameters in manage_topics."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_topics_required_fields_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import manage_topics

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    async def exec_(tool, params, func, identity=None):
        # no client interaction needed; early validation path
        class EmptyClient:  # type: ignore[too-many-ancestors]
            pass

        return await func(EmptyClient(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    # delete without source_topic
    err_del = await manage_topics(stream_id=1, operation="delete")
    assert err_del["status"] == "error" and err_del["operation"] == "delete"
    assert isinstance(err_del.get("error", ""), str) and err_del["error"]

    # mark_read without source_topic
    err_mark = await manage_topics(stream_id=1, operation="mark_read")
    assert err_mark["status"] == "error" and err_mark["operation"] == "mark_read"
    assert isinstance(err_mark.get("error", ""), str) and err_mark["error"]
