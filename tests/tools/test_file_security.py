"""Prevent credential disclosure, path escapes and remote access to local paths."""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from zulipchat_mcp.core.security import set_file_root
from zulipchat_mcp.tools.files import (
    _validate_download_url,
    delete_file,
    download_file,
    upload_file,
)


@pytest.fixture
def root(tmp_path):
    """A file root with an outside directory beside it."""
    inside = tmp_path / "root"
    inside.mkdir()
    (tmp_path / "outside").mkdir()
    set_file_root(inside)
    yield inside
    set_file_root(None)


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
async def test_untrusted_downloads_do_not_send_credentials_or_write(url, root):
    client = MagicMock(base_url="https://zulip.example")
    with (
        patch("zulipchat_mcp.tools.files.get_client", return_value=client),
        patch("httpx.AsyncClient") as http,
    ):
        result = await download_file(file_id=url, download_path=str(root / "out"))
    assert result["status"] == "error"
    http.assert_not_called()
    assert not (root / "out").exists()


def test_configured_origin_accepts_equivalent_default_port():
    client = MagicMock(base_url="https://zulip.example/api/v1")
    _validate_download_url(client, "https://zulip.example:443/user_uploads/1/file.txt")


async def test_delete_requires_unsafe_mode_before_api_call():
    client = MagicMock()
    with (
        patch("zulipchat_mcp.tools.files.get_client", return_value=client),
        patch("zulipchat_mcp.tools.files.is_unsafe_mode", return_value=False),
    ):
        result = await delete_file(attachment_id=123)
    assert result["status"] == "error"
    assert result["error"]["code"] == "POLICY_DENIED"
    assert "--unsafe" in result["error"]["message"]
    client.client.call_endpoint.assert_not_called()


async def test_local_upload_limit_is_enforced_before_reading_entire_file(root):
    path = root / "oversize"
    with path.open("wb") as file:
        file.truncate(26 * 1024 * 1024)
    with patch("zulipchat_mcp.tools.files.get_client") as client:
        result = await upload_file(file_path=str(path))
    assert result["status"] == "error"
    assert "too large" in result["error"]["message"]
    client.return_value.upload_file.assert_not_called()


@pytest.mark.parametrize("redirect", [False, True])
async def test_download_limits_write_nothing(monkeypatch, root, redirect):
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
    destination = root / "new"
    result = await download_file(file_id="1/file", download_path=str(destination))
    assert result["status"] == "error"
    assert len(requests) == 1
    assert requests[0].url.host == "zulip.example"
    assert not destination.exists()


async def test_download_never_overwrites_and_makes_no_request(root):
    destination = root / "existing"
    destination.write_bytes(b"keep me")
    client = MagicMock(base_url="https://zulip.example")
    with (
        patch("zulipchat_mcp.tools.files.get_client", return_value=client),
        patch("httpx.AsyncClient") as http,
    ):
        result = await download_file(file_id="1/file", download_path=str(destination))
    assert result["error"]["code"] == "ALREADY_EXISTS"
    http.assert_not_called()
    assert destination.read_bytes() == b"keep me"


def _escapes(root):
    outside = root.parent / "outside"
    (outside / "secret").write_bytes(b"secret")
    os.symlink(outside, root / "link")
    os.symlink(outside / "secret", root / "secret-link")
    return [
        str(outside / "secret"),
        str(root / ".." / "outside" / "secret"),
        str(root / "link" / "secret"),
        str(root / "secret-link"),
        "/etc/passwd",
    ]


async def test_upload_refuses_paths_outside_the_root(root):
    with patch("zulipchat_mcp.tools.files.get_client") as client:
        for path in _escapes(root):
            result = await upload_file(file_path=path)
            assert result["error"]["code"] == "PATH_OUTSIDE_ROOT", path
            assert str(root) in result["error"]["recovery"]["hint"]
    client.return_value.upload_file.assert_not_called()


async def test_upload_refuses_a_directory_inside_the_root(root):
    (root / "dir").mkdir()
    with patch("zulipchat_mcp.tools.files.get_client") as client:
        result = await upload_file(file_path=str(root / "dir"))
    assert result["error"]["code"] == "FILE_UNREADABLE"
    client.return_value.upload_file.assert_not_called()


async def test_download_refuses_paths_outside_the_root(root):
    _escapes(root)
    client = MagicMock(base_url="https://zulip.example")
    targets = [
        str(root.parent / "outside" / "new"),
        str(root / ".." / "outside" / "new"),
        str(root / "link" / "new"),
    ]
    with (
        patch("zulipchat_mcp.tools.files.get_client", return_value=client),
        patch("httpx.AsyncClient") as http,
    ):
        for target in targets:
            result = await download_file(file_id="1/file", download_path=target)
            assert result["error"]["code"] == "PATH_OUTSIDE_ROOT", target
    http.assert_not_called()
    assert not (root.parent / "outside" / "new").exists()


async def test_relative_paths_resolve_against_the_working_directory(root, monkeypatch):
    monkeypatch.chdir(root.parent / "outside")
    (root.parent / "outside" / "here").write_bytes(b"x")
    with patch("zulipchat_mcp.tools.files.get_client"):
        result = await upload_file(file_path="here")
    assert result["error"]["code"] == "PATH_OUTSIDE_ROOT"


def test_file_root_defaults_to_env_then_cwd(tmp_path, monkeypatch):
    from zulipchat_mcp.core.security import file_root

    set_file_root(None)
    monkeypatch.delenv("ZULIPCHAT_FILE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert file_root() == tmp_path.resolve()
    monkeypatch.setenv("ZULIPCHAT_FILE_ROOT", str(tmp_path / "env"))
    assert file_root() == (tmp_path / "env").resolve()
