"""Canonical API methods/paths and actual registered tool error fidelity."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP

from zulipchat_mcp.core.client import ZulipClientWrapper
from zulipchat_mcp.core.tool_contract import ToolContractMiddleware
from zulipchat_mcp.tools import messaging, stream_management


@pytest.fixture
def wrapper():
    config = MagicMock()
    config.validate_config.return_value = True
    config.get_zulip_client_config.return_value = {
        "email": "owner@example.com",
        "api_key": "fake",
        "site": "https://example.com",
    }
    client = ZulipClientWrapper(config)
    endpoint = MagicMock(return_value={"result": "success"})
    client._client = SimpleNamespace(call_endpoint=endpoint)
    return client


def test_numeric_stream_lookup_is_get_and_preserves_the_requested_id(wrapper):
    result = wrapper.get_stream_id(42)
    wrapper.client.call_endpoint.assert_called_once_with(
        "streams/42", method="GET", request={}
    )
    assert result["stream_id"] == 42


@pytest.mark.parametrize(
    "method,operation", [("mute_topic", "add"), ("unmute_topic", "remove")]
)
def test_topic_mute_fallback_uses_documented_subscription_path(
    wrapper, method, operation
):
    getattr(wrapper, method)(42, "Topic")
    wrapper.client.call_endpoint.assert_called_once_with(
        "users/me/subscriptions/muted_topics",
        method="PATCH",
        request={"op": operation, "stream_id": 42, "topic": "Topic"},
    )


def test_subscription_property_fallback_uses_post(wrapper):
    properties = [{"stream_id": 42, "property": "color", "value": "#aabbcc"}]
    wrapper.update_subscription_settings(properties)
    wrapper.client.call_endpoint.assert_called_once_with(
        "users/me/subscriptions/properties",
        method="POST",
        request={"subscription_data": properties},
    )


def test_message_reads_cache_rendering_separately_and_mutations_expire_it(wrapper):
    wrapper.client.call_endpoint.return_value = {
        "result": "success",
        "message": {"id": 1, "content": "sample"},
    }
    assert wrapper.get_message(1)["_cache"]["hit"] is False
    assert wrapper.get_message(1)["_cache"]["hit"] is True
    assert wrapper.get_message(1, apply_markdown=False)["_cache"]["hit"] is False
    assert wrapper.client.call_endpoint.call_count == 2
    wrapper.client.update_message = MagicMock(return_value={"result": "success"})
    wrapper.edit_message(1, content="Changed")
    assert wrapper.get_message(1)["_cache"]["hit"] is False
    assert wrapper.client.call_endpoint.call_count == 3
    assert wrapper.get_message(1, fresh=True)["_cache"]["max_age_seconds"] == 0
    assert wrapper.client.call_endpoint.call_count == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_registered_send_retains_rate_limit_code_and_never_retries(
    mode, monkeypatch
):
    upstream = MagicMock()
    upstream.send_message.return_value = {
        "result": "error",
        "code": "RATE_LIMIT_HIT",
        "msg": "Wait",
        "retry-after": 29,
    }
    monkeypatch.setattr(messaging, "get_client", lambda: upstream)
    server = FastMCP("api-errors")
    server.tool(messaging.send_message)
    server.add_middleware(ToolContractMiddleware())
    async with Client(server, mode=mode) as client:
        result = await client.call_tool(
            "send_message",
            {"type": "stream", "to": "Demo", "topic": "Test", "content": "Hello"},
            raise_on_error=False,
        )
        assert result.is_error
        assert result.structured_content["error_code"] == "RATE_LIMIT_HIT"
        assert result.structured_content["retry_after_seconds"] == 29
        assert result.structured_content["retryable"] is True
    assert upstream.send_message.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_requested_details_are_partial_when_upstream_fails(mode, monkeypatch):
    upstream = MagicMock()
    upstream.get_streams.return_value = {
        "result": "success",
        "streams": [{"stream_id": 42, "name": "Demo"}],
    }
    upstream.get_stream_topics.return_value = {
        "result": "error",
        "code": "RATE_LIMIT_HIT",
        "msg": "Wait",
        "retry-after": 5,
    }
    monkeypatch.setattr(stream_management, "get_client", lambda: upstream)
    server = FastMCP("stream-detail-outcome")
    server.tool(stream_management.get_stream_info)
    server.add_middleware(ToolContractMiddleware())
    async with Client(server, mode=mode) as client:
        result = (
            await client.call_tool(
                "get_stream_info", {"stream_id": 42, "include_topics": True}
            )
        ).data
        assert result["status"] == "partial"
        assert result["name"] == "Demo"
        assert result["errors"][0]["component"] == "topics"
        assert result["errors"][0]["retry_after_seconds"] == 5
