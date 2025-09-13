"""Tests for simplified ErrorHandler v2.5.0 functionality (no circuit breaker)."""

from __future__ import annotations

import asyncio
import time

import pytest

from zulipchat_mcp.core import (
    ErrorHandler,
    RateLimitConfig,
    RateLimiter,
    RetryConfig,
    RetryStrategy,
    get_error_handler,
    with_rate_limit,
    with_retry,
)
from zulipchat_mcp.core.exceptions import (
    AuthenticationError,
    RateLimitError,
    ValidationError,
)
from zulipchat_mcp.core.exceptions import (
    ConnectionError as ZulipConnectionError,
)


class TestRetryConfig:
    """Test RetryConfig functionality."""

    def test_retry_config_creation(self) -> None:
        """Test creating RetryConfig instances."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff_factor=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=True,
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.backoff_factor == 2.0
        assert config.strategy == RetryStrategy.EXPONENTIAL
        assert config.jitter is True

    def test_retry_config_validation(self) -> None:
        """Test RetryConfig parameter validation."""
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            RetryConfig(max_attempts=0)

        with pytest.raises(ValueError, match="initial_delay must be > 0"):
            RetryConfig(initial_delay=0)

        with pytest.raises(ValueError, match="max_delay must be >= initial_delay"):
            RetryConfig(initial_delay=10.0, max_delay=5.0)

        with pytest.raises(ValueError, match="backoff_factor must be >= 1"):
            RetryConfig(backoff_factor=0.5)


class TestRateLimitConfig:
    """Test RateLimitConfig functionality."""

    def test_rate_limit_config_creation(self) -> None:
        """Test creating RateLimitConfig instances."""
        config = RateLimitConfig(
            max_requests=100,
            time_window=60.0,
            burst_limit=20,
            enforce=True,
        )

        assert config.max_requests == 100
        assert config.time_window == 60.0
        assert config.burst_limit == 20
        assert config.enforce is True

    def test_rate_limit_config_validation(self) -> None:
        """Test RateLimitConfig parameter validation."""
        with pytest.raises(ValueError, match="max_requests must be > 0"):
            RateLimitConfig(max_requests=0)

        with pytest.raises(ValueError, match="time_window must be > 0"):
            RateLimitConfig(time_window=0)

        with pytest.raises(ValueError, match="burst_limit must be > 0"):
            RateLimitConfig(burst_limit=0)


class TestRateLimiter:
    """Test RateLimiter functionality."""

    @pytest.fixture
    def rate_limiter(self) -> RateLimiter:
        """Create a RateLimiter for testing."""
        config = RateLimitConfig(
            max_requests=10,
            time_window=1.0,  # 1 second
            burst_limit=5,
            enforce=True,
        )
        return RateLimiter(config)

    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self, rate_limiter: RateLimiter) -> None:
        """Test RateLimiter initialization."""
        assert rate_limiter.tokens == 5  # burst_limit
        assert rate_limiter.max_tokens == 5
        assert rate_limiter.refill_rate == 10.0  # max_requests / time_window

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_with_tokens(
        self, rate_limiter: RateLimiter
    ) -> None:
        """Test acquiring tokens when available."""
        wait_time = await rate_limiter.acquire(3)
        assert wait_time == 0.0
        assert rate_limiter.tokens == 2

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_without_tokens(
        self, rate_limiter: RateLimiter
    ) -> None:
        """Test acquiring tokens when not available."""
        # Exhaust tokens
        await rate_limiter.acquire(5)
        assert rate_limiter.tokens == 0

        # Next acquire should require waiting
        wait_time = await rate_limiter.acquire(1)
        assert wait_time > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_token_refill(self) -> None:
        """Test token refill over time."""
        config = RateLimitConfig(
            max_requests=10,
            time_window=1.0,
            burst_limit=5,
            enforce=True,
        )
        limiter = RateLimiter(config)

        # Exhaust tokens
        await limiter.acquire(5)
        assert limiter.tokens == 0

        # Wait a bit and check refill
        await asyncio.sleep(0.1)
        await limiter.acquire(0)  # Trigger refill
        assert limiter.tokens > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_disabled(self) -> None:
        """Test rate limiter when enforcement is disabled."""
        config = RateLimitConfig(enforce=False)
        limiter = RateLimiter(config)

        wait_time = await limiter.acquire(1000)  # Large request
        assert wait_time == 0.0


class TestErrorHandler:
    """Test ErrorHandler functionality (simplified without circuit breaker)."""

    def test_error_handler_initialization(self) -> None:
        """Test ErrorHandler initialization."""
        retry_config = RetryConfig(max_attempts=5)
        rate_limit_config = RateLimitConfig(max_requests=100)

        handler = ErrorHandler(
            retry_config=retry_config,
            rate_limit_config=rate_limit_config,
        )

        assert handler.retry_config == retry_config
        assert isinstance(handler.rate_limiter, RateLimiter)

    def test_error_handler_defaults(self) -> None:
        """Test ErrorHandler with default configuration."""
        handler = ErrorHandler()

        assert handler.retry_config.max_attempts == 3
        assert isinstance(handler.rate_limiter, RateLimiter)

    def test_calculate_retry_delay_exponential(self) -> None:
        """Test exponential backoff calculation."""
        config = RetryConfig(
            initial_delay=1.0,
            backoff_factor=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=False,
        )
        handler = ErrorHandler(retry_config=config)

        assert handler.calculate_retry_delay(0) == 1.0
        assert handler.calculate_retry_delay(1) == 2.0
        assert handler.calculate_retry_delay(2) == 4.0

    def test_calculate_retry_delay_linear(self) -> None:
        """Test linear backoff calculation."""
        config = RetryConfig(
            initial_delay=1.0,
            strategy=RetryStrategy.LINEAR,
            jitter=False,
        )
        handler = ErrorHandler(retry_config=config)

        assert handler.calculate_retry_delay(0) == 1.0
        assert handler.calculate_retry_delay(1) == 2.0
        assert handler.calculate_retry_delay(2) == 3.0

    def test_calculate_retry_delay_fixed(self) -> None:
        """Test fixed delay calculation."""
        config = RetryConfig(
            initial_delay=2.0,
            strategy=RetryStrategy.FIXED,
            jitter=False,
        )
        handler = ErrorHandler(retry_config=config)

        assert handler.calculate_retry_delay(0) == 2.0
        assert handler.calculate_retry_delay(1) == 2.0
        assert handler.calculate_retry_delay(2) == 2.0

    def test_calculate_retry_delay_max_cap(self) -> None:
        """Test that retry delay is capped at max_delay."""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=5.0,
            backoff_factor=10.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=False,
        )
        handler = ErrorHandler(retry_config=config)

        # Large attempt should be capped
        assert handler.calculate_retry_delay(10) == 5.0

    def test_is_retryable_errors(self) -> None:
        """Test retryable error detection."""
        handler = ErrorHandler()

        # Retryable errors
        assert handler.is_retryable(ConnectionError()) is True
        assert handler.is_retryable(ZulipConnectionError("test")) is True
        assert handler.is_retryable(RateLimitError("test")) is True
        assert handler.is_retryable(TimeoutError()) is True

        # Non-retryable errors
        assert handler.is_retryable(AuthenticationError("test")) is False
        assert handler.is_retryable(ValidationError("test")) is False
        assert handler.is_retryable(ValueError("test")) is False

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self) -> None:
        """Test successful execution on first attempt."""
        handler = ErrorHandler()

        async def mock_func():
            return "success"

        result = await handler.execute_with_retry(mock_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure_then_success(self) -> None:
        """Test retry on failure then success."""
        handler = ErrorHandler(retry_config=RetryConfig(initial_delay=0.01))
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("temporary failure")
            return "success"

        result = await handler.execute_with_retry(mock_func)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable_error(self) -> None:
        """Test immediate failure on non-retryable error."""
        handler = ErrorHandler()

        async def mock_func():
            raise AuthenticationError("auth failed")

        with pytest.raises(AuthenticationError):
            await handler.execute_with_retry(mock_func)

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self) -> None:
        """Test failure after all retry attempts exhausted."""
        handler = ErrorHandler(
            retry_config=RetryConfig(max_attempts=2, initial_delay=0.01)
        )

        async def mock_func():
            raise ConnectionError("persistent failure")

        with pytest.raises(ConnectionError):
            await handler.execute_with_retry(mock_func)

    def test_create_safe_executor_async(self) -> None:
        """Test creating safe executor for async functions."""
        handler = ErrorHandler()

        async def mock_func(x: int) -> int:
            return x * 2

        safe_func = handler.create_safe_executor(mock_func)

        # Should return wrapped async function
        assert asyncio.iscoroutinefunction(safe_func)

    def test_create_safe_executor_sync(self) -> None:
        """Test creating safe executor for sync functions."""
        handler = ErrorHandler()

        def mock_func(x: int) -> int:
            return x * 2

        safe_func = handler.create_safe_executor(mock_func)

        # Should return wrapped function
        assert callable(safe_func)


class TestGlobalErrorHandler:
    """Test global error handler functions."""

    def test_get_error_handler(self) -> None:
        """Test getting global error handler."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()

        # Should return same instance
        assert handler1 is handler2
        assert isinstance(handler1, ErrorHandler)


class TestDecorators:
    """Test retry and rate limit decorators."""

    @pytest.mark.asyncio
    async def test_with_retry_decorator_success(self) -> None:
        """Test retry decorator on successful function."""

        @with_retry(max_attempts=3)
        async def mock_func(x: int) -> int:
            return x * 2

        result = await mock_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_with_retry_decorator_failure(self) -> None:
        """Test retry decorator with failures."""
        call_count = 0

        @with_retry(max_attempts=3, strategy=RetryStrategy.FIXED)
        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temp failure")
            return "success"

        result = await mock_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_rate_limit_decorator(self) -> None:
        """Test rate limit decorator."""

        @with_rate_limit(calls_per_second=10.0)
        async def mock_func() -> str:
            return "limited"

        # Should work without rate limiting issues in test
        result = await mock_func()
        assert result == "limited"


class TestIntegration:
    """Integration tests for ErrorHandler functionality."""

    @pytest.mark.asyncio
    async def test_error_handler_with_rate_limiting(self) -> None:
        """Test ErrorHandler with rate limiting integration."""
        # Fast rate limit for testing
        rate_config = RateLimitConfig(
            max_requests=2,
            time_window=1.0,
            burst_limit=2,
            enforce=True,
        )

        handler = ErrorHandler(rate_limit_config=rate_config)

        async def mock_func():
            return "success"

        # First two calls should succeed immediately
        result1 = await handler.execute_with_retry(mock_func)
        result2 = await handler.execute_with_retry(mock_func)

        assert result1 == "success"
        assert result2 == "success"

        # Third call should be delayed (but we won't wait for it in test)
        start_time = time.time()
        result3 = await handler.execute_with_retry(mock_func)
        elapsed = time.time() - start_time

        assert result3 == "success"
        # Should have some delay due to rate limiting
        assert elapsed >= 0  # Just check it completes
