"""Extended register/get events parameter coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from zulipchat_mcp.core.validation import NarrowFilter


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.events_v25._get_managers")
async def test_register_events_with_narrow_and_capabilities(mock_managers) -> None:
    from zulipchat_mcp.tools.events_v25 import register_events

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.return_value = {}

    nf = NarrowFilter(operator="stream", operand="general")

    async def execute(tool, params, func, identity=None):
        class Client:
            def register(self, **kwargs):  # type: ignore[no-redef]
                assert "narrow" in kwargs
                assert kwargs.get("client_capabilities") == {"supports": ["typing"]}
                return {"result": "success", "queue_id": "qX", "last_event_id": 0}
        return await func(Client(), {"event_types": ["message"], "narrow": [nf], "client_capabilities": {"supports": ["typing"]}})

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    res = await register_events(event_types=["message"], narrow=[nf], client_capabilities={"supports": ["typing"]})
    assert res["status"] == "success"

