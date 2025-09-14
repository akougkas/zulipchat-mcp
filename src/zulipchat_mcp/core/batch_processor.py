"""Intelligent Batch Processing System for ZulipChat MCP v2.5.1.

This module implements an adaptive batch processing system that dynamically
adjusts batch sizes based on API rate limits and performance characteristics.

Features:
- Dynamic batch sizing with learning
- Predictive rate limiting
- Progress tracking and reporting
- Partial failure recovery
- Automatic retry with backoff
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Generic, TypeVar

from ..utils.logging import get_logger
from ..utils.metrics import Timer, track_tool_call

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchStatus(Enum):
    """Status of batch processing."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BatchConfig:
    """Configuration for batch processing."""

    initial_batch_size: int = 50
    max_batch_size: int = 200
    min_batch_size: int = 10

    # Rate limiting
    max_requests_per_second: float = 10.0
    burst_capacity: int = 20

    # Retry configuration
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 60.0
    backoff_multiplier: float = 2.0

    # Performance tuning
    enable_adaptive_sizing: bool = True
    size_increase_factor: float = 1.5
    size_decrease_factor: float = 0.5
    success_threshold: int = 3  # Consecutive successes before increasing size

    # Progress reporting
    report_interval: float = 1.0  # seconds
    enable_progress_callbacks: bool = True


@dataclass
class BatchResult(Generic[R]):
    """Result of batch processing."""

    status: BatchStatus
    total_items: int
    processed_items: int
    failed_items: list[tuple[Any, Exception]] = field(default_factory=list)
    results: list[R] = field(default_factory=list)

    # Performance metrics
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    total_batches: int = 0
    retry_count: int = 0

    # Statistics
    avg_batch_size: float = 0.0
    avg_processing_time: float = 0.0
    effective_rate: float = 0.0  # items per second

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    @property
    def duration(self) -> timedelta:
        """Calculate total duration."""
        if self.end_time is None:
            return datetime.utcnow() - self.start_time
        return self.end_time - self.start_time


@dataclass
class ProgressReport:
    """Progress report for batch operations."""

    total_items: int
    processed_items: int
    failed_items: int
    current_batch: int
    total_batches: int
    percent_complete: float
    elapsed_time: timedelta
    estimated_time_remaining: timedelta | None
    current_rate: float  # items per second
    status_message: str


class RateLimiter:
    """Token bucket rate limiter with burst capacity."""

    def __init__(self, rate: float, burst: int):
        """Initialize rate limiter.

        Args:
            rate: Tokens per second
            burst: Maximum burst capacity
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        async with self._lock:
            wait_time = 0.0

            while tokens > self.tokens:
                # Calculate how long to wait
                deficit = tokens - self.tokens
                wait_time = deficit / self.rate

                # Wait and refill
                await asyncio.sleep(wait_time)
                self._refill()

            # Consume tokens
            self.tokens -= tokens
            return wait_time

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update

        # Add tokens based on rate
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now


class AdaptiveBatchSizer:
    """Dynamically adjust batch size based on success/failure patterns."""

    def __init__(self, config: BatchConfig):
        """Initialize adaptive batch sizer."""
        self.config = config
        self.current_size = config.initial_batch_size
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.size_history = deque(maxlen=100)
        self.performance_history = deque(maxlen=100)

    def record_success(self, processing_time: float) -> None:
        """Record successful batch processing."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.performance_history.append(processing_time)

        # Increase batch size after threshold successes
        if (
            self.config.enable_adaptive_sizing
            and self.consecutive_successes >= self.config.success_threshold
        ):
            self._increase_size()

    def record_failure(self, is_rate_limit: bool = False) -> None:
        """Record failed batch processing."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        # Decrease batch size on failure
        if self.config.enable_adaptive_sizing:
            if is_rate_limit:
                # Aggressive reduction for rate limits
                self._decrease_size(factor=0.3)
            else:
                self._decrease_size()

    def get_next_batch_size(self) -> int:
        """Get the next batch size to use."""
        self.size_history.append(self.current_size)
        return self.current_size

    def _increase_size(self) -> None:
        """Increase batch size."""
        new_size = int(self.current_size * self.config.size_increase_factor)
        self.current_size = min(new_size, self.config.max_batch_size)
        self.consecutive_successes = 0
        logger.debug(f"Increased batch size to {self.current_size}")

    def _decrease_size(self, factor: float | None = None) -> None:
        """Decrease batch size."""
        decrease_factor = factor or self.config.size_decrease_factor
        new_size = int(self.current_size * decrease_factor)
        self.current_size = max(new_size, self.config.min_batch_size)
        logger.debug(f"Decreased batch size to {self.current_size}")

    def get_statistics(self) -> dict[str, Any]:
        """Get sizing statistics."""
        if not self.size_history:
            return {}

        return {
            "current_size": self.current_size,
            "avg_size": sum(self.size_history) / len(self.size_history),
            "min_size": min(self.size_history),
            "max_size": max(self.size_history),
            "avg_processing_time": (
                sum(self.performance_history) / len(self.performance_history)
                if self.performance_history
                else 0
            ),
        }


class ProgressTracker:
    """Track and report progress of batch operations."""

    def __init__(
        self, total_items: int, callback: Callable[[ProgressReport], None] | None = None
    ):
        """Initialize progress tracker.

        Args:
            total_items: Total number of items to process
            callback: Optional callback for progress reports
        """
        self.total_items = total_items
        self.processed_items = 0
        self.failed_items = 0
        self.current_batch = 0
        self.start_time = datetime.utcnow()
        self.callback = callback
        self.last_report_time = time.monotonic()
        self.recent_rates = deque(maxlen=10)

    def update(self, processed: int, failed: int = 0) -> None:
        """Update progress.

        Args:
            processed: Number of items processed
            failed: Number of items failed
        """
        self.processed_items += processed
        self.failed_items += failed

        # Calculate current rate
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        if elapsed > 0:
            current_rate = self.processed_items / elapsed
            self.recent_rates.append(current_rate)

    def increment_batch(self) -> None:
        """Increment batch counter."""
        self.current_batch += 1

    def should_report(self, interval: float) -> bool:
        """Check if progress should be reported."""
        return time.monotonic() - self.last_report_time >= interval

    def generate_report(self, total_batches: int | None = None) -> ProgressReport:
        """Generate progress report."""
        elapsed = datetime.utcnow() - self.start_time
        percent_complete = (
            (self.processed_items / self.total_items * 100)
            if self.total_items > 0
            else 0
        )

        # Calculate current rate
        current_rate = (
            sum(self.recent_rates) / len(self.recent_rates) if self.recent_rates else 0
        )

        # Estimate time remaining
        if current_rate > 0 and self.processed_items < self.total_items:
            remaining_items = self.total_items - self.processed_items
            estimated_seconds = remaining_items / current_rate
            estimated_time_remaining = timedelta(seconds=estimated_seconds)
        else:
            estimated_time_remaining = None

        # Generate status message
        if percent_complete >= 100:
            status_message = "Processing complete"
        elif percent_complete > 0:
            status_message = f"Processing... {percent_complete:.1f}% complete"
        else:
            status_message = "Starting processing..."

        self.last_report_time = time.monotonic()

        return ProgressReport(
            total_items=self.total_items,
            processed_items=self.processed_items,
            failed_items=self.failed_items,
            current_batch=self.current_batch,
            total_batches=total_batches or 0,
            percent_complete=percent_complete,
            elapsed_time=elapsed,
            estimated_time_remaining=estimated_time_remaining,
            current_rate=current_rate,
            status_message=status_message,
        )


class BatchProcessor(Generic[T, R]):
    """Intelligent batch processor with adaptive sizing and rate limiting."""

    def __init__(self, config: BatchConfig | None = None):
        """Initialize batch processor.

        Args:
            config: Batch processing configuration
        """
        self.config = config or BatchConfig()
        self.rate_limiter = RateLimiter(
            self.config.max_requests_per_second, self.config.burst_capacity
        )
        self.batch_sizer = AdaptiveBatchSizer(self.config)
        self.progress_tracker: ProgressTracker | None = None

    async def process(
        self,
        items: list[T],
        operation: Callable[[list[T]], tuple[list[R], list[tuple[T, Exception]]]],
        progress_callback: Callable[[ProgressReport], None] | None = None,
    ) -> BatchResult[R]:
        """Process items in intelligent batches.

        Args:
            items: Items to process
            operation: Async operation to perform on each batch
                      Returns (results, failures) tuple
            progress_callback: Optional callback for progress updates

        Returns:
            BatchResult with processing results and statistics
        """
        with Timer("batch_processing_duration", {"operation": "batch_process"}):
            track_tool_call("batch_processor")

            result = BatchResult[R](
                status=BatchStatus.PROCESSING,
                total_items=len(items),
                processed_items=0,
            )

            # Initialize progress tracking
            self.progress_tracker = ProgressTracker(len(items), progress_callback)

            # Process in batches
            remaining_items = items.copy()

            while remaining_items:
                # Get next batch size
                batch_size = self.batch_sizer.get_next_batch_size()
                batch = remaining_items[:batch_size]
                remaining_items = remaining_items[batch_size:]

                # Rate limiting
                wait_time = await self.rate_limiter.acquire(1)
                if wait_time > 0:
                    logger.debug(f"Rate limited, waited {wait_time:.2f}s")

                # Process batch with retry logic
                batch_start = time.monotonic()
                success = False

                for attempt in range(self.config.max_retries):
                    try:
                        # Execute operation
                        batch_results, batch_failures = (
                            await self._execute_with_timeout(operation, batch)
                        )

                        # Record results
                        result.results.extend(batch_results)
                        result.failed_items.extend(batch_failures)
                        result.processed_items += len(batch_results)

                        # Update progress
                        self.progress_tracker.update(
                            len(batch_results), len(batch_failures)
                        )

                        # Record success
                        processing_time = time.monotonic() - batch_start
                        self.batch_sizer.record_success(processing_time)
                        success = True
                        break

                    except asyncio.TimeoutError:
                        logger.warning(f"Batch timeout on attempt {attempt + 1}")
                        if attempt < self.config.max_retries - 1:
                            await self._backoff(attempt)

                    except Exception as e:
                        logger.error(f"Batch processing error: {e}")

                        # Check if rate limit error
                        is_rate_limit = "rate" in str(e).lower() or "429" in str(e)
                        self.batch_sizer.record_failure(is_rate_limit)

                        if attempt < self.config.max_retries - 1:
                            await self._backoff(attempt)
                        else:
                            # Mark all items in batch as failed
                            for item in batch:
                                result.failed_items.append((item, e))

                if not success:
                    result.retry_count += 1

                # Update batch counter
                self.progress_tracker.increment_batch()
                result.total_batches += 1

                # Report progress if needed
                if (
                    self.config.enable_progress_callbacks
                    and self.progress_tracker.should_report(self.config.report_interval)
                ):
                    report = self.progress_tracker.generate_report(
                        total_batches=len(items) // batch_size + 1
                    )
                    if progress_callback:
                        progress_callback(report)

            # Finalize result
            result.end_time = datetime.utcnow()

            # Calculate statistics
            if result.total_batches > 0:
                result.avg_batch_size = result.total_items / result.total_batches
                result.avg_processing_time = (
                    result.duration.total_seconds() / result.total_batches
                )

            if result.duration.total_seconds() > 0:
                result.effective_rate = (
                    result.processed_items / result.duration.total_seconds()
                )

            # Determine final status
            if result.failed_items:
                result.status = (
                    BatchStatus.PARTIAL
                    if result.processed_items > 0
                    else BatchStatus.FAILED
                )
            else:
                result.status = BatchStatus.COMPLETED

            # Final progress report
            if progress_callback and self.progress_tracker:
                final_report = self.progress_tracker.generate_report(
                    result.total_batches
                )
                progress_callback(final_report)

            logger.info(
                f"Batch processing completed: {result.processed_items}/{result.total_items} items, "
                f"success rate: {result.success_rate:.1f}%, "
                f"effective rate: {result.effective_rate:.1f} items/s"
            )

            return result

    async def _execute_with_timeout(
        self,
        operation: Callable,
        batch: list[T],
        timeout: float = 30.0,
    ) -> tuple[list[R], list[tuple[T, Exception]]]:
        """Execute operation with timeout."""
        try:
            return await asyncio.wait_for(operation(batch), timeout=timeout)
        except asyncio.TimeoutError:
            raise

    async def _backoff(self, attempt: int) -> None:
        """Calculate and apply backoff delay."""
        delay = min(
            self.config.initial_backoff * (self.config.backoff_multiplier**attempt),
            self.config.max_backoff,
        )
        logger.debug(f"Backing off for {delay:.2f}s")
        await asyncio.sleep(delay)

    def get_statistics(self) -> dict[str, Any]:
        """Get processor statistics."""
        stats = {
            "rate_limiter": {
                "current_tokens": self.rate_limiter.tokens,
                "rate": self.rate_limiter.rate,
                "burst": self.rate_limiter.burst,
            },
            "batch_sizer": self.batch_sizer.get_statistics(),
        }

        if self.progress_tracker:
            report = self.progress_tracker.generate_report()
            stats["progress"] = {
                "processed": report.processed_items,
                "failed": report.failed_items,
                "rate": report.current_rate,
                "elapsed": str(report.elapsed_time),
            }

        return stats
