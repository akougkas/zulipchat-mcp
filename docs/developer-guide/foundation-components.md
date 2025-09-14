# Foundation Components

ZulipChat MCP is built on a robust foundation layer that provides identity management, parameter validation, error handling, and migration support. This guide details each foundation component and their integration patterns.

## Foundation Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Tool Layer                        │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Identity    │ │ Validation  │ │ Error       │   │
│  │ Manager     │ │ Framework   │ │ Handling    │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Migration   │ │ Cache       │ │ Metrics     │   │
│  │ Manager     │ │ System      │ │ & Logging   │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────┤
│                Core Infrastructure                  │
└─────────────────────────────────────────────────────┘
```

## Identity Manager

**Module**: `core/identity.py`  
**Purpose**: Multi-identity support with dynamic switching and capability management

### Core Classes

#### ZulipIdentity
```python
@dataclass
class ZulipIdentity:
    """Represents a Zulip identity with credentials and capabilities."""
    
    type: IdentityType
    email: str
    api_key: str
    site: str
    client: Optional[zulip.Client] = None
    capabilities: Optional[Set[str]] = None
    is_admin: Optional[bool] = None
    
    def validate_credentials(self) -> bool:
        """Validate identity credentials against Zulip API."""
        
    def get_capabilities(self) -> Set[str]:
        """Get identity-specific capabilities."""
        
    def test_connection(self) -> Dict[str, Any]:
        """Test connection and gather identity info."""
```

#### IdentityManager
```python
class IdentityManager:
    """Manages multiple Zulip identities with context switching."""
    
    def __init__(self):
        self.identities: Dict[IdentityType, ZulipIdentity] = {}
        self.current_identity: Optional[ZulipIdentity] = None
        self.capabilities_cache: Dict[IdentityType, Set[str]] = {}
        self.context_stack: List[IdentityType] = []
    
    async def switch_identity(self, 
                            identity_type: IdentityType, 
                            validate: bool = True) -> bool:
        """Switch to specified identity with validation."""
        
    async def execute_with_identity(self, 
                                  operation_name: str,
                                  params: Dict[str, Any],
                                  func: Callable) -> Dict[str, Any]:
        """Execute function with appropriate identity context."""
        
    def get_current_identity(self) -> ZulipIdentity:
        """Get currently active identity."""
        
    def get_capabilities(self) -> Set[str]:
        """Get capabilities for current identity."""
```

### Identity Types & Capabilities

#### User Identity
```python
USER_CAPABILITIES = {
    "send_message", "read_message", "edit_own_message",
    "add_reaction", "search_messages", "upload_file",
    "subscribe_stream", "create_stream", "get_users",
    "update_own_profile", "get_stream_topics"
}
```

#### Bot Identity  
```python
BOT_CAPABILITIES = {
    "send_message", "read_message", "add_reaction", 
    "search_messages", "stream_events", "schedule_message",
    "bulk_read", "webhook_integration", "automated_response"
}
```

#### Admin Identity
```python
ADMIN_CAPABILITIES = {
    # All user and bot capabilities, plus:
    "manage_users", "manage_streams", "realm_settings",
    "data_export", "organization_settings", "user_groups",
    "delete_messages", "move_messages", "bulk_operations"
}
```

### Usage Patterns

#### Basic Identity Switching
```python
# Get current identity manager
identity_manager = get_identity_manager()

# Switch to bot identity for automation
success = await identity_manager.switch_identity(IdentityType.BOT)
if success:
    # Perform bot operations
    await send_automated_message()

# Switch back to user identity  
await identity_manager.switch_identity(IdentityType.USER)
```

#### Context-Aware Execution
```python
# Execute with specific identity context
result = await identity_manager.execute_with_identity(
    "messaging.send_message",
    {"stream": "general", "content": "Hello"},
    send_message_implementation
)

# Execute with identity override
result = await identity_manager.execute_with_identity(
    "admin.manage_users", 
    {"operation": "activate", "user_id": 123},
    manage_users_implementation,
    preferred_identity=IdentityType.ADMIN
)
```

#### Dynamic Admin Detection
```python
# Check if current identity has admin privileges
if identity_manager.is_admin():
    # Perform admin operations
    await get_organization_info()
```

## Parameter Validation Framework

**Module**: `core/validation/`  
**Purpose**: Progressive parameter disclosure with schema-based validation

### Core Classes

#### ParameterValidator
```python
class ParameterValidator:
    """Progressive parameter validation with schema enforcement."""
    
    def __init__(self):
        self.schemas: Dict[str, ParameterSchema] = {}
        self.mode_hierarchy = [
            ValidationMode.BASIC,
            ValidationMode.ADVANCED, 
            ValidationMode.EXPERT
        ]
    
    def validate_tool_params(self, 
                           tool_name: str, 
                           params: Dict[str, Any],
                           mode: ValidationMode = ValidationMode.BASIC) -> Dict[str, Any]:
        """Validate parameters based on disclosure mode."""
        
    def get_parameter_schema(self, 
                           tool_name: str,
                           mode: ValidationMode) -> ParameterSchema:
        """Get parameter schema for tool and mode."""
        
    def sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters for security."""
```

#### ParameterSchema
```python
@dataclass
class ParameterSchema:
    """Schema definition for tool parameters."""
    
    required_params: Dict[str, ParameterDefinition]
    optional_params: Dict[str, ParameterDefinition]
    advanced_params: Dict[str, ParameterDefinition]
    expert_params: Dict[str, ParameterDefinition]
    
    def validate(self, params: Dict[str, Any], mode: ValidationMode) -> Dict[str, Any]:
        """Validate parameters against schema."""
        
    def get_available_params(self, mode: ValidationMode) -> Set[str]:
        """Get available parameters for validation mode."""
```

### Validation Modes

#### Basic Mode
- **Parameters**: Required only
- **Validation**: Essential parameter checking
- **Use Case**: Simple operations, quick usage

```python
# Basic mode - only required parameters
await message("send", "stream", "general", "Hello world!")
```

#### Advanced Mode  
- **Parameters**: Required + common optional parameters
- **Validation**: Extended parameter checking
- **Use Case**: Most common operations

```python  
# Advanced mode - includes topic and formatting
await message("send", "stream", "general", "**Important** message",
              topic="announcements", validation_mode=ValidationMode.ADVANCED)
```

#### Expert Mode
- **Parameters**: All available parameters
- **Validation**: Complete parameter validation
- **Use Case**: Full feature access, complex operations

```python
# Expert mode - all parameters available
await message("send", "stream", "general", "📢 System Update",
              topic="maintenance", cross_post_streams=["development"],
              schedule_at=datetime(2024, 2, 1, 14, 0),
              disable_notifications=False, widget_content=survey_data,
              validation_mode=ValidationMode.EXPERT)
```

### Validation Pipeline

```python
def validation_pipeline(tool_name: str, params: Dict, mode: ValidationMode) -> Dict:
    """Complete validation pipeline."""
    
    # 1. Get schema for tool and mode
    schema = get_parameter_schema(tool_name, mode)
    
    # 2. Check required parameters
    validate_required_params(params, schema.required_params)
    
    # 3. Validate parameter types and formats  
    validate_parameter_types(params, schema)
    
    # 4. Check parameter constraints
    validate_parameter_constraints(params, schema)
    
    # 5. Sanitize input data
    sanitized_params = sanitize_parameters(params)
    
    # 6. Apply parameter transformations
    transformed_params = transform_parameters(sanitized_params, schema)
    
    return transformed_params
```

## Error Handling System

**Module**: `core/error_handling.py`  
**Purpose**: Centralized error handling with retry strategies and circuit breakers

### Exception Hierarchy

```python
class ZulipMCPError(Exception):
    """Base exception for ZulipChat MCP errors."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        super().__init__(message)

class ConfigurationError(ZulipMCPError):
    """Configuration-related errors."""
    
class ConnectionError(ZulipMCPError):
    """Network and connection errors."""
    
class ValidationError(ZulipMCPError):
    """Parameter validation errors."""
    
class RateLimitError(ZulipMCPError):
    """API rate limit exceeded."""
    
class AuthenticationError(ZulipMCPError):
    """Authentication and credential errors."""
    
class NotFoundError(ZulipMCPError):
    """Resource not found errors."""
    
class PermissionError(ZulipMCPError):
    """Insufficient permissions."""
    
class CircuitBreakerOpenError(ZulipMCPError):
    """Circuit breaker is open."""
```

### Error Handler

```python
class ErrorHandler:
    """Centralized error handling with retry logic."""
    
    def __init__(self):
        self.retry_configs: Dict[str, RetryConfig] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    async def execute_with_retry(self, 
                               func: Callable,
                               operation_name: str,
                               config: Optional[RetryConfig] = None) -> Any:
        """Execute function with intelligent retry logic."""
        
    def create_error_response(self, 
                            error: Exception,
                            operation_name: str,
                            context: Optional[Dict] = None) -> Dict[str, Any]:
        """Create standardized error response."""
        
    def should_retry(self, error: Exception) -> bool:
        """Determine if error is retryable."""
```

### Retry Strategies

#### RetryConfig
```python
@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_errors: List[Type[Exception]] = field(default_factory=list)
    non_retryable_errors: List[Type[Exception]] = field(default_factory=list)
```

#### Retry Strategy Implementations
```python
class RetryStrategy(Enum):
    EXPONENTIAL = "exponential"  # delay *= backoff_factor^attempt
    LINEAR = "linear"            # delay += backoff_factor * attempt  
    FIXED = "fixed"              # constant delay
    JITTERED = "jittered"        # exponential + random jitter
```

### Rate Limiting

#### RateLimiter
```python
class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, max_requests: int, time_window: float, burst_limit: int = 10):
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_limit = burst_limit
        self.tokens = max_requests
        self.last_refill = time.time()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens, waiting if necessary."""
        
    def is_rate_limited(self) -> bool:
        """Check if rate limited without acquiring tokens."""
```

### Error Response Format

```python
def create_standardized_error_response(error: Exception, operation: str) -> Dict:
    """Create standardized error response."""
    
    return {
        "status": "error",
        "operation": operation,
        "error": sanitize_error_message(str(error)),
        "error_type": error.__class__.__name__,
        "timestamp": datetime.utcnow().isoformat(),
        "retryable": is_retryable_error(error),
        "details": get_safe_error_details(error)
    }
```

## Migration Management

**Module**: `core/migration.py`  
**Purpose**: Backward compatibility and smooth migration from legacy tools

### Migration Framework

#### MigrationManager
```python
class MigrationManager:
    """Manages tool migration and backward compatibility."""
    
    def __init__(self):
        self.tool_migrations: Dict[str, ToolMigration] = {}
        self.warned_tools: Set[str] = set()
        self.deprecated_since: Dict[str, str] = {}
        self.removal_timeline: Dict[str, str] = {}
    
    def migrate_tool_call(self, tool_name: str, params: Dict) -> Tuple[str, Dict]:
        """Migrate legacy tool call to current equivalent."""
        
    def emit_deprecation_warning(self, old_tool: str, new_tool: str):
        """Emit deprecation warning for legacy tool usage."""
        
    def is_tool_deprecated(self, tool_name: str) -> bool:
        """Check if tool is deprecated."""
```

#### ToolMigration
```python
@dataclass
class ToolMigration:
    """Migration configuration for a legacy tool."""
    
    old_name: str
    new_name: str
    new_params: Dict[str, Any]  # Fixed parameters for new tool
    param_mapping: Dict[str, str]  # old_param -> new_param
    status: MigrationStatus
    deprecated_since: str
    removal_version: str
    migration_notes: Optional[str] = None
    
    def migrate_parameters(self, old_params: Dict) -> Dict:
        """Transform old parameters to new format."""
```

### Migration Patterns

#### Parameter Mapping
```python
# Example migration: send_message -> messaging.message
migration = ToolMigration(
    old_name="send_message",
    new_name="messaging.message", 
    new_params={"operation": "send"},
    param_mapping={
        "message_type": "type",
        "stream": "to", 
        "private_recipients": "to",
        "subject": "topic"
    },
    status=MigrationStatus.DEPRECATED,
    deprecated_since="2.5.0",
    removal_version="3.0.0"
)
```

#### Complex Parameter Transformations
```python
def migrate_search_parameters(old_params: Dict) -> Dict:
    """Complex migration for search parameters."""
    
    narrow = []
    
    # Convert stream_name to narrow filter
    if "stream_name" in old_params:
        narrow.append({
            "operator": "stream", 
            "operand": old_params["stream_name"]
        })
    
    # Convert hours_back to after filter
    if "hours_back" in old_params:
        after_time = datetime.now() - timedelta(hours=old_params["hours_back"])
        narrow.append({
            "operator": "after",
            "operand": after_time.isoformat()
        })
    
    return {"narrow": narrow, **other_params}
```

## Cache System

**Module**: `core/cache.py`  
**Purpose**: Multi-level caching for performance optimization

### Cache Architecture

#### MessageCache
```python
class MessageCache:
    """Multi-level caching for Zulip data."""
    
    def __init__(self):
        # Different TTL for different data types
        self.streams_cache = TTLCache(maxsize=1000, ttl=300)    # 5 min
        self.users_cache = TTLCache(maxsize=5000, ttl=600)      # 10 min  
        self.messages_cache = TTLCache(maxsize=10000, ttl=60)   # 1 min
        self.search_cache = TTLCache(maxsize=1000, ttl=900)     # 15 min
    
    async def get_streams(self, use_cache: bool = True) -> List[Dict]:
        """Get streams with caching."""
        
    async def get_users(self, use_cache: bool = True) -> List[Dict]:
        """Get users with caching."""
        
    def invalidate_cache(self, cache_type: str, key: Optional[str] = None):
        """Invalidate specific cache or cache entry."""
        
    def get_cache_stats(self) -> Dict[str, Dict]:
        """Get cache statistics for monitoring."""
```

### Caching Strategies

#### Cache-Aside Pattern
```python
async def get_stream_data(stream_id: int, use_cache: bool = True) -> Dict:
    """Get stream data with cache-aside pattern."""
    
    cache_key = f"stream:{stream_id}"
    
    if use_cache:
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
    
    # Cache miss - fetch from API
    data = await api_client.get_stream(stream_id)
    
    # Store in cache
    if use_cache and data:
        cache.set(cache_key, data, ttl=300)
    
    return data
```

#### Write-Through Pattern  
```python
async def update_user_data(user_id: int, updates: Dict) -> Dict:
    """Update user data with write-through caching."""
    
    # Update via API
    result = await api_client.update_user(user_id, updates)
    
    if result["status"] == "success":
        # Update cache immediately
        cache_key = f"user:{user_id}"
        updated_data = await api_client.get_user(user_id)
        cache.set(cache_key, updated_data, ttl=600)
    
    return result
```

## Metrics & Logging

**Module**: `utils/logging.py`, `metrics.py`  
**Purpose**: Comprehensive observability with structured logging and metrics

### Structured Logging

#### LogContext Manager
```python
class LogContext:
    """Context manager for structured logging."""
    
    def __init__(self, logger, **context):
        self.logger = logger
        self.context = context
        self.original_context = {}
    
    def __enter__(self):
        # Add context to logger
        for key, value in self.context.items():
            self.original_context[key] = getattr(self.logger, key, None)
            setattr(self.logger, key, value)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original context
        for key, value in self.original_context.items():
            if value is None:
                delattr(self.logger, key)
            else:
                setattr(self.logger, key, value)
```

#### Usage Pattern
```python
logger = structlog.get_logger("zulipchat_mcp")

with LogContext(logger, tool="messaging", operation="send", user_id=123):
    logger.info("Starting message send", recipient="general", topic="test")
    # All logs in this context include tool, operation, user_id
    result = await send_message_implementation()
    logger.info("Message sent successfully", message_id=result["id"])
```

### Metrics Collection

#### MetricsCollector
```python
class MetricsCollector:
    """Prometheus-compatible metrics collection."""
    
    def __init__(self):
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.timers: Dict[str, Dict] = {}
    
    def increment_counter(self, name: str, labels: Optional[Dict] = None):
        """Increment counter metric."""
        
    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """Set gauge metric value."""
        
    def record_histogram(self, name: str, value: float, labels: Optional[Dict] = None):
        """Record histogram value."""
        
    def start_timer(self, name: str, labels: Optional[Dict] = None) -> str:
        """Start timing operation."""
        
    def stop_timer(self, timer_id: str) -> float:
        """Stop timing operation and record duration."""
```

### Health Monitoring

#### HealthMonitor  
```python
class HealthMonitor:
    """System health monitoring and checks."""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.last_check_results: Dict[str, HealthCheckResult] = {}
    
    async def perform_health_check(self) -> HealthStatus:
        """Perform all registered health checks."""
        
    def register_health_check(self, name: str, check: HealthCheck):
        """Register a health check."""
        
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary."""
```

## Component Integration

### Foundation Component Interactions

```python
async def tool_execution_pipeline(tool_name: str, params: Dict) -> Dict:
    """Complete tool execution pipeline using all foundation components."""
    
    try:
        # 1. Parameter validation
        validator = ParameterValidator()
        validated_params = validator.validate_tool_params(
            tool_name, params, ValidationMode.BASIC
        )
        
        # 2. Identity management
        identity_manager = get_identity_manager()
        current_identity = identity_manager.get_current_identity()
        
        # 3. Check capabilities
        required_capabilities = get_required_capabilities(tool_name)
        if not current_identity.has_capabilities(required_capabilities):
            raise PermissionError(f"Insufficient permissions for {tool_name}")
        
        # 4. Execute with error handling
        error_handler = get_error_handler()
        result = await error_handler.execute_with_retry(
            lambda: execute_tool(tool_name, validated_params),
            operation_name=tool_name
        )
        
        # 5. Metrics and logging
        metrics.increment_counter("tool_calls", {"tool": tool_name})
        logger.info("Tool executed successfully", tool=tool_name)
        
        return result
        
    except Exception as e:
        # Error handling and metrics
        metrics.increment_counter("tool_errors", {"tool": tool_name, "error": type(e).__name__})
        logger.error("Tool execution failed", tool=tool_name, error=str(e))
        
        # Create standardized error response
        return create_error_response(e, tool_name)
```

## Extension & Customization

### Custom Identity Types
```python
class CustomIdentity(ZulipIdentity):
    """Custom identity type with specific capabilities."""
    
    def get_capabilities(self) -> Set[str]:
        return {
            "custom_operation",
            "specialized_access",
            *super().get_capabilities()
        }
    
    def validate_credentials(self) -> bool:
        # Custom validation logic
        return custom_validation_check(self.api_key)

# Register custom identity
identity_manager.register_identity_type(IdentityType.CUSTOM, CustomIdentity)
```

### Custom Validation Rules
```python
class CustomValidator(ParameterValidator):
    """Custom parameter validator with domain-specific rules."""
    
    def validate_custom_parameters(self, params: Dict) -> Dict:
        # Custom validation logic
        if "custom_field" in params:
            self.validate_custom_field(params["custom_field"])
        return params

# Register custom validator
validator_registry.register("custom_tool", CustomValidator())
```

### Custom Error Handlers
```python
class CustomErrorHandler(ErrorHandler):
    """Custom error handler with specialized retry logic."""
    
    def should_retry(self, error: Exception) -> bool:
        # Custom retry logic
        if isinstance(error, CustomError):
            return error.is_transient
        return super().should_retry(error)

# Use custom error handler
error_handler = CustomErrorHandler()
```

---

The foundation components provide a robust, extensible infrastructure that supports the complex requirements of multi-identity operations, progressive disclosure, and enterprise-grade reliability. These components work together seamlessly to provide a consistent, high-quality developer experience across all tool categories.

**Next**: [API Reference](../api-reference/) - Detailed API documentation for all tool categories