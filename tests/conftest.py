"""Pytest configuration and shared fixtures for Zulip MCP v2.5.0 tests."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio
from zulip import Client

from zulipchat_mcp.config import ConfigManager
from zulipchat_mcp.core import (
    ErrorHandler,
    IdentityManager,
    IdentityType,
    MigrationManager,
    ParameterValidator,
    RetryConfig,
    RetryStrategy,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config() -> ConfigManager:
    """Mock ConfigManager with basic configuration."""
    config = Mock(spec=ConfigManager)
    config.email = "test@example.com"
    config.api_key = "test-api-key"
    config.site = "https://test.zulipchat.com"
    config.bot_email = "bot@example.com"
    config.bot_api_key = "bot-api-key"
    config.bot_name = "Test Bot"
    config.has_bot_credentials.return_value = True
    config.get_zulip_client_config.side_effect = lambda use_bot=False: {
        "email": "bot@example.com" if use_bot else "test@example.com",
        "api_key": "bot-api-key" if use_bot else "test-api-key",
        "site": "https://test.zulipchat.com",
    }
    config.validate_config.return_value = True
    return config


@pytest.fixture
def mock_zulip_client() -> Mock:
    """Mock Zulip client with common API responses."""
    client = Mock(spec=Client)
    
    # Default successful responses
    client.send_message.return_value = {"result": "success", "id": 12345}
    client.get_messages.return_value = {
        "result": "success",
        "messages": [
            {
                "id": 12345,
                "sender_full_name": "Test User",
                "sender_email": "test@example.com",
                "timestamp": 1640995200,
                "content": "Test message",
                "type": "stream",
                "display_recipient": "general",
                "subject": "test-topic",
                "reactions": [],
                "flags": [],
            }
        ],
        "anchor": 12345,
        "found_anchor": True,
        "found_newest": True,
        "found_oldest": False,
        "history_limited": False,
    }
    client.edit_message.return_value = {"result": "success"}
    client.update_message_flags.return_value = {"result": "success"}
    client.get_streams.return_value = {
        "result": "success",
        "streams": [
            {"name": "general", "stream_id": 1, "description": "General discussion"}
        ],
    }
    client.get_users.return_value = {
        "result": "success",
        "members": [
            {
                "user_id": 1,
                "full_name": "Test User",
                "email": "test@example.com",
                "is_active": True,
            }
        ],
    }
    
    return client


@pytest.fixture
def mock_async_zulip_client() -> AsyncMock:
    """Mock async Zulip client."""
    client = AsyncMock()
    
    # Default successful responses
    client.send_message.return_value = {"result": "success", "id": 12345}
    client.get_messages_raw.return_value = {
        "result": "success",
        "messages": [
            {
                "id": 12345,
                "sender_full_name": "Test User",
                "sender_email": "test@example.com",
                "timestamp": 1640995200,
                "content": "Test message",
                "type": "stream",
                "display_recipient": "general",
                "subject": "test-topic",
                "reactions": [],
                "flags": [],
            }
        ],
        "anchor": 12345,
        "found_anchor": True,
        "found_newest": True,
        "found_oldest": False,
        "history_limited": False,
    }
    client.edit_message.return_value = {"result": "success"}
    client.update_message_flags.return_value = {"result": "success"}
    
    return client


@pytest.fixture
def identity_manager(mock_config) -> IdentityManager:
    """IdentityManager fixture."""
    return IdentityManager(mock_config)


@pytest.fixture
def parameter_validator() -> ParameterValidator:
    """ParameterValidator fixture."""
    return ParameterValidator()


@pytest.fixture
def error_handler() -> ErrorHandler:
    """ErrorHandler fixture with test configuration."""
    return ErrorHandler(
        retry_config=RetryConfig(
            max_attempts=3,
            initial_delay=0.01,  # Fast retries for tests
            strategy=RetryStrategy.FIXED,
            jitter=False,
        )
    )


@pytest.fixture
def migration_manager() -> MigrationManager:
    """MigrationManager fixture."""
    return MigrationManager()


@pytest.fixture
def sample_messages() -> list[dict[str, Any]]:
    """Sample message data for testing."""
    return [
        {
            "id": 12345,
            "sender_full_name": "Alice Johnson",
            "sender_email": "alice@example.com",
            "timestamp": 1640995200,
            "content": "Hello everyone! 👋",
            "type": "stream",
            "display_recipient": "general",
            "subject": "introductions",
            "reactions": [{"emoji_name": "wave", "user_id": [1, 2]}],
            "flags": ["read"],
        },
        {
            "id": 12346,
            "sender_full_name": "Bob Smith",
            "sender_email": "bob@example.com",
            "timestamp": 1640995300,
            "content": "Welcome to the team!",
            "type": "stream",
            "display_recipient": "general",
            "subject": "introductions",
            "reactions": [],
            "flags": [],
        },
        {
            "id": 12347,
            "sender_full_name": "Carol Davis",
            "sender_email": "carol@example.com",
            "timestamp": 1640995400,
            "content": "Check out this [link](https://example.com)",
            "type": "private",
            "display_recipient": [
                {"email": "alice@example.com", "full_name": "Alice Johnson"}
            ],
            "subject": "",
            "reactions": [],
            "flags": ["starred"],
        },
    ]


@pytest.fixture
def sample_narrow_filters() -> list[dict[str, str]]:
    """Sample narrow filters for testing."""
    return [
        {"operator": "stream", "operand": "general"},
        {"operator": "topic", "operand": "test-topic"},
        {"operator": "sender", "operand": "test@example.com"},
        {"operator": "search", "operand": "python"},
        {"operator": "has", "operand": "link"},
        {"operator": "near", "operand": "12345"},
    ]


@pytest.fixture
def large_content() -> str:
    """Large content for testing truncation."""
    return "Large content " * 5000  # ~65KB of text


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing."""
    fixed_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("zulipchat_mcp.tools.messaging_v25.datetime", Mock())
        mp.setattr("zulipchat_mcp.tools.messaging_v25.datetime.now", lambda: fixed_time)
        yield fixed_time


# Markers for different test categories
pytest_mark_slow = pytest.mark.slow
pytest_mark_integration = pytest.mark.integration
pytest_mark_unit = pytest.mark.unit


@pytest.fixture
def benchmark_config():
    """Configuration for benchmark tests."""
    return {
        "max_duration_ms": 100,  # Max 100ms for most operations
        "max_memory_mb": 50,     # Max 50MB memory usage
        "samples": 10,           # Number of benchmark samples
    }


class MockRateLimiter:
    """Mock rate limiter for testing."""
    
    def __init__(self):
        self.calls = 0
        self.should_limit = False
    
    async def __aenter__(self):
        self.calls += 1
        if self.should_limit:
            raise Exception("Rate limited")
        return self
    
    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter fixture."""
    return MockRateLimiter()


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_message(
        id: int = 12345,
        sender: str = "test@example.com",
        content: str = "Test message",
        msg_type: str = "stream",
        stream: str = "general",
        topic: str = "test-topic",
    ) -> dict[str, Any]:
        """Create a test message."""
        return {
            "id": id,
            "sender_full_name": sender.split("@")[0].title(),
            "sender_email": sender,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "content": content,
            "type": msg_type,
            "display_recipient": stream if msg_type == "stream" else sender,
            "subject": topic if msg_type == "stream" else "",
            "reactions": [],
            "flags": [],
        }
    
    @staticmethod
    def create_narrow_filter(operator: str, operand: str) -> dict[str, str]:
        """Create a narrow filter."""
        return {"operator": operator, "operand": operand}


@pytest.fixture
def test_data_factory():
    """Test data factory fixture."""
    return TestDataFactory()


# Performance testing utilities
class PerformanceMonitor:
    """Monitor performance metrics during tests."""
    
    def __init__(self):
        self.start_time = None
        self.memory_usage = []
        self.call_counts = {}
    
    def start(self):
        """Start monitoring."""
        self.start_time = datetime.now()
    
    def stop(self):
        """Stop monitoring and return metrics."""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds() * 1000
            return {
                "duration_ms": duration,
                "call_counts": self.call_counts.copy(),
                "peak_memory_mb": max(self.memory_usage) if self.memory_usage else 0,
            }
        return {}
    
    def record_call(self, func_name: str):
        """Record a function call."""
        self.call_counts[func_name] = self.call_counts.get(func_name, 0) + 1


@pytest.fixture
def performance_monitor():
    """Performance monitor fixture."""
    return PerformanceMonitor()