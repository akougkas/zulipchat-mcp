"""Streamlined tests for batch operations module.

The batch_ops.py module provides concurrent processing of Zulip operations
with 175 lines including BatchProcessor, data classes, and async operations.

Focused on key functionality to maximize coverage:
- BatchResult creation and calculations
- BatchProcessor initialization and core methods
- MessageData and InviteData structures
- Concurrent processing with semaphore limits
- Progress tracking callbacks
- Error aggregation and reporting
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from src.zulipchat_mcp.batch_ops import (
    BatchOperation,
    BatchResult,
    MessageData,
    InviteData,
    BatchProcessor
)
from src.zulipchat_mcp.config import ZulipConfig


@pytest.fixture
def sample_config():
    """Sample Zulip configuration."""
    return ZulipConfig(
        email="test@example.com",
        api_key="test-api-key",
        site="https://test.zulipchat.com"
    )


class TestBatchResult:
    """Test BatchResult data class and calculations."""
    
    def test_batch_result_initialization(self):
        """Test BatchResult direct initialization."""
        successful = [{"id": 1}, {"id": 2}]
        failed = [{"error": "Failed", "item": "test"}]
        
        result = BatchResult(
            successful=successful,
            failed=failed,
            total_time=2.5,
            success_rate=0.67
        )
        
        assert result.successful == successful
        assert result.failed == failed
        assert result.total_time == 2.5
        assert result.success_rate == 0.67
    
    def test_batch_result_from_results_success_case(self):
        """Test BatchResult creation with mostly successful operations."""
        successful = [{"id": 1}, {"id": 2}, {"id": 3}]
        failed = [{"error": "Failed", "item": "test"}]
        
        result = BatchResult.from_results(successful, failed, 1.5)
        
        assert result.successful == successful
        assert result.failed == failed
        assert result.total_time == 1.5
        assert result.success_rate == 0.75  # 3 successful out of 4 total
    
    def test_batch_result_from_results_all_failed(self):
        """Test BatchResult creation with all failures."""
        successful = []
        failed = [{"error": "Failed 1"}, {"error": "Failed 2"}]
        
        result = BatchResult.from_results(successful, failed, 0.5)
        
        assert result.success_rate == 0.0
    
    def test_batch_result_from_results_empty(self):
        """Test BatchResult creation with empty results."""
        result = BatchResult.from_results([], [], 0.0)
        
        assert result.success_rate == 0.0  # Avoid division by zero


class TestDataStructures:
    """Test data structures for batch operations."""
    
    def test_message_data_stream_message(self):
        """Test MessageData for stream messages."""
        msg_data = MessageData(
            message_type="stream",
            to="general",
            content="Hello everyone!",
            topic="announcements"
        )
        
        assert msg_data.message_type == "stream"
        assert msg_data.to == "general"
        assert msg_data.content == "Hello everyone!"
        assert msg_data.topic == "announcements"
    
    def test_message_data_private_message(self):
        """Test MessageData for private messages."""
        msg_data = MessageData(
            message_type="private",
            to=["user1@example.com", "user2@example.com"],
            content="Private group message"
        )
        
        assert msg_data.message_type == "private"
        assert msg_data.to == ["user1@example.com", "user2@example.com"]
        assert msg_data.topic is None
    
    def test_invite_data(self):
        """Test InviteData structure."""
        invite_data = InviteData(
            stream_name="team-updates",
            user_emails=["new1@example.com", "new2@example.com", "new3@example.com"]
        )
        
        assert invite_data.stream_name == "team-updates"
        assert len(invite_data.user_emails) == 3
        assert "new1@example.com" in invite_data.user_emails


class TestBatchProcessor:
    """Test BatchProcessor initialization and core functionality."""
    
    def test_batch_processor_initialization(self, sample_config):
        """Test BatchProcessor initialization with default values."""
        processor = BatchProcessor(sample_config)
        
        assert processor.config == sample_config
        assert processor.chunk_size == 10  # Default
        assert processor.max_concurrent == 5  # Default
        assert processor.progress_callback is None
        assert processor._semaphore._value == 5
    
    def test_batch_processor_custom_parameters(self, sample_config):
        """Test BatchProcessor with custom parameters."""
        progress_callback = Mock()
        
        processor = BatchProcessor(
            config=sample_config,
            chunk_size=20,
            max_concurrent=10,
            progress_callback=progress_callback
        )
        
        assert processor.chunk_size == 20
        assert processor.max_concurrent == 10
        assert processor.progress_callback is progress_callback
        assert processor._semaphore._value == 10
    
    @pytest.mark.asyncio
    async def test_batch_send_messages_success(self, sample_config):
        """Test successful batch message sending."""
        processor = BatchProcessor(sample_config)
        
        messages = [
            MessageData("stream", "general", "Message 1", "topic1"),
            MessageData("stream", "general", "Message 2", "topic2"),
        ]
        
        # Mock the async client and its methods
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"result": "success", "id": 123}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 1.5]  # Start and end time
                
                result = await processor.batch_send_messages(messages)
        
        assert isinstance(result, BatchResult)
        assert len(result.successful) == 2
        assert len(result.failed) == 0
        assert result.success_rate == 1.0
        assert result.total_time == 1.5
    
    @pytest.mark.asyncio
    async def test_batch_send_messages_with_failures(self, sample_config):
        """Test batch message sending with some failures."""
        processor = BatchProcessor(sample_config)
        
        messages = [
            MessageData("stream", "general", "Success message", "topic1"),
            MessageData("stream", "invalid", "Fail message", "topic2"),
        ]
        
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            # First call succeeds, second fails
            mock_client.send_message_async.side_effect = [
                {"result": "success", "id": 123},
                Exception("Stream not found")
            ]
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 2.0]
                
                result = await processor.batch_send_messages(messages)
        
        assert len(result.successful) == 1
        assert len(result.failed) == 1
        assert result.success_rate == 0.5
        assert "Stream not found" in result.failed[0]["error"]
    
    @pytest.mark.asyncio
    async def test_batch_add_reactions_success(self, sample_config):
        """Test successful batch reaction adding."""
        processor = BatchProcessor(sample_config)
        
        message_ids = [123, 124, 125]
        emoji = "thumbs_up"
        
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.add_reaction_async.return_value = {"result": "success"}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 0.8]
                
                result = await processor.batch_add_reactions(message_ids, emoji)
        
        assert len(result.successful) == 3
        assert len(result.failed) == 0
        assert result.success_rate == 1.0
    
    @pytest.mark.asyncio
    async def test_progress_callback_tracking(self, sample_config):
        """Test that progress callback is called during processing."""
        progress_callback = Mock()
        processor = BatchProcessor(
            sample_config,
            progress_callback=progress_callback
        )
        
        messages = [MessageData("stream", "general", f"Message {i}", "test") for i in range(3)]
        
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"result": "success", "id": 123}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 1.0]
                
                await processor.batch_send_messages(messages)
        
        # Progress callback should have been called
        assert progress_callback.called
    
    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, sample_config):
        """Test that semaphore properly limits concurrent operations."""
        processor = BatchProcessor(sample_config, max_concurrent=2)
        
        # Verify semaphore is set correctly
        assert processor._semaphore._value == 2
        
        messages = [MessageData("stream", "general", f"Message {i}", "test") for i in range(5)]
        
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            # Simulate slow async operations to test concurrency
            async def slow_operation(*args, **kwargs):
                await asyncio.sleep(0.1)
                return {"result": "success", "id": 123}
            
            mock_client.send_message_async.side_effect = slow_operation
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 2.0]
                
                result = await processor.batch_send_messages(messages)
        
        # All messages should be processed despite concurrency limits
        assert len(result.successful) == 5
        assert result.success_rate == 1.0


class TestBatchOperations:
    """Test specific batch operation types."""
    
    def test_batch_operation_enum(self):
        """Test BatchOperation enum values."""
        assert BatchOperation.SEND_MESSAGES.value == "send_messages"
        assert BatchOperation.ADD_REACTIONS.value == "add_reactions"
        assert BatchOperation.UPDATE_TOPICS.value == "update_topics"
        assert BatchOperation.INVITE_USERS.value == "invite_users"
        
        # Test all operations are defined
        operations = list(BatchOperation)
        assert len(operations) == 4


class TestAsyncOperations:
    """Test async operation handling and error aggregation."""
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_with_mixed_results(self, sample_config):
        """Test processing with mixture of successes and failures."""
        processor = BatchProcessor(sample_config, chunk_size=2)
        
        # Create mix of valid and invalid messages
        messages = [
            MessageData("stream", "general", "Good message 1", "topic"),
            MessageData("invalid_type", "general", "Bad message", "topic"),
            MessageData("stream", "general", "Good message 2", "topic"),
            MessageData("stream", "", "Message to empty stream", "topic"),  # Should fail
        ]
        
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            
            async def mixed_operation(message_type, to, content, topic):
                if message_type != "stream" or to == "":
                    raise Exception("Invalid message data")
                return {"result": "success", "id": 123}
            
            mock_client.send_message_async.side_effect = mixed_operation
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 1.0]
                
                result = await processor.batch_send_messages(messages)
        
        # Should have 2 successes and 2 failures
        assert len(result.successful) == 2
        assert len(result.failed) == 2
        assert result.success_rate == 0.5
        
        # Check that error information is preserved
        for failed_item in result.failed:
            assert "error" in failed_item
            assert "message_data" in failed_item


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_message_list(self, sample_config):
        """Test processing empty message list."""
        processor = BatchProcessor(sample_config)
        
        with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
            mock_time.time.side_effect = [0.0, 0.1]
            
            result = await processor.batch_send_messages([])
        
        assert len(result.successful) == 0
        assert len(result.failed) == 0
        assert result.success_rate == 0.0
        assert result.total_time == 0.1
    
    @pytest.mark.asyncio
    async def test_single_message_processing(self, sample_config):
        """Test processing single message."""
        processor = BatchProcessor(sample_config)
        
        messages = [MessageData("stream", "general", "Solo message", "topic")]
        
        with patch('src.zulipchat_mcp.batch_ops.AsyncZulipClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.send_message_async.return_value = {"result": "success", "id": 456}
            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            with patch('src.zulipchat_mcp.batch_ops.time') as mock_time:
                mock_time.time.side_effect = [0.0, 0.5]
                
                result = await processor.batch_send_messages(messages)
        
        assert len(result.successful) == 1
        assert len(result.failed) == 0
        assert result.success_rate == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])