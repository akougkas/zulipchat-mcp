"""Tests for tools/users.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.users import (
    get_own_user,
    get_presence,
    get_user_by_email,
    get_user_by_id,
    get_user_group_members,
    get_user_groups,
    get_user_presence,
    get_user_status,
    get_users,
    mute_user,
    unmute_user,
    update_status,
    validate_email,
)


class TestUsersTools:
    """Tests for user tools."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        # Setup common returns
        client.get_users.return_value = {"result": "success", "members": []}
        client.get_user_by_id.return_value = {"result": "success", "user": {}}
        client.get_user_by_email.return_value = {"result": "success", "user": {}}
        client.client.call_endpoint.return_value = {"result": "success"}
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        with patch("src.zulipchat_mcp.tools.users.get_client") as mock_get_client:
            mock_get_client.return_value = mock_client
            yield mock_client

    def test_validate_email(self):
        """Test email validation."""
        assert validate_email("user@example.com") is True
        assert validate_email("invalid") is False
        assert validate_email("user@.com") is False

    @pytest.mark.asyncio
    async def test_get_users(self, mock_deps):
        """Test get_users."""
        mock_deps.get_users.return_value = {
            "result": "success",
            "members": [
                {"user_id": 1, "email": "u1@e.com"},
                {"user_id": 2, "email": "u2@e.com"},
            ],
        }

        # All users
        result = await get_users()
        assert result["status"] == "success"
        assert result["count"] == 2

        # Filtering happens in the client wrapper
        mock_deps.get_users.return_value = {
            "result": "success",
            "members": [{"user_id": 1, "email": "u1@e.com"}],
        }
        result = await get_users(user_ids=[1])
        assert result["status"] == "success"
        assert result["count"] == 1
        assert mock_deps.get_users.call_args.kwargs["user_ids"] == [1]

    @pytest.mark.asyncio
    async def test_get_users_compact_unless_verbose(self, mock_deps):
        raw = {
            "user_id": 1,
            "full_name": "U",
            "email": "u1@e.com",
            "delivery_email": "private@e.com",
            "avatar_url": "https://a",
        }
        mock_deps.get_users.return_value = {"result": "success", "members": [raw]}

        assert (await get_users())["users"] == [
            {"user_id": 1, "name": "U", "email": "u1@e.com", "role": None}
        ]
        assert (await get_users(verbose=True))["users"] == [raw]

    @pytest.mark.asyncio
    async def test_get_users_names_roles_and_filters_by_role(self, mock_deps):
        mock_deps.get_users.return_value = {
            "result": "success",
            "members": [
                {"user_id": 1, "full_name": "Owner", "role": 100, "timezone": "UTC"},
                {"user_id": 2, "full_name": "Admin", "role": 200, "is_active": False},
                {"user_id": 3, "full_name": "Bot", "role": 400, "is_bot": True},
            ],
        }
        rows = (await get_users())["users"]
        assert [row["role"] for row in rows] == ["owner", "admin", "member"]
        assert "timezone" not in rows[0]
        assert rows[1]["inactive"] is True and rows[2]["bot"] is True
        admins = await get_users(role="admin")
        assert [row["name"] for row in admins["users"]] == ["Admin"]

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_deps):
        """Test get_user_by_id."""
        result = await get_user_by_id(1)
        assert result["status"] == "success"
        mock_deps.get_user_by_id.assert_called_with(1, False)

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, mock_deps):
        """Test get_user_by_email."""
        # Invalid email
        result = await get_user_by_email("invalid")
        assert result["status"] == "error"

        # Valid email
        result = await get_user_by_email("u@e.com")
        assert result["status"] == "success"
        mock_deps.get_user_by_email.assert_called_with("u@e.com", False)

    @pytest.mark.asyncio
    async def test_get_own_user(self, mock_deps):
        """Test get_own_user."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "user_id": 1,
            "email": "me@e.com",
            "full_name": "Me",
        }

        result = await get_own_user()
        assert result["status"] == "success"
        assert result["user"]["email"] == "me@e.com"
        mock_deps.client.call_endpoint.assert_called_with(
            "users/me", method="GET", request={}
        )

    @pytest.mark.asyncio
    async def test_get_user_status(self, mock_deps):
        """Test get_user_status."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "status": {"status_text": "busy"},
        }

        result = await get_user_status(1)
        assert result["status"] == "success"
        assert result["user_status"]["status_text"] == "busy"

    @pytest.mark.asyncio
    async def test_update_status(self, mock_deps):
        """Test update_status."""
        # Success
        result = await update_status(status_text="working")
        assert result["status"] == "success"
        mock_deps.client.call_endpoint.assert_called_with(
            "users/me/status", method="POST", request={"status_text": "working"}
        )

        # Validation error (too long)
        result = await update_status(status_text="a" * 61)
        assert result["status"] == "error"

        # Missing args
        result = await update_status()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_user_presence(self, mock_deps):
        """Test get_user_presence."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "presence": {"aggregated": {"status": "active"}},
        }

        result = await get_user_presence(1)
        assert result["status"] == "success"
        assert result["presence"]["aggregated"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_presence(self, mock_deps):
        """Test get_presence (all users)."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "presences": {"u1": {}},
        }

        result = await get_presence()
        assert result["status"] == "success"
        assert result["users_count"] == 1

    @pytest.mark.asyncio
    async def test_get_user_groups(self, mock_deps):
        """Test get_user_groups."""
        raw = {
            "id": 1,
            "name": "role:owners",
            "description": "Owners",
            "members": [7, 8],
            "is_system_group": True,
            "can_manage_group": 3,
            "date_created": 1727225467,
        }
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "user_groups": [raw],
        }

        result = await get_user_groups()
        assert result["status"] == "success"
        assert result["user_groups"] == [
            {
                "id": 1,
                "name": "role:owners",
                "description": "Owners",
                "member_count": 2,
                "is_system_group": True,
            }
        ]
        assert (await get_user_groups(verbose=True))["user_groups"] == [raw]

    @pytest.mark.asyncio
    async def test_get_user_group_members(self, mock_deps):
        """Test get_user_group_members."""
        mock_deps.client.call_endpoint.return_value = {
            "result": "success",
            "members": [1, 2],
        }

        result = await get_user_group_members(1)
        assert result["status"] == "success"
        assert result["member_count"] == 2

    @pytest.mark.asyncio
    async def test_mute_unmute_user(self, mock_deps):
        """Test mute and unmute user."""
        # Mute
        mock_deps.client.call_endpoint.return_value = {"result": "success"}
        res = await mute_user(1)
        assert res["status"] == "success"
        mock_deps.client.call_endpoint.assert_called_with(
            "users/me/muted_users/1", method="POST", request={}
        )

        # Unmute
        res = await unmute_user(1)
        assert res["status"] == "success"
        mock_deps.client.call_endpoint.assert_called_with(
            "users/me/muted_users/1", method="DELETE", request={}
        )


class TestBoundedRosters:
    @pytest.fixture
    def client(self):
        client = MagicMock()
        client.get_users.return_value = {
            "result": "success",
            "members": [
                {"user_id": i, "full_name": f"U{i}", "email": f"u{i}@x", "role": 400}
                for i in (12, 3, 100, 7, 25)
            ],
        }
        client.client.call_endpoint.return_value = {
            "result": "success",
            "presences": {f"u{i}@x": {"aggregated": {}} for i in range(5)},
        }
        with patch("src.zulipchat_mcp.tools.users.get_client", return_value=client):
            yield client

    @pytest.mark.asyncio
    async def test_get_users_pages_by_user_id(self, client):
        first = await get_users(limit=2)
        assert [u["user_id"] for u in first["users"]] == [3, 7]
        assert first["total"] == 5 and first["next_cursor"] == "7"
        second = await get_users(limit=2, cursor=first["next_cursor"])
        assert [u["user_id"] for u in second["users"]] == [12, 25]
        last = await get_users(limit=2, cursor=second["next_cursor"])
        assert [u["user_id"] for u in last["users"]] == [100]
        assert "next_cursor" not in last

    @pytest.mark.asyncio
    async def test_get_presence_pages_by_key(self, client):
        first = await get_presence(limit=3)
        assert list(first["presences"]) == ["u0@x", "u1@x", "u2@x"]
        rest = await get_presence(limit=3, cursor=first["next_cursor"])
        assert list(rest["presences"]) == ["u3@x", "u4@x"]
        assert "next_cursor" not in rest

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad", ["../me/status", "1/../../realm", 0, -5, "not-an-email"]
    )
    async def test_get_user_presence_rejects_invalid_identifier(self, client, bad):
        result = await get_user_presence(bad)
        assert result["status"] == "error"
        assert result["error"]["code"] == "INVALID_ARGUMENT"
        client.client.call_endpoint.assert_not_called()
