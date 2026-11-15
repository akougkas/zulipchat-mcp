"""Tests for tool reliability improvements in v0.4.0.

This module tests the key fixes implemented in v0.4.0:
1. Type validation with string-to-int conversion
2. User resolution with fuzzy matching
3. Structured error messages with recovery guidance
4. Parameter validation improvements

As specified in strategic_optimization_plan.md.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from zulipchat_mcp.tools.search import (
    AmbiguousUserError,
    UserNotFoundError,
    resolve_user_identifier,
)


class TestUserResolution:
    """Test user resolution with fuzzy matching."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client with sample users."""
        client = Mock()
        client.get_users.return_value = {
            "result": "success",
            "members": [
                {
                    "email": "jaime.garcia@example.edu",
                    "full_name": "Jaime Garcia",
                    "user_id": 123,
                },
                {
                    "email": "john.doe@example.com",
                    "full_name": "John Doe",
                    "user_id": 124,
                },
                {
                    "email": "jane.smith@example.com",
                    "full_name": "Jane Smith",
                    "user_id": 125,
                },
            ],
        }
        return client

    @pytest.mark.asyncio
    async def test_resolve_exact_email_match(self, mock_client):
        """Test exact email matching works."""
        result = await resolve_user_identifier("jaime.garcia@example.edu", mock_client)
        assert result["email"] == "jaime.garcia@example.edu"
        assert result["full_name"] == "Jaime Garcia"

    @pytest.mark.asyncio
    async def test_resolve_exact_name_match(self, mock_client):
        """Test exact full name matching works."""
        result = await resolve_user_identifier("Jaime Garcia", mock_client)
        assert result["email"] == "jaime.garcia@example.edu"
        assert result["full_name"] == "Jaime Garcia"

    @pytest.mark.asyncio
    async def test_resolve_partial_name_match(self, mock_client):
        """Test partial name matching (key functionality from strategic plan)."""
        result = await resolve_user_identifier("Jaime", mock_client)
        assert result["email"] == "jaime.garcia@example.edu"
        assert result["full_name"] == "Jaime Garcia"

    @pytest.mark.asyncio
    async def test_resolve_case_insensitive_match(self, mock_client):
        """Test case insensitive matching."""
        result = await resolve_user_identifier("jaime garcia", mock_client)
        assert result["email"] == "jaime.garcia@example.edu"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_user(self, mock_client):
        """Test nonexistent user raises UserNotFoundError."""
        with pytest.raises(UserNotFoundError) as exc_info:
            await resolve_user_identifier("NonexistentUser", mock_client)

        assert "No user matching 'NonexistentUser'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resolve_ambiguous_user(self, mock_client):
        """Test ambiguous matches raise AmbiguousUserError."""
        # Add another John to create ambiguity
        mock_client.get_users.return_value["members"].append(
            {
                "email": "john.wilson@example.com",
                "full_name": "John Wilson",
                "user_id": 126,
            }
        )

        with pytest.raises(AmbiguousUserError) as exc_info:
            await resolve_user_identifier("John", mock_client)

        error = exc_info.value
        assert len(error.matches) >= 2
        assert "Multiple matches for 'John'" in str(error)

    @pytest.mark.asyncio
    async def test_resolve_api_error_handling(self, mock_client):
        """Test API error handling."""
        mock_client.get_users.return_value = {
            "result": "error",
            "msg": "API connection failed",
        }

        with pytest.raises(Exception) as exc_info:
            await resolve_user_identifier("test", mock_client)

        assert "Failed to fetch users" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__])
