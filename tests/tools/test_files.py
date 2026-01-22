"""Tests for tools/files.py."""

from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from src.zulipchat_mcp.tools.files import (
    manage_files,
    upload_file,
    validate_file_security,
)


class TestFilesTools:
    """Tests for file management tools."""

    @pytest.fixture
    def mock_deps(self):
        with (
            patch("src.zulipchat_mcp.tools.files.get_config_manager"),
            patch("src.zulipchat_mcp.tools.files.ZulipClientWrapper") as mock_wrapper,
        ):

            client = MagicMock()
            mock_wrapper.return_value = client
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
    async def test_manage_files_download(self, mock_deps):
        """Test manage_files download."""
        client = mock_deps
        client.base_url = "https://zulip"
        client.current_email = "me@e.com"
        client.config_manager.config.api_key = "key"

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
    async def test_manage_files_permissions(self, mock_deps):
        """Test manage_files get_permissions."""
        result = await manage_files("get_permissions")
        assert result["status"] == "success"
        assert "permissions" in result
