"""Contract tests for search_v25.advanced_search output shapes.

Validates that the transformation layer returns objects conforming to a
stable schema for the `messages` and `topics` result types. We don't
assert specific values beyond structure and required keys.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from jsonschema import validate


MESSAGES_SCHEMA = {
    "type": "object",
    "required": ["status", "query", "search_types", "results", "metadata"],
    "properties": {
        "status": {"enum": ["success"]},
        "query": {"type": "string"},
        "search_types": {"type": "array", "items": {"type": "string"}},
        "aggregations": {"type": "object"},
        "metadata": {
            "type": "object",
            "required": ["total_results", "search_time", "sort_by", "limit", "from_cache"],
            "properties": {
                "total_results": {"type": "number"},
                "search_time": {"type": "string"},
                "sort_by": {"type": "string"},
                "limit": {"type": "number"},
                "from_cache": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
        "results": {
            "type": "object",
            "required": ["messages"],
            "properties": {
                "messages": {
                    "type": "object",
                    "required": ["count", "messages", "has_more"],
                    "properties": {
                        "count": {"type": "number"},
                        "messages": {"type": "array"},
                        "has_more": {"type": "boolean"},
                    },
                }
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


TOPICS_SCHEMA = {
    "type": "object",
    "required": ["status", "query", "search_types", "results", "metadata"],
    "properties": {
        "status": {"enum": ["success"]},
        "query": {"type": "string"},
        "search_types": {"type": "array", "items": {"type": "string"}},
        "results": {
            "type": "object",
            "required": ["topics"],
            "properties": {
                "topics": {
                    "type": "object",
                    "required": ["count", "topics", "has_more"],
                    "properties": {
                        "count": {"type": "number"},
                        "topics": {"type": "array"},
                        "has_more": {"type": "boolean"},
                    },
                }
            },
            "additionalProperties": True,
        },
        "metadata": {"type": "object"},
    },
    "additionalProperties": True,
}


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_advanced_search_messages_contract(mock_managers, make_msg, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    msgs = [
        make_msg(1, content="deploy"),
        make_msg(2, content="deploy now"),
        make_msg(3, content="blue-green deploy"),
    ]

    class Client(fake_client_class):
        def get_messages_raw(self, **kwargs):  # type: ignore[no-redef]
            return {"result": "success", "messages": msgs}

    async def exec_(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    out = await advanced_search(query="deploy", search_type=["messages"], limit=5, use_cache=False)
    validate(out, MESSAGES_SCHEMA)


@pytest.mark.asyncio
@patch("zulipchat_mcp.tools.search_v25._get_managers")
async def test_advanced_search_topics_contract(mock_managers, fake_client_class) -> None:
    from zulipchat_mcp.tools.search_v25 import advanced_search

    mock_config, mock_identity, mock_validator = Mock(), Mock(), Mock()
    mock_managers.return_value = (mock_config, mock_identity, mock_validator)
    mock_validator.suggest_mode.return_value = Mock()
    mock_validator.validate_tool_params.side_effect = lambda name, p, mode: p

    class Client(fake_client_class):
        def get_streams(self, *a, **k):  # type: ignore[no-redef]
            return {"result": "success", "streams": [{"name": "g", "stream_id": 1}]}
        def get_stream_topics(self, stream_id):  # type: ignore[no-redef]
            return {"result": "success", "topics": [{"name": "deploy"}, {"name": "deployments"}]}

    async def exec_(tool, params, func, identity=None):
        return await func(Client(), params)

    mock_identity.execute_with_identity = AsyncMock(side_effect=exec_)

    out = await advanced_search(query="deploy", search_type=["topics"], limit=10, use_cache=False)
    validate(out, TOPICS_SCHEMA)

