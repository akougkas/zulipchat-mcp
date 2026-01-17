"""Enhanced error handling with retry logic and rate limiting for Zulip MCP.

This module provides comprehensive error handling, automatic retry logic,
and rate limiting for API operations.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar, cast

from ..utils.logging import get_logger
from .exceptions import (
    AuthenticationError,
    RateLimitError,
    ValidationError,
    ZulipMCPError,
)
from .exceptions import (
    ConnectionError as ZulipConnectionError,
)
from .exceptions import (
    PermissionError as ZulipPermissionError,
)

logger = get_logger(__name__)

T = TypeVar("T")


class RetryStrategy(Enum):
    """Retry strategies for failed operations."""

    EXPONENTIAL = "exponential"  # Exponential backoff
    LINEAR = "linear"  # Linear backoff
    FIXED = "fixed"  # Fixed delay
    JITTERED = "jittered"  # Exponential with jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_errors: list[type] = field(
        default_factory=lambda: [
            ConnectionError,
            ZulipConnectionError,
            RateLimitError,
            TimeoutError,
        ]
    )
    non_retryable_errors: list[type] = field(
        default_factory=lambda: [
            AuthenticationError,
            ValidationError,
            PermissionError,
            ZulipPermissionError,
        ]
    )

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay <= 0:
            raise ValueError("initial_delay must be > 0")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be >= 1")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests: int = 60  # Maximum requests per time window
    time_window: float = 60.0  # Time window in seconds
    burst_limit: int = 10  # Burst capacity
    enforce: bool = True  # Whether to enforce rate limiting

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_requests <= 0:
            raise ValueError("max_requests must be > 0")
        if self.time_window <= 0:
            raise ValueError("time_window must be > 0")
        if self.burst_limit <= 0:
            raise ValueError("burst_limit must be > 0")


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize rate limiter.

        Args:
            config: Rate limiting configuration
        """
        self.config = config
        self.tokens: float = float(config.burst_limit)
        self.max_tokens: float = float(config.burst_limit)
        self.refill_rate: float = config.max_requests / config.time_window
        self.last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time to wait before making the call (0 if immediate)
        """
        if not self.config.enforce:
            return 0.0

        async with self._lock:
            # Refill tokens based on elapsed time
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            return wait_time

    async def wait_if_needed(self, tokens: int = 1) -> None:
        """Wait if rate limit would be exceeded.

        Args:
            tokens: Number of tokens to acquire
        """
        wait_time = await self.acquire(tokens)
        if wait_time > 0:
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)


# Circuit breaker removed - over-engineering for MCP adapter pattern
# MCP servers should be stateless adapters, not complex state managers


class ErrorHandler:
    """Comprehensive error handler with retry logic and rate limiting."""

    def __init__(
        self,
        retry_config: RetryConfig | None = None,
        rate_limit_config: RateLimitConfig | None = None,
    ) -> None:
        """Initialize error handler.

        Args:
            retry_config: Retry configuration
            rate_limit_config: Rate limiting configuration
        """
        self.retry_config = retry_config or RetryConfig()
        self.rate_limiter = RateLimiter(rate_limit_config or RateLimitConfig())
        # Removed: circuit_breakers and error_stats - over-engineering for MCP use case

    def calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay before next retry attempt.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        config = self.retry_config

        if config.strategy == RetryStrategy.FIXED:
            delay = config.initial_delay
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.initial_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.initial_delay * (config.backoff_factor**attempt)
        elif config.strategy == RetryStrategy.JITTERED:
            # Exponential with jitter
            base_delay = config.initial_delay * (config.backoff_factor**attempt)
            delay = base_delay + random.uniform(0, base_delay * 0.1)
        else:
            delay = config.initial_delay

        # Apply jitter if configured (except for JITTERED strategy which has it built-in)
        if config.jitter and config.strategy != RetryStrategy.JITTERED:
            delay = delay * (0.5 + random.random())

        # Cap at max delay
        return min(delay, config.max_delay)

    def is_retryable(self, error: Exception) -> bool:
        """Check if an error is retryable.

        Args:
            error: Exception to check

        Returns:
            True if the error should be retried
        """
        # Check non-retryable first (takes precedence)
        for error_type in self.retry_config.non_retryable_errors:
            if isinstance(error, error_type):
                return False

        # Check retryable
        for error_type in self.retry_config.retryable_errors:
            if isinstance(error, error_type):
                return True

        # Check for specific error conditions
        if isinstance(error, ZulipMCPError):
            # Check for specific Zulip error codes
            if hasattr(error, "details") and error.details:
                code = error.details.get("code")
                if code in ["RATE_LIMIT_HIT", "REALM_DEACTIVATED"]:
                    return True
                if code in ["BAD_REQUEST", "UNAUTHORIZED", "FORBIDDEN"]:
                    return False

        # Default to not retrying unknown errors
        return False

    async def execute_with_retry(
        self,
        func: Callable[..., T],
        *args: Any,
        operation_name: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute a function with automatic retry on failure.

        Args:
            func: Function to execute
            *args: Function arguments
            operation_name: Name for logging/stats
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retry attempts fail
        """
        operation_name = operation_name or func.__name__
        last_error: Exception | None = None

        for attempt in range(self.retry_config.max_attempts):
            try:
                # Apply rate limiting
                await self.rate_limiter.wait_if_needed()

                # Direct execution - keep it simple
                if asyncio.iscoroutinefunction(func):
                    async_func = cast(Callable[..., Awaitable[T]], func)
                    return await async_func(*args, **kwargs)
                return func(*args, **kwargs)

            except Exception as e:
                last_error = e
                # Simplified error handling - no statistics tracking

                # Check if retryable
                if not self.is_retryable(e):
                    logger.error(f"Non-retryable error in {operation_name}: {e}")
                    raise

                # Check if we have more attempts
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self.calculate_retry_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.retry_config.max_attempts} "
                        f"failed for {operation_name}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.retry_config.max_attempts} attempts failed "
                        f"for {operation_name}"
                    )

        # All attempts failed
        if last_error:
            raise last_error
        else:
            raise RuntimeError(f"Failed to execute {operation_name}")

    # Removed error statistics and circuit breaker methods - over-engineering

    def create_safe_executor(
        self, func: Callable[..., T], operation_name: str | None = None
    ) -> Callable[..., Any]:
        """Create a wrapped version of a function with error handling.

        Args:
            func: Function to wrap
            operation_name: Name for logging/stats

        Returns:
            Wrapped function with error handling
        """
        operation_name = operation_name or func.__name__

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.execute_with_retry(
                func, *args, operation_name=operation_name, **kwargs
            )

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            # Run async handler in sync context
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self.execute_with_retry(
                        func, *args, operation_name=operation_name, **kwargs
                    )
                )
            finally:
                loop.close()

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


# Global error handler instance
_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance.

    Returns:
        Global error handler
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def with_retry(
    max_attempts: int = 3,
    operation_name: str | None = None,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
) -> Callable[[Callable[..., T]], Callable[..., Any]]:
    """Decorator to add retry logic to a function.

    Args:
        max_attempts: Maximum retry attempts
        operation_name: Name for logging/stats
        strategy: Retry strategy to use

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., Any]:
        handler = ErrorHandler(
            retry_config=RetryConfig(
                max_attempts=max_attempts,
                strategy=strategy,
            )
        )
        return handler.create_safe_executor(func, operation_name)

    return decorator


def with_rate_limit(
    calls_per_second: float = 10.0,
    calls_per_minute: float = 200.0,
) -> Callable[[Callable[..., T]], Callable[..., Any]]:
    """Decorator to add rate limiting to a function.

    Args:
        calls_per_second: Maximum calls per second
        calls_per_minute: Maximum calls per minute

    Returns:
        Decorated function with rate limiting
    """

    def decorator(func: Callable[..., T]) -> Callable[..., Any]:
        # Convert calls_per_second to max_requests and time_window
        max_requests = int(calls_per_second)
        time_window = 1.0
        burst_limit = max(1, int(calls_per_second / 10))  # 10% burst capacity

        handler = ErrorHandler(
            rate_limit_config=RateLimitConfig(
                max_requests=max_requests,
                time_window=time_window,
                burst_limit=burst_limit,
            )
        )
        return handler.create_safe_executor(func)

    return decorator
