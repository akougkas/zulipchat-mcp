"""Command chain system for ZulipChat MCP with workflow automation support.

This module provides a flexible command chain system that allows chaining
Zulip API operations together with context passing, error handling, and
conditional execution support.

Per Zulip API documentation: https://zulip.com/api/
Supports chaining operations across messages, streams, users, and real-time events.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ..client import ZulipClientWrapper
from ..exceptions import (
    ValidationError,
    ZulipMCPError,
)

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Command execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class ConditionOperator(Enum):
    """Condition operators for conditional execution."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


@dataclass
class ExecutionContext:
    """Context passed between commands in a chain."""

    # Core context data
    data: dict[str, Any] = field(default_factory=dict)

    # Execution metadata
    start_time: datetime = field(default_factory=datetime.now)
    chain_id: str = ""
    current_command: str | None = None

    # State tracking
    executed_commands: list[str] = field(default_factory=list)
    rollback_data: dict[str, Any] = field(default_factory=dict)

    # Error tracking
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context data."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context data."""
        self.data[key] = value

    def add_error(self, command: str, error: Exception) -> None:
        """Add error to context."""
        self.errors.append(
            {
                "command": command,
                "error": str(error),
                "type": type(error).__name__,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def add_warning(self, message: str) -> None:
        """Add warning to context."""
        self.warnings.append(f"{datetime.now().isoformat()}: {message}")

    def has_errors(self) -> bool:
        """Check if context has any errors."""
        return len(self.errors) > 0


@dataclass
class Condition:
    """Condition for conditional command execution."""

    key: str  # Context key to check
    operator: ConditionOperator
    value: Any = None

    def evaluate(self, context: ExecutionContext) -> bool:
        """Evaluate condition against context."""
        context_value = context.get(self.key)

        if self.operator == ConditionOperator.EXISTS:
            return context_value is not None
        elif self.operator == ConditionOperator.NOT_EXISTS:
            return context_value is None
        elif context_value is None:
            return False

        if self.operator == ConditionOperator.EQUALS:
            return context_value == self.value
        elif self.operator == ConditionOperator.NOT_EQUALS:
            return context_value != self.value
        elif self.operator == ConditionOperator.GREATER_THAN:
            return context_value > self.value
        elif self.operator == ConditionOperator.LESS_THAN:
            return context_value < self.value
        elif self.operator == ConditionOperator.CONTAINS:
            return self.value in context_value
        elif self.operator == ConditionOperator.NOT_CONTAINS:
            return self.value not in context_value

        return False


class Command(ABC):
    """Abstract base class for commands in a chain."""

    def __init__(
        self,
        name: str,
        description: str = "",
        conditions: list[Condition] | None = None,
        rollback_enabled: bool = False,
    ):
        """Initialize command.

        Args:
            name: Command name/identifier
            description: Command description
            conditions: List of conditions that must be met to execute
            rollback_enabled: Whether this command supports rollback
        """
        self.name = name
        self.description = description
        self.conditions = conditions or []
        self.rollback_enabled = rollback_enabled
        self.status = ExecutionStatus.PENDING
        self.execution_time: float | None = None
        self.result: Any = None
        self.error: Exception | None = None

    def should_execute(self, context: ExecutionContext) -> bool:
        """Check if command should execute based on conditions."""
        if not self.conditions:
            return True

        # All conditions must be met (AND logic)
        return all(condition.evaluate(context) for condition in self.conditions)

    @abstractmethod
    def execute(self, context: ExecutionContext, client: ZulipClientWrapper) -> Any:
        """Execute the command.

        Args:
            context: Execution context with shared data
            client: Zulip client wrapper

        Returns:
            Command result

        Raises:
            ZulipMCPError: On execution failure
        """
        pass

    def rollback(self, context: ExecutionContext, client: ZulipClientWrapper) -> None:
        """Rollback command effects if supported.

        Args:
            context: Execution context
            client: Zulip client wrapper
        """
        if not self.rollback_enabled:
            logger.warning(f"Command {self.name} does not support rollback")
            return

        logger.info(f"Rolling back command: {self.name}")
        self._rollback_impl(context, client)

    @abstractmethod
    def _rollback_impl(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> None:
        """Implementation of rollback logic. Override in subclasses."""
        ...


class SendMessageCommand(Command):
    """Command to send a message to Zulip stream or user."""

    def __init__(
        self,
        name: str = "send_message",
        message_type_key: str = "message_type",
        to_key: str = "to",
        content_key: str = "content",
        topic_key: str = "topic",
        **kwargs,
    ):
        """Initialize send message command.

        Args:
            name: Command name
            message_type_key: Context key for message type
            to_key: Context key for recipient
            content_key: Context key for message content
            topic_key: Context key for topic (stream messages)
        """
        super().__init__(
            name, "Send message to Zulip", rollback_enabled=False, **kwargs
        )
        self.message_type_key = message_type_key
        self.to_key = to_key
        self.content_key = content_key
        self.topic_key = topic_key

    def execute(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> dict[str, Any]:
        """Send message via Zulip API."""
        try:
            message_type = context.get(self.message_type_key)
            to = context.get(self.to_key)
            content = context.get(self.content_key)
            topic = context.get(self.topic_key)

            if not all([message_type, to, content]):
                raise ValidationError("Missing required message parameters")

            # Replace placeholders in topic with dynamic values
            if topic:
                topic = topic.format(**context.data)

            result = client.send_message(message_type, to, content, topic)

            if result.get("result") == "success":
                # Store message ID for potential future operations
                context.set("last_message_id", result.get("id"))
                return result
            else:
                raise ZulipMCPError(f"Failed to send message: {result.get('msg')}")

        except Exception as e:
            logger.error(f"Send message command failed: {e}")
            raise


class GetMessagesCommand(Command):
    """Command to retrieve messages from Zulip."""

    def __init__(
        self,
        name: str = "get_messages",
        stream_name_key: str = "stream_name",
        topic_key: str = "topic",
        hours_back_key: str = "hours_back",
        limit_key: str = "limit",
        **kwargs,
    ):
        """Initialize get messages command."""
        super().__init__(name, "Get messages from Zulip", **kwargs)
        self.stream_name_key = stream_name_key
        self.topic_key = topic_key
        self.hours_back_key = hours_back_key
        self.limit_key = limit_key

    def execute(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> list[dict[str, Any]]:
        """Retrieve messages via Zulip API."""
        try:
            stream_name = context.get(self.stream_name_key)
            topic = context.get(self.topic_key)
            hours_back = context.get(self.hours_back_key, 24)
            limit = context.get(self.limit_key, 50)

            if stream_name:
                messages = client.get_messages_from_stream(
                    stream_name, topic=topic, hours_back=hours_back
                )[:limit]
            else:
                messages = client.get_messages(num_before=limit)

            # Convert to dict format and store in context
            message_dicts = [
                {
                    "id": msg.id,
                    "sender": msg.sender_full_name,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "stream": msg.stream_name,
                    "topic": msg.subject,
                }
                for msg in messages
            ]

            context.set("messages", message_dicts)
            context.set("message_count", len(message_dicts))

            return message_dicts

        except Exception as e:
            logger.error(f"Get messages command failed: {e}")
            raise


class AddReactionCommand(Command):
    """Command to add emoji reaction to a message."""

    def __init__(
        self,
        name: str = "add_reaction",
        message_id_key: str = "message_id",
        emoji_name_key: str = "emoji_name",
        **kwargs,
    ):
        """Initialize add reaction command."""
        super().__init__(
            name, "Add reaction to message", rollback_enabled=True, **kwargs
        )
        self.message_id_key = message_id_key
        self.emoji_name_key = emoji_name_key

    def execute(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> dict[str, Any]:
        """Add reaction to message."""
        try:
            message_id = context.get(self.message_id_key)
            emoji_name = context.get(self.emoji_name_key)

            if not message_id or not emoji_name:
                raise ValidationError("Missing message_id or emoji_name")

            result = client.add_reaction(message_id, emoji_name)

            if result.get("result") == "success":
                # Store for potential rollback
                context.rollback_data[f"{self.name}_reaction"] = {
                    "message_id": message_id,
                    "emoji_name": emoji_name,
                }
                return result
            else:
                raise ZulipMCPError(f"Failed to add reaction: {result.get('msg')}")

        except Exception as e:
            logger.error(f"Add reaction command failed: {e}")
            raise

    def _rollback_impl(
        self, context: ExecutionContext, client: ZulipClientWrapper
    ) -> None:
        """Remove the added reaction."""
        rollback_key = f"{self.name}_reaction"
        if rollback_key in context.rollback_data:
            reaction_data = context.rollback_data[rollback_key]
            try:
                # Note: Zulip API would need a remove_reaction method for full rollback
                logger.info(
                    f"Would remove reaction {reaction_data['emoji_name']} "
                    f"from message {reaction_data['message_id']}"
                )
            except Exception as e:
                logger.error(f"Failed to rollback reaction: {e}")


class ProcessDataCommand(Command):
    """Generic command to process data in context."""

    def __init__(
        self,
        name: str,
        processor: Callable[[Any], Any],
        input_key: str,
        output_key: str,
        **kwargs,
    ):
        """Initialize data processing command.

        Args:
            name: Command name
            processor: Function to process the data
            input_key: Context key for input data
            output_key: Context key to store output
        """
        super().__init__(name, f"Process data: {input_key} -> {output_key}", **kwargs)
        self.processor = processor
        self.input_key = input_key
        self.output_key = output_key

    def execute(self, context: ExecutionContext, client: ZulipClientWrapper) -> Any:
        """Process data using the provided processor function."""
        try:
            input_data = context.get(self.input_key)
            if input_data is None:
                raise ValidationError(f"No data found for key: {self.input_key}")

            result = self.processor(input_data)
            context.set(self.output_key, result)

            return result

        except Exception as e:
            logger.error(f"Process data command failed: {e}")
            raise


class CommandChain:
    """Command chain executor with error handling and rollback support.

    Per Zulip API documentation, supports chaining operations across:
    - Message operations (send, edit, react, get)
    - Stream management (subscribe, create, update)
    - User operations (get, update, status)
    - Real-time events (register, retrieve)
    """

    def __init__(
        self,
        name: str,
        client: ZulipClientWrapper | None = None,
        stop_on_error: bool = True,
        enable_rollback: bool = False,
    ):
        """Initialize command chain.

        Args:
            name: Chain name/identifier
            client: Zulip client wrapper
            stop_on_error: Whether to stop execution on first error
            enable_rollback: Whether to rollback on failures
        """
        self.name = name
        self.client = client
        self.commands: list[Command] = []
        self.stop_on_error = stop_on_error
        self.enable_rollback = enable_rollback
        self.execution_context: ExecutionContext | None = None

    def add_command(self, command: Command) -> "CommandChain":
        """Add command to the chain.

        Args:
            command: Command to add

        Returns:
            Self for method chaining
        """
        self.commands.append(command)
        return self

    def execute(
        self,
        initial_context: dict[str, Any] | None = None,
        client: ZulipClientWrapper | None = None,
    ) -> ExecutionContext:
        """Execute the command chain.

        Args:
            initial_context: Initial context data
            client: Zulip client wrapper (overrides instance client)

        Returns:
            Final execution context

        Raises:
            ZulipMCPError: On chain execution failure
        """
        # Initialize execution context
        context = ExecutionContext(
            data=initial_context or {},
            chain_id=f"{self.name}_{datetime.now().isoformat()}",
            start_time=datetime.now(),
        )
        self.execution_context = context

        # Use provided client or instance client
        exec_client = client or self.client
        if not exec_client:
            raise ZulipMCPError("No Zulip client provided for execution")

        logger.info(f"Starting command chain execution: {self.name}")

        executed_commands = []

        try:
            for command in self.commands:
                context.current_command = command.name

                # Check if command should be executed
                if not command.should_execute(context):
                    logger.info(f"Skipping command {command.name} (conditions not met)")
                    command.status = ExecutionStatus.SKIPPED
                    continue

                # Execute command
                logger.info(f"Executing command: {command.name}")
                command.status = ExecutionStatus.RUNNING
                start_time = datetime.now()

                try:
                    result = command.execute(context, exec_client)
                    command.result = result
                    command.status = ExecutionStatus.SUCCESS
                    command.execution_time = (
                        datetime.now() - start_time
                    ).total_seconds()

                    context.executed_commands.append(command.name)
                    executed_commands.append(command)

                    logger.info(f"Command {command.name} completed successfully")

                except Exception as e:
                    command.error = e
                    command.status = ExecutionStatus.FAILED
                    command.execution_time = (
                        datetime.now() - start_time
                    ).total_seconds()

                    context.add_error(command.name, e)
                    logger.error(f"Command {command.name} failed: {e}")

                    # Handle error based on chain configuration
                    if self.stop_on_error:
                        if self.enable_rollback:
                            self._rollback_chain(
                                executed_commands, context, exec_client
                            )
                        raise ZulipMCPError(
                            f"Chain execution failed at command {command.name}: {e}"
                        ) from None

            # Check if any commands failed (for continue-on-error mode)
            if context.has_errors() and not self.stop_on_error:
                context.add_warning(
                    f"Chain completed with {len(context.errors)} errors"
                )

            logger.info(f"Command chain {self.name} completed")

        except Exception as e:
            logger.error(f"Chain execution failed: {e}")
            if self.enable_rollback and executed_commands:
                self._rollback_chain(executed_commands, context, exec_client)
            raise

        return context

    def _rollback_chain(
        self,
        executed_commands: list[Command],
        context: ExecutionContext,
        client: ZulipClientWrapper,
    ) -> None:
        """Rollback executed commands in reverse order."""
        logger.info("Starting chain rollback")

        # Rollback in reverse order
        for command in reversed(executed_commands):
            if command.rollback_enabled:
                try:
                    command.rollback(context, client)
                    command.status = ExecutionStatus.ROLLED_BACK
                except Exception as e:
                    logger.error(f"Failed to rollback command {command.name}: {e}")
                    context.add_error(f"rollback_{command.name}", e)

    def get_execution_summary(self) -> dict[str, Any]:
        """Get execution summary with command statuses."""
        if not self.execution_context:
            return {"status": "not_executed"}

        return {
            "chain_name": self.name,
            "chain_id": self.execution_context.chain_id,
            "start_time": self.execution_context.start_time.isoformat(),
            "total_commands": len(self.commands),
            "executed_commands": len(self.execution_context.executed_commands),
            "errors": len(self.execution_context.errors),
            "warnings": len(self.execution_context.warnings),
            "commands": [
                {
                    "name": cmd.name,
                    "status": cmd.status.value,
                    "execution_time": cmd.execution_time,
                    "error": str(cmd.error) if cmd.error else None,
                }
                for cmd in self.commands
            ],
            "context_keys": list(self.execution_context.data.keys()),
        }
