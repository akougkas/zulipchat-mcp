"""Tests for write operations in tools/files.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.files import manage_files, upload_file


class TestFileOperations:
    """Tests for file operations."""

    @pytest.fixture
    def mock_client(self):
        """Mock ZulipClientWrapper."""
        client = MagicMock()
        client.upload_file.return_value = {
            "result": "success",
            "uri": "/user_uploads/1/file.txt",
        }
        client.send_message.return_value = {"result": "success", "id": 100}
        client.client.call_endpoint.return_value = {"result": "success"}
        client.base_url = "https://zulip.example.com"
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        """Patch dependencies."""
        with (
            patch("src.zulipchat_mcp.tools.files.get_config_manager"),
            patch("src.zulipchat_mcp.tools.files.ZulipClientWrapper") as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_upload_valid_file(self, mock_deps):
        """Test uploading a valid file."""
        content = b"Simple text file"
        result = await upload_file(file_content=content, filename="test.txt")
        assert result["status"] == "success"
        assert result["file_url"] == "/user_uploads/1/file.txt"

        mock_deps.upload_file.assert_called_with(content, "test.txt")

    @pytest.mark.asyncio
    async def test_upload_nonexistent_file(self, mock_deps):
        """Test uploading a file from path that doesn't exist."""
        # Use built-in open patch for the specific module
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            result = await upload_file(file_path="nonexistent.txt")
            assert result["status"] == "error"
            assert "Failed to read file" in result["error"]

    @pytest.mark.asyncio
    async def test_upload_empty_file(self, mock_deps):
        """Test uploading empty content."""
        result = await upload_file(file_content=b"", filename="empty.txt")
        assert result["status"] == "error"
        # It hits the first check `if not file_content and not file_path`
        assert "Either file_content or file_path is required" in result["error"]

    @pytest.mark.asyncio
    async def test_upload_large_file(self, mock_deps):
        """Test uploading file larger than limit."""
        large_content = b"a" * (25 * 1024 * 1024 + 1)
        result = await upload_file(file_content=large_content, filename="big.dat")
        assert result["status"] == "error"
        assert "File too large" in result["error"]

    @pytest.mark.asyncio
    async def test_upload_dangerous_extension(self, mock_deps):
        """Test uploading file with dangerous extension."""
        # The tool currently adds WARNINGS but does not block dangerous extensions in `validate_file_security`.
        # `if not validation["valid"]: return error`.
        # `dangerous_extensions` adds to `warnings`, but doesn't set `valid=False`.
        # So this should SUCCEED with warnings.

        result = await upload_file(file_content=b"script", filename="malware.exe")
        assert result["status"] == "success"
        assert "warnings" in result
        assert any("dangerous" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_upload_with_path_traversal(self, mock_deps):
        """Test upload with path traversal in filename (security check)."""
        # The code uses `os.path.basename` when reading from file_path.
        # If passed as filename argument, it's used as is.
        # Zulip server handles filename sanitization usually.
        # The tool doesn't explicitly block ".." in filename arg.

        result = await upload_file(file_content=b"data", filename="../../../etc/passwd")
        assert result["status"] == "success"
        # Verify it passed the filename as is to client
        mock_deps.upload_file.assert_called_with(b"data", "../../../etc/passwd")

    @pytest.mark.asyncio
    async def test_list_files(self, mock_deps):
        """Test listing files."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "attachments": [{"id": 1, "name": "test.txt"}],
        }
        result = await manage_files(operation="list")
        assert result["status"] == "success"
        assert result["operation"] == "list"
        assert len(result["files"]) == 1
        assert result["files"][0]["name"] == "test.txt"

        mock_deps.client.call_endpoint.assert_called_with(
            "attachments", method="GET", request={}
        )

    @pytest.mark.asyncio
    async def test_delete_own_file(self, mock_deps):
        """Test delete operation."""
        result = await manage_files(operation="delete", file_id="1")
        assert result["status"] == "success"
        assert result["operation"] == "delete"

        mock_deps.client.call_endpoint.assert_called_with(
            "attachments/1", method="DELETE", request={}
        )

    @pytest.mark.asyncio
    async def test_delete_others_file_fails(self, mock_deps):
        """Test delete others file (API failure)."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "error",
            "msg": "Permission denied",
        }
        result = await manage_files(operation="delete", file_id="2")
        assert result["status"] == "error"
        assert "Permission denied" in result["error"]

    @pytest.mark.asyncio
    async def test_share_file_to_stream(self, mock_deps):
        """Test sharing a file."""
        result = await manage_files(
            operation="share",
            file_id="123",
            share_in_stream="general",
            share_in_topic="resources",
        )
        assert result["status"] == "success"
        assert result["operation"] == "share"
        mock_deps.send_message.assert_called()
