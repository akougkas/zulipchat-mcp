"""Core domain logic and primitives for ZulipChat MCP."""

# Export new v2.5.0 foundation components (simplified)
from .error_handling import (
    ErrorHandler,
    RateLimitConfig,
    RateLimiter,
    RetryConfig,
    RetryStrategy,
    get_error_handler,
    with_rate_limit,
    with_retry,
)
# Note: CircuitBreaker removed as over-engineering
from .identity import Identity, IdentityManager, IdentityType
from .migration import MigrationManager, MigrationStatus, ToolMigration
from .validation import (
    NarrowBuilder,
    NarrowFilter,
    NarrowOperator,
    ParameterSchema,
    ParameterValidator,
    ToolSchema,
    ValidationMode,
    get_parameter_validator,
)

__all__ = [
    # Identity Management
    "Identity",
    "IdentityManager",
    "IdentityType",
    # Validation
    "NarrowBuilder",
    "NarrowFilter",
    "NarrowOperator",
    "ParameterSchema",
    "ParameterValidator",
    "ToolSchema",
    "ValidationMode",
    "get_parameter_validator",
    # Error Handling (simplified)
    "ErrorHandler",
    "RateLimitConfig",
    "RateLimiter",
    "RetryConfig",
    "RetryStrategy",
    "get_error_handler",
    "with_rate_limit",
    "with_retry",
    # Migration
    "MigrationManager",
    "MigrationStatus",
    "ToolMigration",
]
