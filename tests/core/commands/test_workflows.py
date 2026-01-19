"""Tests for core/commands/workflows.py."""

from unittest.mock import MagicMock

import pytest

from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.core.commands.workflows import (
    ChainBuilder,
    create_monitored_message_chain,
    create_simple_notification_chain,
)


class TestChainBuilder:
    """Tests for ChainBuilder workflows."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=ZulipClientWrapper)
        # Setup defaults for client calls
        client.send_message.return_value = {"result": "success", "id": 100}
        client.add_reaction.return_value = {"result": "success"}
        client.get_messages_from_stream.return_value = {
            "result": "success",
            "messages": [],
        }
        client.get_messages.return_value = []
        return client

    def test_create_message_workflow(self, mock_client):
        """Test message workflow execution."""
        chain = ChainBuilder.create_message_workflow(
            stream_name="general",
            topic="test",
            content="hello",
            add_reaction=True,
            emoji="smile",
        )

        ctx = chain.execute(client=mock_client, initial_context={"dummy": "init"})

        assert ctx.has_errors() is False
        mock_client.send_message.assert_called_with(
            "stream", "general", "hello", "test"
        )
        mock_client.add_reaction.assert_called_with(100, "smile")

    def test_create_message_workflow_no_reaction(self, mock_client):
        """Test message workflow without reaction."""
        chain = ChainBuilder.create_message_workflow(
            stream_name="general", topic="test", content="hello", add_reaction=False
        )

        chain.execute(client=mock_client, initial_context={"dummy": "init"})

        mock_client.send_message.assert_called()
        mock_client.add_reaction.assert_not_called()

    def test_create_digest_workflow(self, mock_client):
        """Test digest workflow execution."""
        # Setup messages for streams
        mock_client.get_messages_from_stream.side_effect = [
            {
                "result": "success",
                "messages": [{"sender_full_name": "Alice", "content": "Hi", "id": 1}],
            },
            {
                "result": "success",
                "messages": [{"sender_full_name": "Bob", "content": "Bye", "id": 2}],
            },
        ]

        chain = ChainBuilder.create_digest_workflow(
            stream_names=["s1", "s2"],
            hours_back=12,
            target_stream="summary",
            target_topic="Daily",
        )

        ctx = chain.execute(client=mock_client, initial_context={"dummy": "init"})

        assert ctx.has_errors() is False

        # Verify get_messages calls
        assert mock_client.get_messages_from_stream.call_count == 2

        # Verify digest content sent
        mock_client.send_message.assert_called()
        args = mock_client.send_message.call_args[0]
        content = args[2]

        assert "Daily Digest" in content
        assert "#s1 (1 messages)" in content
        assert "#s2 (1 messages)" in content
        assert "Total messages across all streams: 2" in content

    def test_create_daily_summary_workflow(self, mock_client):
        """Test daily summary helper."""
        chain = ChainBuilder.create_daily_summary_workflow(streams=["s1"])

        # Setup mock return for get_messages_from_stream to avoid failures in loop
        mock_client.get_messages_from_stream.return_value = {
            "result": "success",
            "messages": [],
        }

        # Verify chain structure implicitly by execution
        chain.execute(client=mock_client, initial_context={"dummy": "init"})
        mock_client.get_messages_from_stream.assert_called()

    def test_create_morning_briefing_workflow(self, mock_client):
        """Test morning briefing helper."""
        chain = ChainBuilder.create_morning_briefing_workflow(priority_streams=["s1"])
        mock_client.get_messages_from_stream.return_value = {
            "result": "success",
            "messages": [],
        }
        chain.execute(client=mock_client, initial_context={"dummy": "init"})
        mock_client.get_messages_from_stream.assert_called()

    def test_create_catch_up_workflow(self, mock_client):
        """Test catch up helper."""
        chain = ChainBuilder.create_catch_up_workflow(max_streams=1)
        mock_client.get_messages_from_stream.return_value = {
            "result": "success",
            "messages": [],
        }
        chain.execute(client=mock_client, initial_context={"dummy": "init"})
        mock_client.get_messages_from_stream.assert_called()


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_simple_notification_chain(self):
        """Test create_simple_notification_chain."""
        chain = create_simple_notification_chain("s", "t", "msg")
        assert chain.name == "message_workflow"
        # Can verify content processor logic if needed, or trust create_message_workflow test

    def test_create_monitored_message_chain(self):
        """Test create_monitored_message_chain."""
        chain = create_monitored_message_chain("s", "t", "msg", "eyes")
        assert chain.name == "message_workflow"
