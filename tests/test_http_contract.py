"""Exercise real HTTP auth, protocol headers and remote tool boundaries."""

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.testclient import TestClient

from zulipchat_mcp.tools import files, system


@pytest.fixture
def http_server(monkeypatch):
    mcp = FastMCP(
        "http-contract",
        tasks=False,
        auth=StaticTokenVerifier(
            tokens={"test-token": {"client_id": "test", "scopes": []}}
        ),
    )
    mcp.tool(files.upload_file)
    mcp.tool(files.manage_files)
    mcp.tool(system.switch_identity)
    monkeypatch.setattr(
        files, "get_client", lambda: MagicMock(base_url="https://zulip.example")
    )
    app = mcp.http_app(
        json_response=True, host_origin_protection=True, allowed_hosts=["testserver"]
    )
    with TestClient(app) as client:
        yield client


def rpc(client, method="server/discover", params=None, headers=None):
    return client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": {
                **(params or {}),
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "test",
                        "version": "1",
                    },
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer test-token",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": method,
            **(headers or {}),
        },
    )


def test_http_auth_host_origin_and_modern_discovery(http_server):
    assert rpc(http_server, headers={"Authorization": ""}).status_code == 401
    assert (
        rpc(http_server, headers={"Authorization": "Bearer wrong"}).status_code == 401
    )
    assert rpc(http_server, headers={"Host": "attacker.example"}).status_code == 421
    assert (
        rpc(http_server, headers={"Origin": "https://attacker.example"}).status_code
        == 403
    )
    response = rpc(http_server)
    assert response.status_code == 200
    assert "result" in response.json()


def test_http_rejects_mismatched_method_header(http_server):
    response = rpc(http_server, headers={"Mcp-Method": "tools/call"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


def test_modern_tool_list_has_cache_metadata(http_server):
    response = rpc(http_server, "tools/list")
    assert response.status_code == 200
    result = response.json()["result"]
    assert "ttlMs" in result
    assert result["cacheScope"] in {"public", "private"}


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("upload_file", {"file_path": "/etc/passwd"}),
        (
            "manage_files",
            {"operation": "download", "file_id": "1/file", "download_path": "/tmp/out"},
        ),
    ],
)
def test_http_tools_reject_server_local_file_paths(http_server, tool, arguments):
    response = rpc(
        http_server,
        "tools/call",
        {"name": tool, "arguments": arguments},
        {"Mcp-Name": tool},
    )
    assert response.status_code == 200
    result = response.json()["result"]["structuredContent"]
    assert result["status"] == "error"
    assert "Local file paths are disabled over HTTP" in result["error"]


def test_http_cannot_change_identity_for_other_callers(http_server):
    response = rpc(
        http_server,
        "tools/call",
        {"name": "switch_identity", "arguments": {"identity": "bot"}},
        {"Mcp-Name": "switch_identity"},
    )
    assert response.status_code == 200
    result = response.json()["result"]["structuredContent"]
    assert result["status"] == "error"
    assert "only available over stdio" in result["error"]
