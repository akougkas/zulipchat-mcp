"""Covers simple-param path and highlights in advanced_search."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
@patch("zulipchat_mcp.tools.search_v25._generate_cache_key", return_value="simple")
async def test_advanced_search_simple_params_highlights(
    _mock_key, mock_managers
) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client:
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {
                "result": "success",
                "messages": [
                    {
                        "id": 1,
                        "content": "Deploy guide for docker",
                        "sender_full_name": "Alice",
                        "display_recipient": "dev",
                        "subject": "ops",
                    }
                ],
            }

    async def execute(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=execute)

    out = await advanced_search(
        query="docker",
        search_type=["messages"],
        stream="dev",
        highlight=True,
        limit=5,
        use_cache=False,
    )
    assert out["status"] == "success"
    msgs = out["results"]["messages"]["messages"]
    assert (
        msgs
        and "highlights" in msgs[0]
        and any("docker" in h for h in msgs[0]["highlights"])
    )
