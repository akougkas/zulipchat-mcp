"""Exercise actual MCP discovery and execution, with fake-only dependencies."""

from unittest.mock import AsyncMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.tools.base import ToolResult

from zulipchat_mcp.core.tool_contract import ToolContractMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_read_only_policy_filters_catalog_and_blocks_direct_calls(mode):
    server = FastMCP("policy-contract")
    invoked = AsyncMock(return_value={"status": "success"})

    @server.tool
    async def send_message() -> dict:
        return await invoked()

    @server.tool
    def server_info() -> dict:
        return {"status": "success", "version": "test"}

    @server.tool
    def resolve_user(name: str) -> dict:
        return {"status": "success", "name": name}

    server.add_middleware(ToolContractMiddleware(read_only=True))
    async with Client(server, mode=mode) as client:
        assert {tool.name for tool in await client.list_tools()} == {
            "server_info",
            "resolve_user",
        }
        info = (await client.call_tool("server_info")).data["capabilities"]
        assert info["tool_profile"] == "read-only"
        assert info["enabled_tools"] == ["resolve_user", "server_info"]
        assert info["enabled_tool_count"] == 2
        assert info["identity_switching"] is False
        result = await client.call_tool("send_message", {}, raise_on_error=False)
        assert result.is_error is True
        assert result.structured_content["error_code"] == "POLICY_DENIED"
        assert result.structured_content["retryable"] is False
        assert (await client.call_tool("resolve_user", {"name": "Jaime"})).data[
            "name"
        ] == "Jaime"
    invoked.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
@pytest.mark.parametrize(
    "data,expected_error",
    [
        ({"status": "error", "error": "Bad narrow", "code": "BAD_NARROW"}, True),
        ({"status": "partial", "delivered": True, "message_id": 42}, False),
        ({"status": "timeout", "request_id": "same-request"}, False),
        ({"status": "success", "llm_unavailable": True}, False),
    ],
)
async def test_wire_error_truth_preserves_details_and_nonerror_outcomes(
    mode, data, expected_error
):
    server = FastMCP("outcome-contract")

    @server.tool
    def operation() -> dict:
        return data

    server.add_middleware(ToolContractMiddleware())
    async with Client(server, mode=mode) as client:
        result = await client.call_tool("operation", {}, raise_on_error=False)
        assert result.is_error is expected_error
        assert result.structured_content == data


@pytest.mark.asyncio
async def test_preexisting_error_meta_and_content_are_preserved():
    server = FastMCP("existing-error")

    @server.tool
    def operation() -> ToolResult:
        return ToolResult(
            content="original diagnostic",
            structured_content={"status": "error", "error": "Denied"},
            meta={"trace": "synthetic"},
            is_error=True,
        )

    server.add_middleware(ToolContractMiddleware())
    async with Client(server) as client:
        result = await client.call_tool("operation", {}, raise_on_error=False)
        assert result.is_error is True
        assert result.content[0].text == "original diagnostic"


@pytest.mark.asyncio
async def test_capabilities_apply_without_an_initial_list_and_over_http():
    server = FastMCP("capability-contract")

    @server.tool
    def server_info() -> dict:
        return {"status": "success"}

    server.add_middleware(ToolContractMiddleware(transport="http"))
    async with Client(server) as client:
        info = (await client.call_tool("server_info")).data["capabilities"]
        assert info["enabled_tools"] == ["server_info"]
        assert info["enabled_tool_count"] == 1
        assert info["transport"] == "http"
        assert info["identity_switching"] is False
