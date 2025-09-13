"""Common workflows and patterns for ZulipChat MCP command chains.

This module implements workflow patterns inspired by effective agent design:
- Prompt chaining and routing
- Orchestrator-worker patterns
- Evaluator-optimizer patterns

Reference: Building effective agents (https://www.anthropic.com/engineering/building-effective-agents)
"""

from typing import Any

from .engine import (
    AddReactionCommand,
    CommandChain,
    Condition,
    ConditionOperator,
    GetMessagesCommand,
    ProcessDataCommand,
    SendMessageCommand,
)


class ChainBuilder:
    """Builder pattern for creating common command chains and workflows."""

    @staticmethod
    def create_message_workflow(
        stream_name: str,
        topic: str,
        content: str,
        add_reaction: bool = True,
        emoji: str = "white_check_mark",
    ) -> CommandChain:
        """Create a workflow to send message and optionally add reaction.

        Args:
            stream_name: Target stream name
            topic: Message topic
            content: Message content
            add_reaction: Whether to add reaction after sending
            emoji: Emoji name for reaction

        Returns:
            Configured command chain
        """
        chain = CommandChain("message_workflow")

        # Set initial context
        chain.add_command(
            ProcessDataCommand(
                name="set_message_params",
                processor=lambda _: {
                    "message_type": "stream",
                    "to": stream_name,
                    "topic": topic,
                    "content": content,
                },
                input_key="dummy",
                output_key="message_params",
            )
        )

        # Copy params to individual keys
        def extract_params(params: dict[str, Any]) -> dict[str, Any]:
            return params

        chain.add_command(
            ProcessDataCommand(
                name="extract_message_type",
                processor=lambda params: params["message_type"],
                input_key="message_params",
                output_key="message_type",
            )
        )

        chain.add_command(
            ProcessDataCommand(
                name="extract_to",
                processor=lambda params: params["to"],
                input_key="message_params",
                output_key="to",
            )
        )

        chain.add_command(
            ProcessDataCommand(
                name="extract_topic",
                processor=lambda params: params["topic"],
                input_key="message_params",
                output_key="topic",
            )
        )

        chain.add_command(
            ProcessDataCommand(
                name="extract_content",
                processor=lambda params: params["content"],
                input_key="message_params",
                output_key="content",
            )
        )

        # Send message
        chain.add_command(SendMessageCommand())

        # Add reaction if requested
        if add_reaction:
            chain.add_command(
                ProcessDataCommand(
                    name="set_emoji",
                    processor=lambda _: emoji,
                    input_key="dummy",
                    output_key="emoji_name",
                )
            )

            chain.add_command(
                AddReactionCommand(
                    conditions=[Condition("last_message_id", ConditionOperator.EXISTS)]
                )
            )

        return chain

    @staticmethod
    def create_digest_workflow(
        stream_names: list[str],
        hours_back: int = 24,
        target_stream: str = "general",
        target_topic: str = "Daily Digest",
    ) -> CommandChain:
        """Create a workflow to generate and send message digest.

        Args:
            stream_names: Streams to include in digest
            hours_back: Hours to look back for messages
            target_stream: Stream to send digest to
            target_topic: Topic for digest message

        Returns:
            Configured command chain
        """
        chain = CommandChain("digest_workflow")

        # Process each stream
        for i, stream_name in enumerate(stream_names):
            # Set stream parameters
            def _set_params(
                _: Any, stream_name: str = stream_name, hours: int = hours_back
            ) -> dict[str, Any]:
                return {"stream_name": stream_name, "hours_back": hours}

            chain.add_command(
                ProcessDataCommand(
                    name=f"set_stream_{i}_params",
                    processor=_set_params,
                    input_key="dummy",
                    output_key=f"stream_{i}_params",
                )
            )

            # Extract stream name and hours_back
            chain.add_command(
                ProcessDataCommand(
                    name=f"extract_stream_{i}_name",
                    processor=lambda params: params["stream_name"],
                    input_key=f"stream_{i}_params",
                    output_key="stream_name",
                )
            )

            chain.add_command(
                ProcessDataCommand(
                    name=f"extract_hours_back_{i}",
                    processor=lambda params: params["hours_back"],
                    input_key=f"stream_{i}_params",
                    output_key="hours_back",
                )
            )

            # Get messages
            chain.add_command(GetMessagesCommand(name=f"get_messages_{i}"))

            # Store messages with stream-specific key
            chain.add_command(
                ProcessDataCommand(
                    name=f"store_messages_{i}",
                    processor=lambda msgs: msgs,
                    input_key="messages",
                    output_key=f"stream_{i}_messages",
                )
            )

        # Generate digest
        def create_digest(context_data: dict[str, Any]) -> str:
            digest_lines = [f"# Daily Digest - Last {hours_back} hours\n"]
            total_messages = 0

            for i, stream_name in enumerate(stream_names):
                messages = context_data.get(f"stream_{i}_messages", [])
                total_messages += len(messages)

                digest_lines.append(f"## #{stream_name} ({len(messages)} messages)")

                if messages:
                    # Show recent message senders
                    senders: dict[str, int] = {}
                    for msg in messages:
                        sender = msg["sender"]
                        senders[sender] = senders.get(sender, 0) + 1

                    top_senders = sorted(
                        senders.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                    if top_senders:
                        digest_lines.append("Top contributors:")
                        for sender, count in top_senders:
                            digest_lines.append(f"- {sender}: {count} messages")

                digest_lines.append("")

            digest_lines.append(
                f"**Total messages across all streams: {total_messages}**"
            )
            return "\n".join(digest_lines)

        chain.add_command(
            ProcessDataCommand(
                name="generate_digest",
                processor=create_digest,
                input_key="dummy",
                output_key="digest_content",
            )
        )

        # Set digest message parameters
        chain.add_command(
            ProcessDataCommand(
                name="set_digest_params",
                processor=lambda content: {
                    "message_type": "stream",
                    "to": target_stream,
                    "topic": target_topic,
                    "content": content,
                },
                input_key="digest_content",
                output_key="digest_params",
            )
        )

        # Extract digest parameters
        chain.add_command(
            ProcessDataCommand(
                name="extract_digest_type",
                processor=lambda params: params["message_type"],
                input_key="digest_params",
                output_key="message_type",
            )
        )

        chain.add_command(
            ProcessDataCommand(
                name="extract_digest_to",
                processor=lambda params: params["to"],
                input_key="digest_params",
                output_key="to",
            )
        )

        chain.add_command(
            ProcessDataCommand(
                name="extract_digest_topic",
                processor=lambda params: params["topic"],
                input_key="digest_params",
                output_key="topic",
            )
        )

        chain.add_command(
            ProcessDataCommand(
                name="extract_digest_content",
                processor=lambda params: params["content"],
                input_key="digest_params",
                output_key="content",
            )
        )

        # Send digest
        chain.add_command(SendMessageCommand(name="send_digest"))

        return chain

    @staticmethod
    def create_daily_summary_workflow(
        streams: list[str] | None = None,
        hours_back: int = 24,
    ) -> CommandChain:
        """Create a daily summary workflow (common pattern for agent integrations).

        This implements an orchestrator-worker pattern where:
        - Orchestrator coordinates data gathering from multiple streams
        - Workers process individual stream data
        - Evaluator consolidates results into a summary

        Args:
            streams: List of stream names to summarize (None for all subscribed)
            hours_back: Hours to look back for messages

        Returns:
            Configured daily summary command chain
        """
        if streams is None:
            streams = ["general", "development", "random"]

        return ChainBuilder.create_digest_workflow(
            stream_names=streams,
            hours_back=hours_back,
            target_stream="general",
            target_topic="Daily Summary",
        )

    @staticmethod
    def create_morning_briefing_workflow(
        priority_streams: list[str] | None = None,
    ) -> CommandChain:
        """Create a morning briefing workflow with priority stream focus.

        Implements evaluator-optimizer pattern:
        - Evaluates message importance across streams
        - Optimizes content for concise briefing format

        Args:
            priority_streams: High-priority streams for morning updates

        Returns:
            Configured morning briefing command chain
        """
        if priority_streams is None:
            priority_streams = ["general", "important", "announcements"]

        return ChainBuilder.create_digest_workflow(
            stream_names=priority_streams,
            hours_back=16,  # Since evening before
            target_stream="general",
            target_topic="Morning Briefing",
        )

    @staticmethod
    def create_catch_up_workflow(
        since_hours: int = 4,
        max_streams: int = 5,
    ) -> CommandChain:
        """Create a catch-up workflow for recent activity.

        Implements prompt chaining pattern:
        - Initial prompt gathers recent activity
        - Chained prompts filter and prioritize content
        - Final prompt formats for easy consumption

        Args:
            since_hours: Hours to look back
            max_streams: Maximum number of streams to include

        Returns:
            Configured catch-up command chain
        """
        # For now, use a subset approach
        streams = ["general", "development"][:max_streams]

        return ChainBuilder.create_digest_workflow(
            stream_names=streams,
            hours_back=since_hours,
            target_stream="general",
            target_topic="Quick Catch-up",
        )


# Factory functions for common workflow patterns
def create_simple_notification_chain(
    stream: str, topic: str, message: str
) -> CommandChain:
    """Create a simple notification chain."""
    return ChainBuilder.create_message_workflow(
        stream, topic, message, add_reaction=False
    )


def create_monitored_message_chain(
    stream: str, topic: str, message: str, reaction: str = "eyes"
) -> CommandChain:
    """Create a message chain with monitoring reaction."""
    return ChainBuilder.create_message_workflow(stream, topic, message, True, reaction)
