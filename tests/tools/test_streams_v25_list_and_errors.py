"""List and error branches for streams_v25.manage_streams and get_stream_info."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.streams_v25._get_managers")
async def test_manage_streams_list_and_update_errors(mock_managers) -> None:
    from zulipchat_mcp.tools.streams_v25 import get_stream_info, manage_streams

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_streams(self, **kwargs):  # type: ignore[no-redef]
            return {
                "result": "success",
                "streams": [{"name": "general", "stream_id": 1}],
            }

        # Provide shape used by manage_streams(list) path (dict param signature)
        def get_streams_raw(self, request):  # not used; keep for completeness
            return self.get_streams(**request)

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    # list with include_all_active True and include_public False
    lst = await manage_streams("list", include_public=False, include_all_active=True)
    assert lst["status"] == "success" and "streams" in lst

    # update error branches
    err1 = await manage_streams("update")
    assert err1["status"] == "error" and "required for update" in err1["error"]
    err2 = await manage_streams("update", stream_ids=[1])
    assert err2["status"] == "error" and "properties" in err2["error"]

    # subscribe error (no ids/names)
    # Exercise get_stream_info error for missing identifiers
    info_err = await get_stream_info()
    assert (
        info_err["status"] == "error"
        and "Either stream_id or stream_name" in info_err["error"]
    )
