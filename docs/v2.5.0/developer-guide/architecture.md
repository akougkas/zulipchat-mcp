# Architecture Overview

ZulipChat MCP v2.5.0 implements a layered architecture with identity-aware operations, progressive disclosure, and comprehensive error handling. This document provides a complete architectural overview for developers.

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                 MCP Protocol Layer                  │
├─────────────────────────────────────────────────────┤
│              Tool Categories (7)                    │
│  Messaging │ Streams │ Events │ Users │ Search │    │
│            Files │ Admin                           │
├─────────────────────────────────────────────────────┤
│                 Foundation Layer                    │
│  Identity │ Validation │ Error Handling │ Migration │
├─────────────────────────────────────────────────────┤
│                 Core Infrastructure                 │
│  Client │ Cache │ Logging │ Metrics │ Health       │
├─────────────────────────────────────────────────────┤
│                 Zulip API Integration               │
└─────────────────────────────────────────────────────┘
```

## Core Architectural Principles

### 1. Identity-Aware Operations
Every operation is executed with a specific identity context:
- **User Identity**: Interactive operations with standard permissions
- **Bot Identity**: Automated operations with programmatic capabilities  
- **Admin Identity**: Administrative operations with full access

### 2. Progressive Disclosure
Parameters and functionality are revealed progressively:
- **Basic Mode**: Essential parameters only
- **Advanced Mode**: Extended functionality
- **Expert Mode**: Full feature access

### 3. Stateless Design
- No server-side session state
- Each operation is self-contained
- Caching for performance, not state management

### 4. Async-First Architecture
- All I/O operations use async/await
- Non-blocking execution throughout
- Efficient resource utilization

## Foundation Layer Components

### Identity Management (`core/identity.py`)

```python
class IdentityManager:
    """Manages multiple Zulip identities with dynamic switching."""
    
    def __init__(self):
        self.identities: Dict[IdentityType, ZulipIdentity] = {}
        self.current_identity: Optional[ZulipIdentity] = None
        self.capabilities_cache: Dict[IdentityType, Set[str]] = {}
    
    async def switch_identity(self, identity_type: IdentityType) -> bool:
        """Switch to specified identity with validation."""
        
    async def execute_with_identity(self, operation_name: str, 
                                   params: Dict, func: Callable) -> Dict:
        """Execute operation with appropriate identity context."""
```

**Key Features:**
- Dynamic identity switching with validation
- Capability-based access control
- Context preservation across operations
- Automatic admin privilege detection

### Parameter Validation (`core/validation/`)

```python
class ParameterValidator:
    """Progressive parameter validation with schema enforcement."""
    
    def __init__(self):
        self.schemas: Dict[str, ParameterSchema] = {}
        self.mode_hierarchy = [ValidationMode.BASIC, 
                              ValidationMode.ADVANCED, 
                              ValidationMode.EXPERT]
    
    def validate_tool_params(self, tool_name: str, params: Dict, 
                           mode: ValidationMode = ValidationMode.BASIC) -> Dict:
        """Validate parameters based on disclosure mode."""
```

**Validation Modes:**
- **BASIC**: Required parameters only
- **ADVANCED**: Optional parameters with common use cases
- **EXPERT**: All parameters with full validation

### Error Handling (`core/error_handling.py`)

```python
class ErrorHandler:
    """Centralized error handling with retry strategies."""
    
    async def execute_with_retry(self, func: Callable, 
                               operation_name: str,
                               config: Optional[RetryConfig] = None) -> Any:
        """Execute function with intelligent retry logic."""
        
    def create_error_response(self, error: Exception, 
                            operation_name: str,
                            context: Optional[Dict] = None) -> Dict:
        """Create standardized error responses."""
```

**Retry Strategies:**
- `EXPONENTIAL`: Exponential backoff (default)
- `LINEAR`: Linear delay increase
- `FIXED`: Constant delay
- `JITTERED`: Exponential with randomization

### Migration System (`core/migration.py`)

```python
class MigrationManager:
    """Manages backward compatibility and tool migration."""
    
    def __init__(self):
        self.tool_migrations: Dict[str, ToolMigration] = {}
        self.warned_tools: Set[str] = set()
    
    def migrate_tool_call(self, tool_name: str, params: Dict) -> Tuple[str, Dict]:
        """Migrate legacy tool call to v2.5.0 equivalent."""
        
    def _migrate_params(self, migration: ToolMigration, old_params: Dict) -> Dict:
        """Transform parameters from legacy to new format."""
```

**Migration Features:**
- Automatic parameter transformation
- Deprecation warnings
- Legacy tool mapping  
- Timeline-based removal

## Core Infrastructure

### Zulip Client Wrapper (`core/client.py`)

```python
class ZulipClientWrapper:
    """Enhanced Zulip client with caching and error handling."""
    
    def __init__(self, email: str, api_key: str, site: str):
        self.client = zulip.Client(email=email, api_key=api_key, site=site)
        self.cache = MessageCache()
        self.rate_limiter = RateLimiter()
    
    async def call_api(self, method: str, params: Dict) -> Dict:
        """Make API call with caching and rate limiting."""
```

**Features:**
- Connection pooling and keep-alive
- Automatic retry on transient failures
- Response caching with TTL
- Rate limiting with backoff

### Caching System (`core/cache.py`)

```python
class MessageCache:
    """Multi-level caching for Zulip data."""
    
    def __init__(self):
        self.streams_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)
        self.users_cache: TTLCache = TTLCache(maxsize=5000, ttl=600)
        self.messages_cache: TTLCache = TTLCache(maxsize=10000, ttl=60)
    
    async def get_streams(self, use_cache: bool = True) -> List[Dict]:
        """Get streams with optional caching."""
```

**Cache Types:**
- **Streams**: Long TTL (5 minutes), low volatility
- **Users**: Very long TTL (10 minutes), stable data
- **Messages**: Short TTL (1 minute), high volatility
- **Search Results**: Configurable TTL based on query

### Logging & Observability (`utils/logging.py`, `metrics.py`)

```python
# Structured logging with context
logger = structlog.get_logger("zulipchat_mcp")

with LogContext(logger, tool="messaging", operation="send"):
    logger.info("Sending message", recipient="general", topic="test")
    
# Metrics collection
from zulipchat_mcp.metrics import metrics

metrics.increment_counter("tool_calls", labels={"tool": "messaging"})
metrics.record_histogram("response_time", duration_ms, labels={"operation": "send"})
```

**Observability Features:**
- Structured JSON logging
- Context-aware log correlation
- Prometheus metrics collection
- Health check endpoints
- Performance monitoring

## Tool Architecture

### Tool Category Structure

Each tool category follows a consistent pattern:

```python
# tools/messaging_v25.py
@tool
async def message(
    operation: str,  # Required: "send", "schedule", "draft"
    type: str,       # Required: "stream", "private" 
    to: str,         # Required: recipient
    content: str,    # Required: message content
    
    # Advanced parameters
    topic: Optional[str] = None,
    schedule_at: Optional[datetime] = None,
    
    # Expert parameters  
    cross_post_streams: Optional[List[str]] = None,
    disable_notifications: Optional[bool] = None,
    
    # System parameters
    validation_mode: ValidationMode = ValidationMode.BASIC,
    identity_override: Optional[IdentityType] = None
) -> Dict[str, Any]:
    """Send, schedule, or draft messages with progressive disclosure."""
    
    # 1. Parameter validation
    validator = ParameterValidator()
    validated_params = validator.validate_tool_params(
        "messaging.message", locals(), validation_mode
    )
    
    # 2. Identity resolution
    identity_manager = get_identity_manager()
    
    # 3. Operation execution with error handling
    async def _execute_message_operation(client, params):
        # Implementation here
        pass
    
    # 4. Execute with identity and retry logic
    result = await identity_manager.execute_with_identity(
        "messaging.message", validated_params, _execute_message_operation
    )
    
    # 5. Metrics and logging
    track_tool_call("message")
    return result
```

### Common Tool Patterns

#### 1. Parameter Validation Pattern
```python
# Progressive validation
validator = ParameterValidator()
validated = validator.validate_tool_params(tool_name, params, mode)

# Schema-based validation
schema = get_tool_schema(tool_name, mode)
validated = schema.validate(params)
```

#### 2. Identity Execution Pattern
```python
# Execute with appropriate identity
result = await identity_manager.execute_with_identity(
    operation_name, params, execution_function
)

# Identity override for specific operations
result = await identity_manager.execute_with_identity(
    operation_name, params, execution_function,
    preferred_identity=IdentityType.BOT
)
```

#### 3. Error Handling Pattern
```python
try:
    result = await perform_operation()
    track_tool_call(tool_name)
    return result
except Exception as e:
    track_tool_error(tool_name, str(e))
    logger.error(f"Error in {tool_name}: {e}")
    return create_error_response(e, tool_name)
```

## Data Flow Architecture

### Request Processing Flow

```
1. MCP Request → Tool Function
2. Parameter Validation → Progressive Disclosure
3. Identity Resolution → Capability Check
4. Zulip API Call → Rate Limiting + Caching
5. Response Processing → Error Handling
6. Metrics Collection → Logging
7. MCP Response ← Standardized Format
```

### Error Propagation

```
Exception → ErrorHandler → Retry Logic → Rate Limiter → 
Circuit Breaker → Error Response → MCP Client
```

### Caching Strategy

```
Request → Cache Check → Cache Hit?
                     ├─ Yes → Cached Response
                     └─ No → API Call → Cache Store → Response
```

## Performance Characteristics

### Throughput Optimization

1. **Async Operations**: All I/O is non-blocking
2. **Connection Pooling**: Reuse HTTP connections
3. **Caching**: Multi-level caching reduces API calls
4. **Batch Operations**: Bulk operations where supported

### Memory Management

1. **TTL Caches**: Automatic expiration prevents memory leaks
2. **Lazy Loading**: Load data only when needed
3. **Resource Cleanup**: Proper cleanup of connections and caches

### Scalability Considerations

1. **Stateless Design**: Horizontal scaling support
2. **Rate Limiting**: Prevents API abuse
3. **Circuit Breakers**: Fail fast under load
4. **Health Monitoring**: Proactive issue detection

## Security Architecture

### Authentication & Authorization

1. **Multi-Identity Support**: User, bot, and admin contexts
2. **Capability-Based Access**: Dynamic permission checking
3. **Credential Management**: Secure storage and rotation
4. **Context Isolation**: Identity-specific execution contexts

### Data Protection

1. **Input Sanitization**: All parameters validated
2. **Output Filtering**: Sensitive data removal
3. **Audit Logging**: Comprehensive operation tracking
4. **Error Sanitization**: No credential exposure in errors

## Extension Points

### Adding New Tools

1. **Follow Tool Pattern**: Use established patterns
2. **Parameter Schema**: Define progressive disclosure schema
3. **Identity Support**: Implement identity-aware operations
4. **Error Handling**: Use centralized error handling
5. **Testing**: Comprehensive test coverage

### Custom Validation

```python
class CustomValidator(ParameterValidator):
    def validate_custom_params(self, params: Dict) -> Dict:
        # Custom validation logic
        return validated_params

# Register custom validator
register_validator("custom_tool", CustomValidator())
```

### Identity Extension

```python
class CustomIdentity(ZulipIdentity):
    def get_capabilities(self) -> Set[str]:
        # Define custom capabilities
        return {"custom_capability", "special_access"}

# Register custom identity type
identity_manager.register_identity_type(IdentityType.CUSTOM, CustomIdentity)
```

## Deployment Architecture

### Development Environment
- Single process with debug logging
- Hot reloading for development
- Mock services for testing

### Production Environment
- Multi-process deployment
- Load balancing support
- Health monitoring and alerting
- Centralized logging and metrics

### High Availability
- Stateless design enables horizontal scaling
- Circuit breakers prevent cascade failures
- Graceful degradation under load
- Automatic recovery mechanisms

## Migration Architecture

### Backward Compatibility Strategy

1. **Dual Tool Registration**: Legacy and v2.5.0 tools coexist
2. **Parameter Migration**: Automatic parameter transformation
3. **Deprecation Warnings**: User notification system
4. **Timeline Management**: Controlled removal process

### Migration Patterns

```python
# Legacy tool call
legacy_result = send_message("general", "Hello", topic="test")

# Automatic migration to
new_result = message("send", "stream", "general", "Hello", topic="test")

# Parameter transformation
old_params = {"stream_name": "general", "subject": "test"}
new_params = {"to": "general", "topic": "test"}  # Automatic mapping
```

---

This architecture provides a robust, scalable, and maintainable foundation for the ZulipChat MCP server while supporting complex identity management, progressive disclosure, and comprehensive error handling.

**Next**: [Tool Categories](tool-categories.md) - Detailed breakdown of the 7 tool categories