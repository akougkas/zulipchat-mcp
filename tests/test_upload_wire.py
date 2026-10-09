"""Binary upload contracts through authenticated HTTP JSON-RPC."""

import base64
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.testclient import TestClient

from zulipchat_mcp.tools import files


@pytest.fixture
def upload_http(monkeypatch):
    zulip = MagicMock()
    zulip.upload_file.return_value = {
        "result": "success",
        "uri": "/user_uploads/1/upload.bin",
    }
    monkeypatch.setattr(files, "get_client", lambda: zulip)
    mcp = FastMCP(
        "upload-contract",
        tasks=False,
        auth=StaticTokenVerifier(
            tokens={"test-token": {"client_id": "test", "scopes": []}}
        ),
    )
    files.register_files_tools(mcp)
    app = mcp.http_app(
        json_response=True, host_origin_protection=True, allowed_hosts=["testserver"]
    )
    with TestClient(app) as http:
        yield http, zulip


def upload(http, **arguments):
    response = http.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "upload_file",
                "arguments": arguments,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "upload-test",
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
            "Mcp-Method": "tools/call",
            "Mcp-Name": "upload_file",
        },
    )
    assert response.status_code == 200
    return response.json()["result"]["structuredContent"]


@pytest.mark.parametrize("content", [b"\x00\xff\x80", b"", b"plain text"])
def test_binary_base64_upload_preserves_bytes(upload_http, content):
    http, zulip = upload_http
    result = upload(
        http,
        file_content_base64=base64.b64encode(content).decode("ascii"),
        filename="binary.dat",
    )
    assert result["status"] == "success"
    assert result["file_size"] == len(content)
    zulip.upload_file.assert_called_once_with(content, "binary.dat")


@pytest.mark.parametrize("content", ["text \u2603", "", "AP+A"])
def test_existing_text_argument_stays_utf8(upload_http, content):
    http, zulip = upload_http
    result = upload(http, file_content=content, filename="text.txt")
    assert result["status"] == "success"
    zulip.upload_file.assert_called_once_with(content.encode("utf-8"), "text.txt")


@pytest.mark.parametrize(
    "encoded",
    ["!@#$", "aA", "aA==\n", "a A==", "\u2603", "-_8=", "aB==", "aA===", "===="],
)
def test_invalid_base64_does_not_upload(upload_http, encoded):
    http, zulip = upload_http
    result = upload(http, file_content_base64=encoded)
    assert result["status"] == "error"
    assert "base64" in result["error"]
    zulip.upload_file.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"file_content_base64": "", "file_content": ""},
        {"file_content_base64": "", "file_path": "/not-read"},
        {"file_content": "text", "file_path": "/not-read"},
    ],
)
def test_upload_requires_one_unambiguous_source(upload_http, arguments):
    http, zulip = upload_http
    result = upload(http, **arguments)
    assert result["status"] == "error"
    assert "Exactly one" in result["error"]
    zulip.upload_file.assert_not_called()


def test_encoded_size_is_bounded_before_decode(upload_http, monkeypatch):
    http, zulip = upload_http
    monkeypatch.setattr(files, "MAX_FILE_SIZE", 4)
    with patch.object(files, "b64decode") as decode:
        result = upload(http, file_content_base64="A" * 12)
    assert result["status"] == "error"
    assert "too large" in result["error"]
    decode.assert_not_called()
    zulip.upload_file.assert_not_called()


@pytest.mark.parametrize("size, status", [(4, "success"), (5, "error")])
def test_decoded_size_bound_even_with_equal_encoded_length(
    upload_http, monkeypatch, size, status
):
    http, zulip = upload_http
    monkeypatch.setattr(files, "MAX_FILE_SIZE", 4)
    content = b"x" * size
    encoded = base64.b64encode(content).decode("ascii")
    assert len(encoded) == 8
    result = upload(http, file_content_base64=encoded)
    assert result["status"] == status
    if status == "success":
        zulip.upload_file.assert_called_once_with(content, "upload.bin")
    else:
        assert "too large" in result["error"]
        zulip.upload_file.assert_not_called()
