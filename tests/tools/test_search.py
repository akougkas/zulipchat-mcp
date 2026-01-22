"""Tests for tools/search.py."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp.tools.search import (
    AmbiguousUserError,
    UserNotFoundError,
    advanced_search,
    check_messages_match_narrow,
    construct_narrow,
    resolve_user_identifier,
    search_messages,
)


class TestSearchTools:
    """Tests for search tools."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.get_users.return_value = {
            "result": "success",
            "members": [
                {"full_name": "Test User", "email": "user@example.com", "user_id": 1},
                {
                    "full_name": "Another User",
                    "email": "another@example.com",
                    "user_id": 2,
                },
                {"full_name": "Test Bot", "email": "bot@example.com", "user_id": 3},
            ],
        }
        client.get_messages_raw.return_value = {
            "result": "success",
            "messages": [],
            "anchor": 100,
        }
        client.get_streams.return_value = {
            "result": "success",
            "streams": [{"name": "general", "description": "General stream"}],
        }
        # For check_messages_match_narrow
        client.client.call_endpoint.return_value = {
            "result": "success",
            "messages": {"1": {}},
        }
        return client

    @pytest.fixture
    def mock_deps(self, mock_client):
        with (
            patch("src.zulipchat_mcp.tools.search.get_config_manager"),
            patch("src.zulipchat_mcp.tools.search.ZulipClientWrapper") as mock_wrapper,
        ):
            mock_wrapper.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_resolve_user_identifier(self, mock_client):
        """Test user resolution logic."""
        # Exact email
        res = await resolve_user_identifier("user@example.com", mock_client)
        assert res["email"] == "user@example.com"

        # Exact name
        res = await resolve_user_identifier("Test User", mock_client)
        assert res["email"] == "user@example.com"

        # Fuzzy name
        res = await resolve_user_identifier("another", mock_client)
        assert res["email"] == "another@example.com"

        # Not found
        with pytest.raises(UserNotFoundError):
            await resolve_user_identifier("nonexistent", mock_client)

        # Ambiguous (mock behavior for similar names)
        mock_client.get_users.return_value["members"].append(
            {"full_name": "Another User 2", "email": "a2@example.com"}
        )
        # "Another" matches both Another User and Another User 2
        # But "Another User" matches exact.
        # Let's try "Another"
        with pytest.raises(AmbiguousUserError):
            await resolve_user_identifier("Another", mock_client)

    @pytest.mark.asyncio
    async def test_search_messages_basic(self, mock_deps):
        """Test basic search."""
        mock_deps.get_messages_raw.return_value = {
            "result": "success",
            "messages": [
                {
                    "id": 1,
                    "sender_full_name": "U",
                    "sender_email": "e",
                    "timestamp": 100,
                    "content": "c",
                    "type": "stream",
                    "display_recipient": "s",
                    "subject": "t",
                }
            ],
        }

        result = await search_messages(query="hello")

        assert result["status"] == "success"
        assert len(result["messages"]) == 1

        # Verify call
        args = mock_deps.get_messages_raw.call_args[1]
        narrow = args["narrow"]
        assert {"operator": "search", "operand": "hello"} in narrow

    @pytest.mark.asyncio
    async def test_time_filter_post_fetch(self, mock_deps):
        """Test that time filtering happens after fetch (Bug Regression).

        When no narrow filter is provided, the fallback strategy uses
        anchor='newest' to avoid Zulip server timeouts, then filters
        client-side by timestamp.
        """
        now = datetime.now()
        ts_now = now.timestamp()
        ts_old = (now - timedelta(hours=2)).timestamp()

        mock_deps.get_messages_raw.return_value = {
            "result": "success",
            "messages": [
                {
                    "id": 1,
                    "sender_full_name": "U",
                    "sender_email": "e",
                    "timestamp": ts_now,
                    "content": "recent",
                    "type": "s",
                },
                {
                    "id": 2,
                    "sender_full_name": "U",
                    "sender_email": "e",
                    "timestamp": ts_old,
                    "content": "old",
                    "type": "s",
                },
            ],
        }

        # Search last 1 hour (no narrow = fallback to anchor="newest")
        result = await search_messages(last_hours=1)

        assert result["status"] == "success"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "recent"

        # Without a narrow, fallback uses anchor="newest" (avoids server timeout)
        args = mock_deps.get_messages_raw.call_args[1]
        assert args["anchor"] == "newest"

    @pytest.mark.asyncio
    async def test_time_filter_with_stream_uses_anchor_date(self, mock_deps):
        """Test that anchor='date' is used when a stream narrow is provided."""
        now = datetime.now()
        ts_now = now.timestamp()

        mock_deps.get_messages_raw.return_value = {
            "result": "success",
            "messages": [
                {
                    "id": 1,
                    "sender_full_name": "U",
                    "sender_email": "e",
                    "timestamp": ts_now,
                    "content": "msg",
                    "type": "stream",
                    "display_recipient": "test-stream",
                    "subject": "topic",
                },
            ],
        }

        # Search with stream filter = anchor="date" is used
        result = await search_messages(stream="test-stream", last_hours=1)

        assert result["status"] == "success"

        # With a narrow filter, anchor="date" is used efficiently
        args = mock_deps.get_messages_raw.call_args[1]
        assert args["anchor"] == "date"
        assert args["anchor_date"] is not None

    @pytest.mark.asyncio
    async def test_search_messages_fuzzy_user(self, mock_deps):
        """Test search with sender name requiring resolution."""
        # 'Test User' resolves to 'user@example.com'
        await search_messages(sender="Test User")

        args = mock_deps.get_messages_raw.call_args[1]
        narrow = args["narrow"]
        # Should be resolved email
        assert {"operator": "sender", "operand": "user@example.com"} in narrow

    @pytest.mark.asyncio
    async def test_advanced_search_aggregations(self, mock_deps):
        """Test advanced search aggregations."""
        mock_deps.get_messages_raw.return_value = {
            "result": "success",
            "messages": [
                {
                    "id": 1,
                    "sender_full_name": "U1",
                    "sender_email": "e1",
                    "timestamp": 100,
                    "content": "c",
                    "type": "stream",
                    "display_recipient": "s1",
                },
                {
                    "id": 2,
                    "sender_full_name": "U1",
                    "sender_email": "e1",
                    "timestamp": 100,
                    "content": "c",
                    "type": "stream",
                    "display_recipient": "s1",
                },
                {
                    "id": 3,
                    "sender_full_name": "U2",
                    "sender_email": "e2",
                    "timestamp": 100,
                    "content": "c",
                    "type": "stream",
                    "display_recipient": "s2",
                },
            ],
        }

        result = await advanced_search(
            query="",
            search_type=["messages"],
            aggregations=["count_by_user", "count_by_stream"],
        )

        assert result["status"] == "success"
        agg = result["results"]["aggregations"]
        assert agg["count_by_user"]["U1"] == 2
        assert agg["count_by_user"]["U2"] == 1
        assert agg["count_by_stream"]["s1"] == 2

    @pytest.mark.asyncio
    async def test_construct_narrow(self):
        """Test narrow construction."""
        result = await construct_narrow(
            stream="general", has_image=True, is_private=False
        )
        assert result["status"] == "success"
        narrow = result["narrow"]

        assert {"operator": "stream", "operand": "general"} in narrow
        assert {"operator": "has", "operand": "image"} in narrow
        assert {"operator": "is", "operand": "private", "negated": True} in narrow

    @pytest.mark.asyncio
    async def test_check_messages_match_narrow(self, mock_deps):
        """Test check_messages_match_narrow."""
        result = await check_messages_match_narrow(
            msg_ids=[1, 2], narrow=[{"operator": "stream", "operand": "general"}]
        )

        assert result["status"] == "success"
        assert result["total_checked"] == 2
        assert result["matching_count"] == 1  # Based on mock return {"1": {}}
        assert result["non_matching_count"] == 1
