"""Batch operations for Zulip API with concurrent processing and error handling."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .async_client import AsyncZulipClient
from .config import ZulipConfig


class BatchOperation(Enum):
    """Supported batch operations."""

    SEND_MESSAGES = "send_messages"
    ADD_REACTIONS = "add_reactions"
    UPDATE_TOPICS = "update_topics"
    INVITE_USERS = "invite_users"


@dataclass
class BatchResult:
    """Result of batch operation execution."""

    successful: list[Any]
    failed: list[dict[str, Any]]
    total_time: float
    success_rate: float

    @classmethod
    def from_results(
        cls,
        successful: list[Any],
        failed: list[dict[str, Any]],
        total_time: float
    ) -> "BatchResult":
        """Create BatchResult from operation results."""
        total = len(successful) + len(failed)
        success_rate = len(successful) / total if total > 0 else 0.0

        return cls(
            successful=successful,
            failed=failed,
            total_time=total_time,
            success_rate=success_rate
        )


@dataclass
class MessageData:
    """Data structure for batch message sending."""

    message_type: str
    to: str | list[str]
    content: str
    topic: str | None = None


@dataclass
class InviteData:
    """Data structure for batch user invitations."""

    stream_name: str
    user_emails: list[str]


class BatchProcessor:
    """Processor for batch Zulip operations with concurrency control."""

    def __init__(
        self,
        config: ZulipConfig,
        chunk_size: int = 10,
        max_concurrent: int = 5,
        progress_callback: Callable[[int, int], None] | None = None
    ):
        """Initialize batch processor.
        
        Args:
            config: Zulip configuration
            chunk_size: Number of operations per chunk
            max_concurrent: Maximum concurrent operations
            progress_callback: Optional progress tracking callback
        """
        self.config = config
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
        self.progress_callback = progress_callback
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def batch_send_messages(self, messages: list[MessageData]) -> BatchResult:
        """Send multiple messages concurrently.
        
        Args:
            messages: List of message data to send
            
        Returns:
            Batch operation result
        """
        start_time = time.time()
        successful = []
        failed = []

        async def send_single_message(client: AsyncZulipClient, msg_data: MessageData, index: int) -> dict[str, Any]:
            async with self._semaphore:
                result = await client.send_message_async(
                    message_type=msg_data.message_type,
                    to=msg_data.to,
                    content=msg_data.content,
                    topic=msg_data.topic
                )
                return result

        async with AsyncZulipClient(self.config) as client:
            # Process all messages concurrently with proper exception handling
            tasks = [
                send_single_message(client, msg_data, i)
                for i, msg_data in enumerate(messages)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions that occurred
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed.append({
                        "index": i,
                        "message_data": messages[i],
                        "error": str(result),
                        "error_type": type(result).__name__
                    })
                else:
                    successful.append(result)

                if self.progress_callback:
                    self.progress_callback(len(successful) + len(failed), len(messages))

        total_time = time.time() - start_time
        return BatchResult.from_results(successful, failed, total_time)

    async def batch_add_reactions(
        self,
        message_ids: list[int],
        emoji: str
    ) -> BatchResult:
        """Add the same reaction to multiple messages concurrently.
        
        Args:
            message_ids: List of message IDs
            emoji: Emoji name to add
            
        Returns:
            Batch operation result
        """
        start_time = time.time()
        successful = []
        failed = []

        async def add_single_reaction(client: AsyncZulipClient, message_id: int, index: int) -> None:
            async with self._semaphore:
                try:
                    result = await client.add_reaction_async(message_id, emoji)
                    successful.append({
                        "message_id": message_id,
                        "emoji": emoji,
                        "result": result
                    })

                    if self.progress_callback:
                        self.progress_callback(len(successful) + len(failed), len(message_ids))

                except Exception as e:
                    failed.append({
                        "index": index,
                        "message_id": message_id,
                        "emoji": emoji,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })

                    if self.progress_callback:
                        self.progress_callback(len(successful) + len(failed), len(message_ids))

        async with AsyncZulipClient(self.config) as client:
            # Process reactions in chunks
            for i in range(0, len(message_ids), self.chunk_size):
                chunk = message_ids[i:i + self.chunk_size]
                tasks = [
                    add_single_reaction(client, message_id, i + j)
                    for j, message_id in enumerate(chunk)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        return BatchResult.from_results(successful, failed, total_time)

    async def batch_update_topics(
        self,
        message_ids: list[int],
        new_topic: str
    ) -> BatchResult:
        """Move multiple messages to a new topic concurrently.
        
        Args:
            message_ids: List of message IDs to move
            new_topic: New topic name
            
        Returns:
            Batch operation result
        """
        start_time = time.time()
        successful = []
        failed = []

        async def update_single_topic(client: AsyncZulipClient, message_id: int, index: int) -> None:
            async with self._semaphore:
                try:
                    result = await client.edit_message_async(
                        message_id=message_id,
                        topic=new_topic
                    )
                    successful.append({
                        "message_id": message_id,
                        "new_topic": new_topic,
                        "result": result
                    })

                    if self.progress_callback:
                        self.progress_callback(len(successful) + len(failed), len(message_ids))

                except Exception as e:
                    failed.append({
                        "index": index,
                        "message_id": message_id,
                        "new_topic": new_topic,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })

                    if self.progress_callback:
                        self.progress_callback(len(successful) + len(failed), len(message_ids))

        async with AsyncZulipClient(self.config) as client:
            # Process topic updates in chunks
            for i in range(0, len(message_ids), self.chunk_size):
                chunk = message_ids[i:i + self.chunk_size]
                tasks = [
                    update_single_topic(client, message_id, i + j)
                    for j, message_id in enumerate(chunk)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        return BatchResult.from_results(successful, failed, total_time)

    async def batch_invite_users(
        self,
        stream_names: list[str],
        user_emails: list[str]
    ) -> BatchResult:
        """Bulk invite users to multiple streams.
        
        Args:
            stream_names: List of stream names
            user_emails: List of user email addresses
            
        Returns:
            Batch operation result
        """
        start_time = time.time()
        successful = []
        failed = []

        # Create invitation data for all combinations
        invite_data = []
        for stream_name in stream_names:
            for user_email in user_emails:
                invite_data.append(InviteData(stream_name, [user_email]))

        async def invite_single_user(client: AsyncZulipClient, invite: InviteData, index: int) -> None:
            async with self._semaphore:
                try:
                    # Use the HTTP client directly for stream subscription
                    http_client = client._ensure_client()

                    # Get stream ID first
                    streams_response = await http_client.get(f"{client.base_url}/streams")
                    streams_response.raise_for_status()
                    streams_data = streams_response.json()

                    stream_id = None
                    if streams_data["result"] == "success":
                        for stream in streams_data["streams"]:
                            if stream["name"] == invite.stream_name:
                                stream_id = stream["stream_id"]
                                break

                    if not stream_id:
                        raise ValueError(f"Stream '{invite.stream_name}' not found")

                    # Add user to stream
                    subscription_data = {
                        "subscriptions": f'[{{"name": "{invite.stream_name}"}}]',
                        "principals": f'{invite.user_emails}'
                    }

                    result_response = await http_client.post(
                        f"{client.base_url}/users/me/subscriptions",
                        data=subscription_data
                    )
                    result_response.raise_for_status()
                    result = result_response.json()

                    successful.append({
                        "stream_name": invite.stream_name,
                        "user_emails": invite.user_emails,
                        "result": result
                    })

                    if self.progress_callback:
                        self.progress_callback(len(successful) + len(failed), len(invite_data))

                except Exception as e:
                    failed.append({
                        "index": index,
                        "stream_name": invite.stream_name,
                        "user_emails": invite.user_emails,
                        "error": str(e),
                        "error_type": type(e).__name__
                    })

                    if self.progress_callback:
                        self.progress_callback(len(successful) + len(failed), len(invite_data))

        async with AsyncZulipClient(self.config) as client:
            # Process invitations in chunks
            for i in range(0, len(invite_data), self.chunk_size):
                chunk = invite_data[i:i + self.chunk_size]
                tasks = [
                    invite_single_user(client, invite, i + j)
                    for j, invite in enumerate(chunk)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        return BatchResult.from_results(successful, failed, total_time)

    async def execute_batch_operation(
        self,
        operation: BatchOperation,
        **kwargs
    ) -> BatchResult:
        """Execute a batch operation by type.
        
        Args:
            operation: Type of batch operation to execute
            **kwargs: Operation-specific arguments
            
        Returns:
            Batch operation result
            
        Raises:
            ValueError: If operation type is not supported or missing required arguments
        """
        if operation == BatchOperation.SEND_MESSAGES:
            if "messages" not in kwargs:
                raise ValueError("Missing 'messages' argument for SEND_MESSAGES operation")
            return await self.batch_send_messages(kwargs["messages"])

        elif operation == BatchOperation.ADD_REACTIONS:
            if "message_ids" not in kwargs or "emoji" not in kwargs:
                raise ValueError("Missing 'message_ids' or 'emoji' argument for ADD_REACTIONS operation")
            return await self.batch_add_reactions(kwargs["message_ids"], kwargs["emoji"])

        elif operation == BatchOperation.UPDATE_TOPICS:
            if "message_ids" not in kwargs or "new_topic" not in kwargs:
                raise ValueError("Missing 'message_ids' or 'new_topic' argument for UPDATE_TOPICS operation")
            return await self.batch_update_topics(kwargs["message_ids"], kwargs["new_topic"])

        elif operation == BatchOperation.INVITE_USERS:
            if "stream_names" not in kwargs or "user_emails" not in kwargs:
                raise ValueError("Missing 'stream_names' or 'user_emails' argument for INVITE_USERS operation")
            return await self.batch_invite_users(kwargs["stream_names"], kwargs["user_emails"])

        else:
            raise ValueError(f"Unsupported batch operation: {operation}")


# Convenience functions for direct usage
async def send_messages_batch(
    config: ZulipConfig,
    messages: list[MessageData],
    chunk_size: int = 10,
    max_concurrent: int = 5,
    progress_callback: Callable[[int, int], None] | None = None
) -> BatchResult:
    """Send multiple messages in batch.
    
    Args:
        config: Zulip configuration
        messages: List of message data
        chunk_size: Chunk size for processing
        max_concurrent: Maximum concurrent operations
        progress_callback: Progress tracking callback
        
    Returns:
        Batch operation result
    """
    processor = BatchProcessor(config, chunk_size, max_concurrent, progress_callback)
    return await processor.batch_send_messages(messages)


async def add_reactions_batch(
    config: ZulipConfig,
    message_ids: list[int],
    emoji: str,
    chunk_size: int = 10,
    max_concurrent: int = 5,
    progress_callback: Callable[[int, int], None] | None = None
) -> BatchResult:
    """Add reactions to multiple messages in batch.
    
    Args:
        config: Zulip configuration
        message_ids: List of message IDs
        emoji: Emoji name
        chunk_size: Chunk size for processing
        max_concurrent: Maximum concurrent operations
        progress_callback: Progress tracking callback
        
    Returns:
        Batch operation result
    """
    processor = BatchProcessor(config, chunk_size, max_concurrent, progress_callback)
    return await processor.batch_add_reactions(message_ids, emoji)


async def update_topics_batch(
    config: ZulipConfig,
    message_ids: list[int],
    new_topic: str,
    chunk_size: int = 10,
    max_concurrent: int = 5,
    progress_callback: Callable[[int, int], None] | None = None
) -> BatchResult:
    """Update topics for multiple messages in batch.
    
    Args:
        config: Zulip configuration
        message_ids: List of message IDs
        new_topic: New topic name
        chunk_size: Chunk size for processing
        max_concurrent: Maximum concurrent operations
        progress_callback: Progress tracking callback
        
    Returns:
        Batch operation result
    """
    processor = BatchProcessor(config, chunk_size, max_concurrent, progress_callback)
    return await processor.batch_update_topics(message_ids, new_topic)


async def invite_users_batch(
    config: ZulipConfig,
    stream_names: list[str],
    user_emails: list[str],
    chunk_size: int = 10,
    max_concurrent: int = 5,
    progress_callback: Callable[[int, int], None] | None = None
) -> BatchResult:
    """Invite users to multiple streams in batch.
    
    Args:
        config: Zulip configuration
        stream_names: List of stream names
        user_emails: List of user emails
        chunk_size: Chunk size for processing
        max_concurrent: Maximum concurrent operations
        progress_callback: Progress tracking callback
        
    Returns:
        Batch operation result
    """
    processor = BatchProcessor(config, chunk_size, max_concurrent, progress_callback)
    return await processor.batch_invite_users(stream_names, user_emails)
