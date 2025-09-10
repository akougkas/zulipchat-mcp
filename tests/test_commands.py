"""Comprehensive tests for the full command chain system.

The commands.py module contains 830 lines of complex command chain functionality including:
- ExecutionContext with data passing, error tracking, rollback support
- Condition system with 8 different operators
- Multiple command types: SendMessage, GetMessages, AddReaction, ProcessData
- CommandChain with execution, rollback, and chain building
- ChainBuilder with static methods for creating common workflows

This test suite aims to achieve 80%+ coverage of this critical system.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.zulipchat_mcp.core.commands.engine import (
    AddReactionCommand,
    ChainBuilder,
    Command,
    CommandChain,
    Condition,
    ConditionOperator,
    ExecutionContext,
    ExecutionStatus,
    GetMessagesCommand,
    ProcessDataCommand,
    SendMessageCommand,
)
from src.zulipchat_mcp.core.exceptions import ValidationError, ZulipMCPError

# Mock ZulipMessage for tests
class ZulipMessage:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestExecutionContext:
    """Test ExecutionContext data passing and state management."""

    def test_execution_context_initialization(self):
        """Test ExecutionContext initialization with defaults."""
        context = ExecutionContext()

        assert context.data == {}
        assert isinstance(context.start_time, datetime)
        assert context.chain_id == ""
        assert context.current_command is None
        assert context.executed_commands == []
        assert context.rollback_data == {}
        assert context.errors == []
        assert context.warnings == []

    def test_execution_context_custom_initialization(self):
        """Test ExecutionContext with custom initial data."""
        initial_data = {"key1": "value1", "key2": 42}
        context = ExecutionContext(data=initial_data, chain_id="test-chain")

        assert context.data == initial_data
        assert context.chain_id == "test-chain"

    def test_context_get_set_operations(self):
        """Test context data get/set operations."""
        context = ExecutionContext()

        # Test setting and getting values
        context.set("test_key", "test_value")
        assert context.get("test_key") == "test_value"

        # Test default value
        assert context.get("nonexistent", "default") == "default"
        assert context.get("nonexistent") is None

    def test_context_error_tracking(self):
        """Test error tracking in context."""
        context = ExecutionContext()

        assert not context.has_errors()

        test_error = ValueError("Test error")
        context.add_error("test_command", test_error)

        assert context.has_errors()
        assert len(context.errors) == 1

        error_entry = context.errors[0]
        assert error_entry["command"] == "test_command"
        assert error_entry["error"] == "Test error"
        assert error_entry["type"] == "ValueError"
        assert "timestamp" in error_entry

    def test_context_warning_tracking(self):
        """Test warning tracking in context."""
        context = ExecutionContext()

        context.add_warning("Test warning")

        assert len(context.warnings) == 1
        assert "Test warning" in context.warnings[0]
        assert datetime.now().isoformat()[:10] in context.warnings[0]  # Check date part


class TestConditionSystem:
    """Test the condition system for conditional execution."""

    def test_condition_equals_operator(self):
        """Test EQUALS condition operator."""
        condition = Condition("status", ConditionOperator.EQUALS, "active")
        context = ExecutionContext()

        context.set("status", "active")
        assert condition.evaluate(context) is True

        context.set("status", "inactive")
        assert condition.evaluate(context) is False

    def test_condition_not_equals_operator(self):
        """Test NOT_EQUALS condition operator."""
        condition = Condition("status", ConditionOperator.NOT_EQUALS, "inactive")
        context = ExecutionContext()

        context.set("status", "active")
        assert condition.evaluate(context) is True

        context.set("status", "inactive")
        assert condition.evaluate(context) is False

    def test_condition_greater_than_operator(self):
        """Test GREATER_THAN condition operator."""
        condition = Condition("count", ConditionOperator.GREATER_THAN, 10)
        context = ExecutionContext()

        context.set("count", 15)
        assert condition.evaluate(context) is True

        context.set("count", 5)
        assert condition.evaluate(context) is False

    def test_condition_less_than_operator(self):
        """Test LESS_THAN condition operator."""
        condition = Condition("count", ConditionOperator.LESS_THAN, 10)
        context = ExecutionContext()

        context.set("count", 5)
        assert condition.evaluate(context) is True

        context.set("count", 15)
        assert condition.evaluate(context) is False

    def test_condition_contains_operator(self):
        """Test CONTAINS condition operator."""
        condition = Condition("message", ConditionOperator.CONTAINS, "error")
        context = ExecutionContext()

        context.set("message", "System error occurred")
        assert condition.evaluate(context) is True

        context.set("message", "All systems normal")
        assert condition.evaluate(context) is False

    def test_condition_not_contains_operator(self):
        """Test NOT_CONTAINS condition operator."""
        condition = Condition("message", ConditionOperator.NOT_CONTAINS, "error")
        context = ExecutionContext()

        context.set("message", "All systems normal")
        assert condition.evaluate(context) is True

        context.set("message", "System error occurred")
        assert condition.evaluate(context) is False

    def test_condition_exists_operator(self):
        """Test EXISTS condition operator."""
        condition = Condition("api_key", ConditionOperator.EXISTS)
        context = ExecutionContext()

        context.set("api_key", "some-key")
        assert condition.evaluate(context) is True

        context2 = ExecutionContext()  # Fresh context
        assert condition.evaluate(context2) is False  # key doesn't exist

    def test_condition_not_exists_operator(self):
        """Test NOT_EXISTS condition operator."""
        condition = Condition("optional_param", ConditionOperator.NOT_EXISTS)
        context = ExecutionContext()

        # Key doesn't exist
        assert condition.evaluate(context) is True

        context.set("optional_param", "value")
        assert condition.evaluate(context) is False

    def test_condition_with_none_value(self):
        """Test condition evaluation when context value is None."""
        condition = Condition("test_key", ConditionOperator.EQUALS, "value")
        context = ExecutionContext()

        context.set("test_key", None)
        assert condition.evaluate(context) is False  # None should not equal "value"


class TestCommandBase:
    """Test the abstract Command base class functionality."""

    def test_command_initialization(self):
        """Test basic command initialization."""

        # Create a concrete command for testing
        class TestCommand(Command):
            def execute(self, context, client):
                return {"result": "test"}

        conditions = [Condition("ready", ConditionOperator.EQUALS, True)]
        cmd = TestCommand(
            name="test_cmd",
            description="Test command",
            conditions=conditions,
            rollback_enabled=True,
        )

        assert cmd.name == "test_cmd"
        assert cmd.description == "Test command"
        assert cmd.conditions == conditions
        assert cmd.rollback_enabled is True
        assert cmd.status == ExecutionStatus.PENDING
        assert cmd.execution_time is None
        assert cmd.result is None
        assert cmd.error is None

    def test_command_should_execute_no_conditions(self):
        """Test should_execute with no conditions (should always execute)."""

        class TestCommand(Command):
            def execute(self, context, client):
                return {"result": "test"}

        cmd = TestCommand("test")
        context = ExecutionContext()

        assert cmd.should_execute(context) is True

    def test_command_should_execute_with_conditions(self):
        """Test should_execute with conditions."""

        class TestCommand(Command):
            def execute(self, context, client):
                return {"result": "test"}

        conditions = [
            Condition("ready", ConditionOperator.EQUALS, True),
            Condition("count", ConditionOperator.GREATER_THAN, 0),
        ]
        cmd = TestCommand("test", conditions=conditions)
        context = ExecutionContext()

        # Not all conditions met
        context.set("ready", True)
        context.set("count", 0)
        assert cmd.should_execute(context) is False

        # All conditions met
        context.set("count", 5)
        assert cmd.should_execute(context) is True

    def test_command_rollback_not_enabled(self):
        """Test rollback when not enabled."""

        class TestCommand(Command):
            def execute(self, context, client):
                return {"result": "test"}

        cmd = TestCommand("test", rollback_enabled=False)
        context = ExecutionContext()
        client = Mock()

        # Should log warning but not fail
        cmd.rollback(context, client)
        assert cmd.rollback_enabled is False


class TestSendMessageCommand:
    """Test SendMessageCommand implementation."""

    def test_send_message_command_initialization(self):
        """Test SendMessageCommand initialization."""
        cmd = SendMessageCommand(
            name="custom_send",
            message_type_key="msg_type",
            to_key="recipient",
            content_key="msg_content",
            topic_key="msg_topic",
        )

        assert cmd.name == "custom_send"
        assert cmd.message_type_key == "msg_type"
        assert cmd.to_key == "recipient"
        assert cmd.content_key == "msg_content"
        assert cmd.topic_key == "msg_topic"
        assert cmd.rollback_enabled is False

    def test_send_message_command_execution_success(self):
        """Test successful message sending."""
        cmd = SendMessageCommand()
        context = ExecutionContext()
        client = Mock()

        # Set up context data
        context.set("message_type", "stream")
        context.set("to", "general")
        context.set("content", "Hello world!")
        context.set("topic", "test")

        # Mock successful API response
        client.send_message.return_value = {"result": "success", "id": 123}

        result = cmd.execute(context, client)

        assert result["result"] == "success"
        assert result["id"] == 123
        assert context.get("last_message_id") == 123

        client.send_message.assert_called_once_with(
            "stream", "general", "Hello world!", "test"
        )

    def test_send_message_command_missing_parameters(self):
        """Test send message with missing required parameters."""
        cmd = SendMessageCommand()
        context = ExecutionContext()
        client = Mock()

        # Missing required parameters
        context.set("message_type", "stream")
        # Missing 'to' and 'content'

        with pytest.raises(
            ValidationError, match="Missing required message parameters"
        ):
            cmd.execute(context, client)

    def test_send_message_command_api_failure(self):
        """Test send message when API returns failure."""
        cmd = SendMessageCommand()
        context = ExecutionContext()
        client = Mock()

        context.set("message_type", "stream")
        context.set("to", "general")
        context.set("content", "Hello!")
        context.set("topic", "test")

        # Mock API failure
        client.send_message.return_value = {
            "result": "error",
            "msg": "Stream not found",
        }

        with pytest.raises(
            ZulipMCPError, match="Failed to send message: Stream not found"
        ):
            cmd.execute(context, client)

    def test_send_message_command_topic_placeholder_replacement(self):
        """Test topic placeholder replacement with context data."""
        cmd = SendMessageCommand()
        context = ExecutionContext()
        client = Mock()

        context.set("message_type", "stream")
        context.set("to", "general")
        context.set("content", "Daily update")
        context.set("topic", "Daily standup - {date}")
        context.set("date", "2024-01-15")

        client.send_message.return_value = {"result": "success", "id": 456}

        cmd.execute(context, client)

        # Verify topic placeholder was replaced
        client.send_message.assert_called_once_with(
            "stream", "general", "Daily update", "Daily standup - 2024-01-15"
        )


class TestGetMessagesCommand:
    """Test GetMessagesCommand implementation."""

    def test_get_messages_command_from_stream(self):
        """Test getting messages from a specific stream."""
        cmd = GetMessagesCommand()
        context = ExecutionContext()
        client = Mock()

        # Set up context
        context.set("stream_name", "general")
        context.set("topic", "deployment")
        context.set("hours_back", 12)
        context.set("limit", 25)

        # Mock messages
        mock_message = ZulipMessage(
            id=1,
            sender_full_name="Alice",
            sender_email="alice@test.com",
            timestamp=123456,
            content="Deployment complete",
            type="stream",
            stream_name="general",
            subject="deployment",
        )

        client.get_messages_from_stream.return_value = [mock_message]

        result = cmd.execute(context, client)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["sender"] == "Alice"
        assert result[0]["content"] == "Deployment complete"
        assert context.get("messages") == result
        assert context.get("message_count") == 1

        client.get_messages_from_stream.assert_called_once_with(
            "general", topic="deployment", hours_back=12
        )

    def test_get_messages_command_all_messages(self):
        """Test getting messages from all streams."""
        cmd = GetMessagesCommand()
        context = ExecutionContext()
        client = Mock()

        # No stream_name specified
        context.set("limit", 30)

        mock_message = ZulipMessage(
            id=2,
            sender_full_name="Bob",
            sender_email="bob@test.com",
            timestamp=123457,
            content="General update",
            type="stream",
            stream_name="updates",
            subject="general",
        )

        client.get_messages.return_value = [mock_message]

        result = cmd.execute(context, client)

        assert len(result) == 1
        assert result[0]["id"] == 2

        client.get_messages.assert_called_once_with(num_before=30)

    def test_get_messages_command_default_parameters(self):
        """Test get messages with default hours_back and limit."""
        cmd = GetMessagesCommand()
        context = ExecutionContext()
        client = Mock()

        context.set("stream_name", "test")
        client.get_messages_from_stream.return_value = []

        cmd.execute(context, client)

        # Should use defaults: hours_back=24, limit=50
        client.get_messages_from_stream.assert_called_once_with(
            "test", topic=None, hours_back=24
        )


class TestAddReactionCommand:
    """Test AddReactionCommand implementation."""

    def test_add_reaction_command_success(self):
        """Test successful reaction addition."""
        cmd = AddReactionCommand()
        context = ExecutionContext()
        client = Mock()

        context.set("message_id", 123)
        context.set("emoji_name", "thumbs_up")

        client.add_reaction.return_value = {"result": "success"}

        result = cmd.execute(context, client)

        assert result["result"] == "success"
        assert "add_reaction_reaction" in context.rollback_data

        rollback_data = context.rollback_data["add_reaction_reaction"]
        assert rollback_data["message_id"] == 123
        assert rollback_data["emoji_name"] == "thumbs_up"

        client.add_reaction.assert_called_once_with(123, "thumbs_up")

    def test_add_reaction_command_missing_params(self):
        """Test add reaction with missing parameters."""
        cmd = AddReactionCommand()
        context = ExecutionContext()
        client = Mock()

        # Missing message_id
        context.set("emoji_name", "thumbs_up")

        with pytest.raises(ValidationError, match="Missing message_id or emoji_name"):
            cmd.execute(context, client)

    def test_add_reaction_command_rollback(self):
        """Test add reaction rollback functionality."""
        cmd = AddReactionCommand()
        context = ExecutionContext()
        client = Mock()

        # Set up rollback data
        context.rollback_data["add_reaction_reaction"] = {
            "message_id": 123,
            "emoji_name": "thumbs_up",
        }

        cmd._rollback_impl(context, client)

        # Rollback should log (actual removal would need API method)
        assert "add_reaction_reaction" in context.rollback_data


class TestProcessDataCommand:
    """Test ProcessDataCommand implementation."""

    def test_process_data_command_success(self):
        """Test successful data processing."""

        def double_processor(value):
            return value * 2

        cmd = ProcessDataCommand(
            name="double_data",
            processor=double_processor,
            input_key="input_value",
            output_key="output_value",
        )

        context = ExecutionContext()
        client = Mock()

        context.set("input_value", 21)

        result = cmd.execute(context, client)

        assert result == 42
        assert context.get("output_value") == 42

    def test_process_data_command_missing_input(self):
        """Test process data with missing input."""
        cmd = ProcessDataCommand(
            name="test_proc",
            processor=lambda x: x,
            input_key="missing_key",
            output_key="output",
        )

        context = ExecutionContext()
        client = Mock()

        with pytest.raises(ValidationError, match="No data found for key: missing_key"):
            cmd.execute(context, client)


class TestCommandChain:
    """Test CommandChain orchestration and execution."""

    def test_command_chain_initialization(self):
        """Test CommandChain initialization."""
        client = Mock()
        chain = CommandChain(
            "test_chain", client=client, stop_on_error=True, enable_rollback=True
        )

        assert chain.name == "test_chain"
        assert chain.client is client
        assert chain.commands == []
        assert chain.stop_on_error is True
        assert chain.enable_rollback is True
        assert chain.execution_context is None

    def test_command_chain_add_command(self):
        """Test adding commands to chain."""
        chain = CommandChain("test")
        cmd = SendMessageCommand()

        result = chain.add_command(cmd)

        assert result is chain  # Should return self for chaining
        assert len(chain.commands) == 1
        assert chain.commands[0] is cmd

    def test_command_chain_execute_success(self):
        """Test successful command chain execution."""
        client = Mock()
        chain = CommandChain("test", client=client)

        # Add mock command
        mock_cmd = Mock(spec=Command)
        mock_cmd.should_execute.return_value = True
        mock_cmd.execute.return_value = {"result": "success"}
        mock_cmd.name = "test_command"
        mock_cmd.status = ExecutionStatus.PENDING

        chain.add_command(mock_cmd)

        context = chain.execute()

        assert mock_cmd.status == ExecutionStatus.SUCCESS
        assert "test_command" in context.executed_commands
        assert not context.has_errors()

        mock_cmd.should_execute.assert_called_once()
        mock_cmd.execute.assert_called_once()

    def test_command_chain_execute_with_skipped_command(self):
        """Test chain execution with skipped command due to conditions."""
        client = Mock()
        chain = CommandChain("test", client=client)

        # Mock command that should be skipped
        mock_cmd = Mock(spec=Command)
        mock_cmd.should_execute.return_value = False
        mock_cmd.name = "skipped_command"
        mock_cmd.status = ExecutionStatus.PENDING

        chain.add_command(mock_cmd)

        context = chain.execute()

        assert mock_cmd.status == ExecutionStatus.SKIPPED
        assert "skipped_command" not in context.executed_commands

        mock_cmd.should_execute.assert_called_once()
        mock_cmd.execute.assert_not_called()

    def test_command_chain_execute_with_failure(self):
        """Test chain execution with command failure."""
        client = Mock()
        chain = CommandChain("test", client=client, stop_on_error=True)

        # Mock command that will fail
        mock_cmd = Mock(spec=Command)
        mock_cmd.should_execute.return_value = True
        mock_cmd.execute.side_effect = ZulipMCPError("Command failed")
        mock_cmd.name = "failing_command"
        mock_cmd.status = ExecutionStatus.PENDING

        chain.add_command(mock_cmd)

        with pytest.raises(
            ZulipMCPError, match="Chain execution failed at command failing_command"
        ):
            chain.execute()

        assert mock_cmd.status == ExecutionStatus.FAILED

    def test_command_chain_continue_on_error(self):
        """Test chain execution that continues on error."""
        client = Mock()
        chain = CommandChain("test", client=client, stop_on_error=False)

        # First command fails
        cmd1 = Mock(spec=Command)
        cmd1.should_execute.return_value = True
        cmd1.execute.side_effect = ValueError("First command failed")
        cmd1.name = "cmd1"
        cmd1.status = ExecutionStatus.PENDING

        # Second command succeeds
        cmd2 = Mock(spec=Command)
        cmd2.should_execute.return_value = True
        cmd2.execute.return_value = {"result": "success"}
        cmd2.name = "cmd2"
        cmd2.status = ExecutionStatus.PENDING

        chain.add_command(cmd1).add_command(cmd2)

        context = chain.execute()

        assert cmd1.status == ExecutionStatus.FAILED
        assert cmd2.status == ExecutionStatus.SUCCESS
        assert context.has_errors()
        assert len(context.warnings) > 0
        assert "cmd2" in context.executed_commands

    def test_command_chain_execution_summary(self):
        """Test getting execution summary."""
        client = Mock()
        chain = CommandChain("summary_test", client=client)

        cmd = Mock(spec=Command)
        cmd.should_execute.return_value = True
        cmd.execute.return_value = {"result": "success"}
        cmd.name = "test_cmd"
        cmd.status = ExecutionStatus.PENDING
        cmd.execution_time = 0.5
        cmd.error = None

        chain.add_command(cmd)
        chain.execute()

        summary = chain.get_execution_summary()

        assert summary["chain_name"] == "summary_test"
        assert summary["total_commands"] == 1
        assert summary["executed_commands"] == 1
        assert summary["errors"] == 0
        assert len(summary["commands"]) == 1
        assert summary["commands"][0]["name"] == "test_cmd"
        assert summary["commands"][0]["status"] == ExecutionStatus.SUCCESS.value


class TestChainBuilder:
    """Test ChainBuilder static methods for creating workflows."""

    def test_create_message_workflow(self):
        """Test creating a message workflow."""
        chain = ChainBuilder.create_message_workflow(
            stream_name="general",
            topic="test",
            content="Hello world!",
            add_reaction=True,
            emoji="rocket",
        )

        assert chain.name == "message_workflow"
        assert len(chain.commands) > 5  # Multiple setup commands + send + reaction

        # Check that we have a SendMessageCommand
        send_commands = [
            cmd for cmd in chain.commands if isinstance(cmd, SendMessageCommand)
        ]
        assert len(send_commands) == 1

        # Check that we have AddReactionCommand
        reaction_commands = [
            cmd for cmd in chain.commands if isinstance(cmd, AddReactionCommand)
        ]
        assert len(reaction_commands) == 1

    def test_create_message_workflow_no_reaction(self):
        """Test creating a message workflow without reaction."""
        chain = ChainBuilder.create_message_workflow(
            stream_name="general",
            topic="test",
            content="Hello world!",
            add_reaction=False,
        )

        # Should not have AddReactionCommand
        reaction_commands = [
            cmd for cmd in chain.commands if isinstance(cmd, AddReactionCommand)
        ]
        assert len(reaction_commands) == 0

    def test_create_digest_workflow(self):
        """Test creating a digest workflow."""
        chain = ChainBuilder.create_digest_workflow(
            stream_names=["general", "development"],
            hours_back=24,
            target_stream="digest",
            target_topic="Daily Summary",
        )

        assert chain.name == "digest_workflow"
        assert len(chain.commands) > 0

        # Should have commands for processing multiple streams
        process_commands = [
            cmd for cmd in chain.commands if isinstance(cmd, ProcessDataCommand)
        ]
        assert len(process_commands) > 2  # At least one for each stream


class TestComplexChainScenarios:
    """Test complex command chain scenarios and edge cases."""

    def test_chain_with_data_passing(self):
        """Test data passing between commands via context."""
        client = Mock()
        chain = CommandChain("data_test", client=client)

        # Command that produces data
        producer = ProcessDataCommand(
            name="producer",
            processor=lambda _: "produced_value",
            input_key="dummy",
            output_key="shared_data",
        )

        # Command that uses the produced data
        consumer = ProcessDataCommand(
            name="consumer",
            processor=lambda x: f"consumed_{x}",
            input_key="shared_data",
            output_key="final_result",
        )

        chain.add_command(producer).add_command(consumer)

        # Need to provide dummy input for producer
        context = chain.execute({"dummy": "input"})

        assert context.get("shared_data") == "produced_value"
        assert context.get("final_result") == "consumed_produced_value"

    def test_chain_rollback_functionality(self):
        """Test chain rollback when enabled."""
        client = Mock()
        chain = CommandChain(
            "rollback_test", client=client, enable_rollback=True, stop_on_error=True
        )

        # Successful command with rollback enabled
        success_cmd = Mock(spec=Command)
        success_cmd.should_execute.return_value = True
        success_cmd.execute.return_value = {"result": "success"}
        success_cmd.rollback_enabled = True
        success_cmd.name = "success_cmd"
        success_cmd.status = ExecutionStatus.PENDING

        # Failing command
        fail_cmd = Mock(spec=Command)
        fail_cmd.should_execute.return_value = True
        fail_cmd.execute.side_effect = ZulipMCPError("Command failed")
        fail_cmd.name = "fail_cmd"
        fail_cmd.status = ExecutionStatus.PENDING

        chain.add_command(success_cmd).add_command(fail_cmd)

        with pytest.raises(ZulipMCPError):
            chain.execute()

        # The successful command should have been rolled back
        assert success_cmd.rollback.call_count >= 1  # May be called multiple times
        assert success_cmd.status == ExecutionStatus.ROLLED_BACK

    def test_conditional_execution_in_chain(self):
        """Test commands with conditions in a chain."""
        client = Mock()
        chain = CommandChain("conditional_test", client=client)

        # Command that always executes
        always_cmd = Mock(spec=Command)
        always_cmd.should_execute.return_value = True
        always_cmd.execute.return_value = {"result": "always"}
        always_cmd.name = "always_cmd"
        always_cmd.status = ExecutionStatus.PENDING

        # Command with condition that will fail
        conditional_cmd = Mock(spec=Command)
        conditional_cmd.should_execute.return_value = False
        conditional_cmd.name = "conditional_cmd"
        conditional_cmd.status = ExecutionStatus.PENDING

        chain.add_command(always_cmd).add_command(conditional_cmd)

        context = chain.execute()

        assert always_cmd.status == ExecutionStatus.SUCCESS
        assert conditional_cmd.status == ExecutionStatus.SKIPPED
        assert "always_cmd" in context.executed_commands
        assert "conditional_cmd" not in context.executed_commands


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
