"""Prevent credential disclosure and remote access to server-local paths."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from zulipchat_mcp.tools.files import _validate_download_url, manage_files, upload_file


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.example/user_uploads/file.txt",
        "http://zulip.example/user_uploads/file.txt",
        "https://zulip.example:444/user_uploads/file.txt",
        "https://zulip.example@attacker.example/user_uploads/file.txt",
        "https://user@zulip.example/user_uploads/file.txt",
        "https://zulip.example/api/v1/users/me",
        "https://zulip.example/user_uploads/../api/v1/users/me",
        "https://zulip.example/user_uploads/%2e%2e/api/v1/users/me",
        "https://zulip.example/user_uploads/%252e%252e/api/v1/users/me",
    ],
)
async def test_untrusted_downloads_do_not_send_credentials_or_write(url, tmp_path):
    client = MagicMock(base_url="https://zulip.example")
    with (
        patch("zulipchat_mcp.tools.files.get_client", return_value=client),
        patch("httpx.AsyncClient") as http,
    ):
        result = await manage_files(
            "download", file_id=url, download_path=str(tmp_path / "out")
        )
    assert result["status"] == "error"
    http.assert_not_called()
    assert not (tmp_path / "out").exists()


def test_configured_origin_accepts_equivalent_default_port():
    client = MagicMock(base_url="https://zulip.example/api/v1")
    _validate_download_url(client, "https://zulip.example:443/user_uploads/1/file.txt")


async def test_delete_requires_unsafe_mode_before_api_call():
    client = MagicMock()
    with (
        patch("zulipchat_mcp.tools.files.get_client", return_value=client),
        patch("zulipchat_mcp.tools.files.is_unsafe_mode", return_value=False),
    ):
        result = await manage_files("delete", file_id="123")
    assert result["status"] == "error"
    assert "--unsafe" in result["error"]
    client.client.call_endpoint.assert_not_called()


async def test_local_upload_limit_is_enforced_before_reading_entire_file(tmp_path):
    path = tmp_path / "oversize"
    with path.open("wb") as file:
        file.truncate(26 * 1024 * 1024)
    with patch("zulipchat_mcp.tools.files.get_client") as client:
        result = await upload_file(file_path=str(path))
    assert result["status"] == "error"
    assert "too large" in result["error"]
    client.return_value.upload_file.assert_not_called()


@pytest.mark.parametrize("redirect", [False, True])
async def test_download_limits_preserve_existing_destination(
    monkeypatch, tmp_path, redirect
):
    from zulipchat_mcp.tools import files

    requests = []

    def respond(request):
        requests.append(request)
        if redirect:
            return httpx.Response(
                302, headers={"location": "https://attacker.example/collect"}
            )
        return httpx.Response(200, content=b"oversized-download")

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond),
            **kwargs,
        ),
    )
    monkeypatch.setattr(files, "MAX_FILE_SIZE", 8)
    client = MagicMock(base_url="https://zulip.example")
    client.client.email = "user@example.com"
    client.client.api_key = "test-key"
    monkeypatch.setattr(files, "get_client", lambda: client)
    destination = tmp_path / "existing"
    destination.write_bytes(b"keep me")
    result = await manage_files(
        "download", file_id="1/file", download_path=str(destination)
    )
    assert result["status"] == "error"
    assert len(requests) == 1
    assert requests[0].url.host == "zulip.example"
    assert destination.read_bytes() == b"keep me"
