"""Tests for tools/files.py."""

import base64
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from src.zulipchat_mcp.tools.files import (
    _normalize_site_url,
    _normalize_upload_path,
    _resolve_download_credentials,
    _resolve_file_url,
    manage_files,
    upload_file,
    validate_file_security,
)


class TestNormalizeUploadPath:
    """Unit tests for _normalize_upload_path."""

    @pytest.mark.parametrize(
        "input_path,expected",
        [
            ("/user_uploads/43617/abc/file.txt", "/user_uploads/43617/abc/file.txt"),
            ("user_uploads/43617/abc/file.txt", "/user_uploads/43617/abc/file.txt"),
            ("/api/user_uploads/43617/abc/f.txt", "/user_uploads/43617/abc/f.txt"),
            ("api/user_uploads/43617/abc/f.txt", "/user_uploads/43617/abc/f.txt"),
            ("43617/abc/file.txt", "/user_uploads/43617/abc/file.txt"),
            ("/43617/abc/file.txt", "/user_uploads/43617/abc/file.txt"),
        ],
    )
    def test_variants(self, input_path, expected):
        assert _normalize_upload_path(input_path) == expected


class TestNormalizeSiteUrl:
    """Unit tests for _normalize_site_url."""

    @pytest.mark.parametrize(
        "input_url,expected",
        [
            ("https://chat.zulip.org", "https://chat.zulip.org"),
            ("https://chat.zulip.org/", "https://chat.zulip.org"),
            ("https://chat.zulip.org/api", "https://chat.zulip.org"),
            ("https://chat.zulip.org/api/v1", "https://chat.zulip.org"),
            ("https://org.zulipchat.com/api/v1/", "https://org.zulipchat.com"),
        ],
    )
    def test_variants(self, input_url, expected):
        assert _normalize_site_url(input_url) == expected


class TestResolveFileUrl:
    """Unit tests for _resolve_file_url."""

    def _make_client(self, base_url="https://example.zulipchat.com"):
        c = MagicMock()
        c.base_url = base_url
        return c

    def test_relative_user_uploads(self):
        url = _resolve_file_url(
            self._make_client(), "/user_uploads/43617/abc/file.txt"
        )
        assert url == "https://example.zulipchat.com/user_uploads/43617/abc/file.txt"

    def test_raw_suffix(self):
        url = _resolve_file_url(self._make_client(), "43617/abc/file.txt")
        assert url == "https://example.zulipchat.com/user_uploads/43617/abc/file.txt"

    def test_absolute_url_passthrough(self):
        abs_url = "https://other.zulipchat.com/user_uploads/1/a/b.txt"
        url = _resolve_file_url(self._make_client(), abs_url)
        assert url == abs_url

    def test_absolute_url_strips_api(self):
        url = _resolve_file_url(
            self._make_client(),
            "https://other.zulipchat.com/api/user_uploads/1/a/b.txt",
        )
        assert url == "https://other.zulipchat.com/user_uploads/1/a/b.txt"

    def test_preserves_query_and_fragment(self):
        url = _resolve_file_url(
            self._make_client(),
            "/user_uploads/1/a/b.txt?raw=1#section",
        )
        assert "?raw=1" in url
        assert "#section" in url
        assert "/api/" not in url

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _resolve_file_url(self._make_client(), "   ")

    def test_falls_back_to_sdk_client_base_url(self):
        client = MagicMock()
        client.base_url = ""
        client.client.base_url = "https://sdk.zulipchat.com/api/v1"
        url = _resolve_file_url(client, "/user_uploads/1/a/b.txt")
        assert url == "https://sdk.zulipchat.com/user_uploads/1/a/b.txt"

    def test_no_base_url_raises(self):
        client = MagicMock()
        client.base_url = ""
        client.client.base_url = ""
        with pytest.raises(ValueError, match="Unable to determine"):
            _resolve_file_url(client, "/user_uploads/1/a/b.txt")


class TestResolveDownloadCredentials:
    """Unit tests for _resolve_download_credentials."""

    def test_user_identity_prefers_sdk(self):
        client = MagicMock()
        client.identity = "user"
        client.client.email = "sdk@e.com"
        client.client.api_key = "sdk-key"
        client.current_email = "fallback@e.com"
        client.config_manager.config.email = "cfg@e.com"
        client.config_manager.config.api_key = "cfg-key"
        email, key = _resolve_download_credentials(client)
        assert email == "sdk@e.com"
        assert key == "sdk-key"

    def test_bot_identity_uses_bot_config(self):
        client = MagicMock()
        client.identity = "bot"
        client.client.email = None
        client.client.api_key = None
        client.current_email = None
        client.config_manager.config.email = "user@e.com"
        client.config_manager.config.api_key = "user-key"
        client.config_manager.config.bot_email = "bot@e.com"
        client.config_manager.config.bot_api_key = "bot-key"
        email, key = _resolve_download_credentials(client)
        assert email == "bot@e.com"
        assert key == "bot-key"

    def test_missing_credentials_raises(self):
        client = MagicMock()
        client.identity = "user"
        client.client.email = None
        client.client.api_key = None
        client.current_email = None
        client.config_manager.config.email = None
        client.config_manager.config.api_key = None
        with pytest.raises(ValueError, match="Missing Zulip credentials"):
            _resolve_download_credentials(client)

    def test_bot_falls_back_to_user_creds_when_bot_creds_missing(self):
        client = MagicMock()
        client.identity = "bot"
        client.client.email = None
        client.client.api_key = None
        client.current_email = None
        client.config_manager.config.bot_email = None
        client.config_manager.config.bot_api_key = None
        client.config_manager.config.email = "user@e.com"
        client.config_manager.config.api_key = "user-key"
        email, key = _resolve_download_credentials(client)
        assert email == "user@e.com"
        assert key == "user-key"


class TestFilesTools:
    """Tests for file management tools."""

    @pytest.fixture
    def mock_deps(self):
        with patch("src.zulipchat_mcp.tools.files.get_client") as mock_get_client:
            client = MagicMock()
            mock_get_client.return_value = client
            yield client

    def test_validate_file_security(self):
        """Test file security validation."""
        # Safe file
        res = validate_file_security(b"content", "test.txt")
        assert res["valid"] is True
        assert res["metadata"]["mime_type"] == "text/plain"

        # Large file
        large = b"a" * (25 * 1024 * 1024 + 1)
        res = validate_file_security(large, "large.txt")
        assert res["valid"] is False
        assert "File too large" in res["error"]

        # Dangerous extension
        res = validate_file_security(b"content", "script.exe")
        assert res["valid"] is True
        assert len(res["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_upload_file_content(self, mock_deps):
        """Test upload_file with content."""
        client = mock_deps
        client.upload_file.return_value = {"result": "success", "uri": "/uri"}

        result = await upload_file(file_content=b"data", filename="test.txt")

        assert result["status"] == "success"
        assert result["file_url"] == "/uri"
        client.upload_file.assert_called()

    @pytest.mark.asyncio
    async def test_upload_file_path(self, mock_deps):
        """Test upload_file with path."""
        client = mock_deps
        client.upload_file.return_value = {"result": "success", "uri": "/uri"}

        with patch("builtins.open", mock_open(read_data=b"data")):
            result = await upload_file(file_path="test.txt")

        assert result["status"] == "success"
        client.upload_file.assert_called_with(b"data", "test.txt")

    @pytest.mark.asyncio
    async def test_upload_file_share(self, mock_deps):
        """Test upload_file with sharing."""
        client = mock_deps
        client.upload_file.return_value = {"result": "success", "uri": "/uri"}
        client.send_message.return_value = {"result": "success", "id": 1}

        result = await upload_file(
            file_content=b"data", filename="test.txt", stream="general", topic="files"
        )

        assert result["status"] == "success"
        assert "shared_in_stream" in result
        client.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_manage_files_list(self, mock_deps):
        """Test manage_files list."""
        client = mock_deps
        client.client.call_endpoint.return_value = {
            "result": "success",
            "attachments": [],
        }

        result = await manage_files("list")
        assert result["status"] == "success"
        assert result["operation"] == "list"

    @pytest.mark.asyncio
    async def test_manage_files_share(self, mock_deps):
        """Test manage_files share."""
        client = mock_deps
        client.base_url = "https://zulip"
        client.send_message.return_value = {"result": "success", "id": 1}

        result = await manage_files("share", file_id="123", share_in_stream="general")

        assert result["status"] == "success"
        assert result["message_id"] == 1
        client.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_manage_files_share_with_relative_upload_path(self, mock_deps):
        """Test manage_files share with /user_uploads path input."""
        client = mock_deps
        client.base_url = "https://zulip"
        client.send_message.return_value = {"result": "success", "id": 2}

        result = await manage_files(
            "share",
            file_id="/user_uploads/43617/path/file.txt",
            share_in_stream="general",
        )

        assert result["status"] == "success"
        client.send_message.assert_called_with(
            "stream",
            "general",
            "📎 Shared file: https://zulip/user_uploads/43617/path/file.txt",
            None,
        )

    @pytest.mark.asyncio
    async def test_manage_files_share_strips_api_from_base_url(self, mock_deps):
        """Test manage_files share strips API suffix from base_url."""
        client = mock_deps
        client.base_url = "https://zulip.example.com/api/v1"
        client.send_message.return_value = {"result": "success", "id": 3}

        result = await manage_files(
            "share",
            file_id="/user_uploads/43617/path/file.txt",
            share_in_stream="general",
        )

        assert result["status"] == "success"
        client.send_message.assert_called_with(
            "stream",
            "general",
            "📎 Shared file: https://zulip.example.com/user_uploads/43617/path/file.txt",
            None,
        )

    @pytest.mark.asyncio
    async def test_manage_files_download(self, mock_deps):
        """Test manage_files download."""
        client = mock_deps
        client.base_url = "https://zulip"
        client.current_email = "me@e.com"
        client.config_manager.config.api_key = "key"
        client.client.email = None
        client.client.api_key = None

        # Test getting URL only
        result = await manage_files("download", file_id="123")
        assert result["status"] == "success"
        assert "download_url" in result

        # Test downloading to file - properly mock async context manager
        mock_response = MagicMock()
        mock_response.content = b"filedata"
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        # httpx is imported inside the function, so patch the module directly
        with patch.dict("sys.modules", {"httpx": MagicMock()}):
            import sys

            mock_async_client = MagicMock()
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_http)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            sys.modules["httpx"].AsyncClient = MagicMock(return_value=mock_async_client)

            with patch("builtins.open", mock_open()) as m_open:
                result = await manage_files(
                    "download", file_id="123", download_path="out.bin"
                )

                assert result["status"] == "success"
                m_open().write.assert_called_with(b"filedata")

    @pytest.mark.asyncio
    async def test_manage_files_download_strips_api_upload_prefix(self, mock_deps):
        """Test manage_files download normalizes /api/user_uploads file_id."""
        client = mock_deps
        client.base_url = "https://zulip.example.com"

        result = await manage_files(
            "download",
            file_id="/api/user_uploads/43617/path/file.txt?raw=1",
        )

        assert result["status"] == "success"
        assert (
            result["download_url"]
            == "https://zulip.example.com/user_uploads/43617/path/file.txt?raw=1"
        )

    @pytest.mark.asyncio
    async def test_manage_files_download_accepts_absolute_url(self, mock_deps):
        """Test manage_files download with an absolute URL."""
        client = mock_deps
        client.base_url = "https://zulip"
        file_url = "https://grc.zulipchat.com/user_uploads/43617/path/file.txt"

        result = await manage_files("download", file_id=file_url)

        assert result["status"] == "success"
        assert result["download_url"] == file_url

    @pytest.mark.asyncio
    async def test_manage_files_download_uses_sdk_credentials(self, mock_deps):
        """Test download uses SDK credentials when config values are empty."""
        client = mock_deps
        client.base_url = "https://zulip"
        client.current_email = None
        client.config_manager.config.api_key = None
        client.client.email = "sdk@example.com"
        client.client.api_key = "sdk-key"

        mock_response = MagicMock()
        mock_response.content = b"filedata"
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch.dict("sys.modules", {"httpx": MagicMock()}):
            import sys

            mock_async_client = MagicMock()
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_http)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            sys.modules["httpx"].AsyncClient = MagicMock(return_value=mock_async_client)

            with patch("builtins.open", mock_open()):
                result = await manage_files(
                    "download",
                    file_id="/user_uploads/1/file.txt",
                    download_path="out.bin",
                )

        assert result["status"] == "success"
        expected_auth = base64.b64encode(b"sdk@example.com:sdk-key").decode()
        assert mock_http.get.call_args.kwargs["headers"]["Authorization"] == (
            f"Basic {expected_auth}"
        )

    @pytest.mark.asyncio
    async def test_manage_files_download_uses_bot_config_credentials(self, mock_deps):
        """Test download uses bot credentials when bot identity is active."""
        client = mock_deps
        client.identity = "bot"
        client.base_url = "https://zulip"
        client.current_email = None
        client.client.email = None
        client.client.api_key = None
        client.config_manager.config.email = "user@example.com"
        client.config_manager.config.api_key = "user-key"
        client.config_manager.config.bot_email = "bot@example.com"
        client.config_manager.config.bot_api_key = "bot-key"

        mock_response = MagicMock()
        mock_response.content = b"filedata"
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch.dict("sys.modules", {"httpx": MagicMock()}):
            import sys

            mock_async_client = MagicMock()
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_http)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            sys.modules["httpx"].AsyncClient = MagicMock(return_value=mock_async_client)

            with patch("builtins.open", mock_open()):
                result = await manage_files(
                    "download",
                    file_id="/user_uploads/1/file.txt",
                    download_path="out.bin",
                )

        assert result["status"] == "success"
        expected_auth = base64.b64encode(b"bot@example.com:bot-key").decode()
        assert mock_http.get.call_args.kwargs["headers"]["Authorization"] == (
            f"Basic {expected_auth}"
        )

    @pytest.mark.asyncio
    async def test_manage_files_permissions(self, mock_deps):
        """Test manage_files get_permissions."""
        result = await manage_files("get_permissions")
        assert result["status"] == "success"
        assert "permissions" in result
