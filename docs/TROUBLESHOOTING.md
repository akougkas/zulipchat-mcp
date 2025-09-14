# Troubleshooting Guide

Comprehensive troubleshooting guide for ZulipChat MCP covering common issues, error scenarios, debugging procedures, and operational support.

## Quick Diagnostics Checklist

When experiencing issues, start with these basic checks:

- [ ] **Server Status**: Is the MCP server running?
- [ ] **Configuration**: Are all required environment variables set?  
- [ ] **Authentication**: Can you connect to Zulip with provided credentials?
- [ ] **Network**: Is there connectivity to the Zulip server?
- [ ] **Permissions**: Does the current identity have required capabilities?
- [ ] **Rate Limits**: Are you hitting API rate limits?

## Common Error Scenarios

### Authentication Errors

#### Symptoms
- `401 Unauthorized` responses from Zulip API
- "Authentication failed" error messages
- Tools fail immediately without retry

#### Causes & Solutions

**Invalid API Key**:
```bash
# Problem: API key is incorrect or expired
Error: 401 Unauthorized - Invalid API key

# Solution: Verify and regenerate API key
1. Login to your Zulip organization
2. Go to Personal Settings → Account & Privacy
3. Generate new API key
4. Update environment variable:
   export ZULIP_API_KEY="new_api_key_here"
```

**Email/Site Mismatch**:
```bash
# Problem: Email doesn't match the Zulip site
Error: Authentication failed for user@example.com

# Solution: Verify email and site configuration
echo "Email: $ZULIP_EMAIL"
echo "Site: $ZULIP_SITE" 
# Ensure email is registered on the Zulip site
```

**Bot vs User Credentials**:
```python
# Problem: Using bot credentials for user operations
{
    "status": "error",
    "error": "Bot identity cannot perform user operations",
    "error_type": "PermissionError"
}

# Solution: Switch to appropriate identity
await switch_identity("user")  # For interactive operations
await switch_identity("bot")   # For automated operations
```

#### Diagnostic Commands
```bash
# Test authentication directly
curl -u "$ZULIP_EMAIL:$ZULIP_API_KEY" \
     "$ZULIP_SITE/api/v1/users/me"

# Test with Python
python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
result = client.client.get_profile()
print(f'Authenticated as: {result[\"full_name\"]}')
"
```

### Network Connectivity Issues

#### Symptoms
- `ConnectionError` exceptions
- Timeouts on API calls
- Intermittent failures with automatic retries

#### Causes & Solutions

**Network Interruption**:
```bash
# Diagnostic: Test basic connectivity
ping $(echo $ZULIP_SITE | sed 's|https://||')

# Expected: Successful ping responses
# If fails: Check network connection and DNS
```

**HTTPS/SSL Issues**:
```bash
# Diagnostic: Test HTTPS connectivity
curl -I "$ZULIP_SITE/api/v1/server_settings"

# Expected: HTTP 200 OK
# If fails: Check SSL certificates and proxy settings
```

**Firewall/Proxy Blocking**:
```bash
# Problem: Corporate firewall blocks Zulip
Error: Connection timeout

# Solution: Configure proxy settings
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=https://proxy.company.com:8080

# Or whitelist Zulip domains in firewall
```

#### Connection Diagnostics Script
```python
async def diagnose_connectivity():
    """Comprehensive connectivity diagnostics."""
    
    results = {}
    
    # Test DNS resolution
    try:
        import socket
        site_host = ZULIP_SITE.replace('https://', '').replace('http://', '')
        socket.gethostbyname(site_host)
        results["dns_resolution"] = "✅ Success"
    except Exception as e:
        results["dns_resolution"] = f"❌ Failed: {e}"
    
    # Test HTTPS connection
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ZULIP_SITE}/api/v1/server_settings")
            results["https_connection"] = f"✅ Status: {response.status_code}"
    except Exception as e:
        results["https_connection"] = f"❌ Failed: {e}"
    
    # Test authentication
    try:
        from src.zulipchat_mcp.core.client import ZulipClientWrapper
        from src.zulipchat_mcp.config import ConfigManager
        config = ConfigManager()
        client = ZulipClientWrapper(config)
        profile = client.client.get_profile()
        results["authentication"] = f"✅ Logged in as: {profile['full_name']}"
    except Exception as e:
        results["authentication"] = f"❌ Failed: {e}"
    
    return results
```

### Rate Limiting Errors

#### Symptoms
- `RateLimitError` with `retry_after` value
- `429 Too Many Requests` responses  
- Automatic delays between operations

#### Causes & Solutions

**API Rate Limit Exceeded**:
```python
# Error response
{
    "status": "error",
    "error": "Rate limit exceeded. Try again in 60 seconds",
    "error_type": "RateLimitError",
    "retry_after": 60,
    "retryable": True
}

# Solution: Implement exponential backoff
import asyncio

async def with_retry(operation):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            return await operation()
        except RateLimitError as e:
            if attempt == max_attempts - 1:
                raise
            wait_time = e.retry_after or (2 ** attempt)
            await asyncio.sleep(wait_time)
```

**Burst Activity Without Throttling**:
```python
# Problem: Too many requests in short time
# Solution: Use bulk operations and caching

# Instead of multiple individual calls
for user_id in user_ids:
    await manage_users("get", user_id=user_id)  # ❌ Rate limited

# Use bulk approach or caching
users = await manage_users("list")  # ✅ Single call
user_map = {u["user_id"]: u for u in users["users"]}
```

#### Rate Limit Configuration
```python
# Note: Advanced rate limiter configuration not yet implemented
# Current rate limiting is handled by the Zulip API server
# Basic retry logic is built into the client wrapper

# For now, handle rate limits with delays:
import asyncio
await asyncio.sleep(1)  # Add delay between requests if needed
```

### Configuration Errors

#### Symptoms
- Server fails to start
- "Invalid configuration" errors
- Missing required parameters

#### Causes & Solutions

**Missing Environment Variables**:
```bash
# Problem: Required variables not set
Error: Missing required environment variable: ZULIP_EMAIL

# Solution: Set all required variables
export ZULIP_EMAIL="your@email.com"
export ZULIP_API_KEY="your_api_key"  
export ZULIP_SITE="https://yourorg.zulipchat.com"

# Verify they're set
env | grep ZULIP
```

**Malformed URLs**:
```bash
# Problem: URL missing protocol
export ZULIP_SITE="yourorg.zulipchat.com"  # ❌ Missing https://

# Solution: Include protocol
export ZULIP_SITE="https://yourorg.zulipchat.com"  # ✅ Correct
```

**Bot Configuration Issues**:
```bash
# Problem: Bot credentials incomplete
export ZULIP_BOT_EMAIL="bot@example.com"
# Missing: ZULIP_BOT_API_KEY

# Solution: Set all bot variables or none
export ZULIP_BOT_EMAIL="bot@example.com" 
export ZULIP_BOT_API_KEY="bot_api_key"
export ZULIP_BOT_NAME="My Assistant Bot"
```

#### Configuration Validator
```python
async def validate_configuration():
    """Validate all configuration settings."""
    
    issues = []
    
    # Check required variables
    required_vars = ["ZULIP_EMAIL", "ZULIP_API_KEY", "ZULIP_SITE"]
    for var in required_vars:
        if not os.getenv(var):
            issues.append(f"Missing required variable: {var}")
    
    # Validate email format
    email = os.getenv("ZULIP_EMAIL")
    if email and "@" not in email:
        issues.append("ZULIP_EMAIL must be valid email address")
    
    # Validate URL format  
    site = os.getenv("ZULIP_SITE")
    if site and not site.startswith(("http://", "https://")):
        issues.append("ZULIP_SITE must include http:// or https://")
    
    # Check bot configuration consistency
    bot_vars = ["ZULIP_BOT_EMAIL", "ZULIP_BOT_API_KEY"]
    bot_configured = [bool(os.getenv(var)) for var in bot_vars]
    if any(bot_configured) and not all(bot_configured):
        issues.append("Incomplete bot configuration - set all bot variables or none")
    
    return issues
```

### Tool-Specific Errors

#### Message Send Failures

**Stream Not Found**:
```python
# Error
{
    "status": "error",
    "error": "Stream 'nonexistent' not found",
    "error_type": "NotFoundError"
}

# Solutions:
1. Verify stream name spelling
2. Check if stream is private/invite-only
3. Ensure current user has access
4. List available streams:
   streams = await manage_streams("list")
```

**Permission Denied**:
```python
# Error  
{
    "status": "error",
    "error": "Insufficient permissions to post in stream",
    "error_type": "PermissionError"
}

# Solutions:
1. Check stream post policy
2. Verify user is subscribed to stream
3. Switch to admin identity if available:
   await switch_identity("admin")
```

**Message Too Large**:
```python
# Error
{
    "status": "error", 
    "error": "Message content exceeds 50KB limit",
    "error_type": "ValidationError"
}

# Solution: Truncate message or upload as file
if len(content) > 50000:
    # Upload as file instead
    file_result = await upload_file(content.encode(), "large_message.txt")
    content = f"Large message uploaded: {file_result['url']}"
```

#### Search Failures

**Invalid Search Syntax**:
```python
# Problem: Invalid narrow syntax
await search_messages([{"operator": "invalid", "operand": "test"}])

# Solution: Use valid operators
valid_operators = [
    "stream", "topic", "sender", "search", "has", "is",
    "after", "before", "near", "id"
]

# Example: 
await search_messages([
    {"operator": "stream", "operand": "general"},
    {"operator": "search", "operand": "python"}
])
```

**No Results Found**:
```python
# Not an error, but empty results
{
    "status": "success",
    "messages": [],
    "total_results": 0
}

# Solutions:
1. Broaden search criteria
2. Check date ranges
3. Verify stream access
4. Use simpler search terms
```

### Identity & Permission Errors

#### Identity Switch Failed

**Missing Bot Credentials**:
```python
# Error
{
    "status": "error",
    "error": "Bot credentials not configured", 
    "error_type": "ConfigurationError",
    "missing_config": ["ZULIP_BOT_EMAIL", "ZULIP_BOT_API_KEY"]
}

# Solution: Configure bot credentials or use user identity
export ZULIP_BOT_EMAIL="bot@example.com"
export ZULIP_BOT_API_KEY="bot_api_key"
```

**Admin Privileges Required**:
```python
# Error
{
    "status": "error",
    "error": "Admin privileges required for this operation",
    "error_type": "PermissionError", 
    "required_identity": "admin"
}

# Solution: Check admin status and switch identity
status = await switch_identity("user", operation="status") 
if "admin" in status["available_identities"]:
    await switch_identity("admin")
else:
    # Use alternative approach or request admin access
```

## Debugging Procedures

### Enable Debug Logging

**Via CLI Arguments**:
```bash
python -m zulipchat_mcp.server --debug \
  --zulip-email user@example.com \
  --zulip-api-key api_key \
  --zulip-site https://org.zulipchat.com
```

**Via Environment Variable**:
```bash
export MCP_DEBUG=true
python -m zulipchat_mcp.server
```

**Programmatically**:
```python
from src.zulipchat_mcp.utils.logging import setup_structured_logging
setup_structured_logging(level="DEBUG")
```

### Debug Log Analysis

**Find Error Patterns**:
```bash
# Count errors by type (requires jq)
grep "ERROR" logs.json | jq '.error_type' | sort | uniq -c

# Find failed operations
grep "status.*error" logs.json | jq '.operation'

# Track retry attempts
grep "retry" logs.json | wc -l
```

**Performance Analysis**:
```bash
# Find slow operations (>1 second)
grep "duration_ms" logs.json | jq 'select(.duration_ms > 1000)'

# Calculate average response times
grep "api_call_duration" logs.json | \
  jq '.duration_ms' | \
  awk '{sum+=$1} END {print sum/NR " ms average"}'
```

### Health Check System

> ⚠️ **IMPORTANT**: Health checks exist but are NOT exposed through MCP. They can only be used programmatically within the server code.

**Available Health Checks** (internal only):
- `config_validation`: Validates ConfigManager settings
- `cache_operational`: Tests message cache functionality
- `metrics_operational`: Checks if metrics are being collected

**Note**: There is NO Zulip connection health check, NO performance monitoring, and NO exposed health endpoints.

**Manual Health Check** (requires code access):
```python
# This only works if you have direct Python access to the server
# NOT available through MCP tools
# Note: Health check module not yet fully implemented

# Basic health checks you can perform manually:
from src.zulipchat_mcp.config import ConfigManager
from src.zulipchat_mcp.core.client import ZulipClientWrapper

config = ConfigManager()
if config.validate_config():
    print("✅ Config validation: OK")
else:
    print("❌ Config validation: FAILED")

try:
    client = ZulipClientWrapper(config)
    client.client.get_profile()
    print("✅ Zulip connection: OK")
except Exception as e:
    print(f"❌ Zulip connection: FAILED - {e}")
```

**Actual Health Check Response** (simplified):
```json
{
    "status": "healthy|degraded|unhealthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "duration_ms": 125.5,
    "checks": {
        "config_validation": {
            "healthy": true,
            "status": "pass",
            "critical": true
        },
        "cache_operational": {
            "healthy": true,
            "status": "pass",
            "critical": false
        },
        "metrics_operational": {
            "healthy": true,
            "status": "pass",
            "critical": false
        }
    },
    "metrics": {
        "uptime_seconds": 3600,
        "total_requests": 0  // Sum of empty counters
    }
}
```

### Performance Diagnostics

> ⚠️ **NOTE**: Performance metrics are collected but NOT exposed through MCP tools. The metrics module exists but has limited functionality.

**What's Actually Available**:
- Basic counters for tool calls and errors (internal tracking)
- Simple timer decorators for measuring durations
- No exposed metrics endpoints or dashboards

**Reality Check**:
```python
# The metrics module exists but:
# - get_metrics() is not a public function
# - No histogram tracking for response times
# - No cache statistics API
# - Metrics are only accessible through internal code

# What you CAN do:
# Enable debug logging to see timing information
export MCP_DEBUG=true
uv run python -m src.zulipchat_mcp.server --debug
# Then check stderr output for timing logs
```

**Identify Slow Operations**:
```python
# Find operations taking >5 seconds
slow_ops = []
for op_name, times in histograms.items():
    max_time = times.get("max", 0)
    if max_time > 5000:  # 5 seconds
        slow_ops.append({
            "operation": op_name,
            "max_time_ms": max_time,
            "avg_time_ms": times.get("avg", 0)
        })

print("Slow operations:", slow_ops)
```

## Recovery Procedures

### Automatic Recovery

**Retry Logic**:
The system automatically retries failed operations:
- **Retryable errors**: Connection errors, rate limits, timeouts
- **Non-retryable errors**: Authentication, validation, permission errors
- **Retry strategy**: Exponential backoff with jitter
- **Max attempts**: 3 (configurable)

**Circuit Breaker**:
> ⚠️ **NOTE**: Circuit breaker was removed from v2.5.0 as "over-engineering for MCP adapter pattern". The code comment states MCP servers should be stateless adapters.

### Manual Recovery

**Clear Message Cache** (if implemented):
```python
# Note: Cache clearing not yet implemented
# Current caching is handled by DuckDB and client wrapper
# To clear cache, restart the server or delete database files

# Database files are typically in:
# - ~/.cache/zulipchat-mcp/ (if using XDG dirs)
# - ./zulipchat_mcp.db (local file)

# Restart the server to clear in-memory caches
```

**Restart Server**:
```bash
# The most reliable way to recover from persistent errors
# is to restart the MCP server
# Ctrl+C to stop, then restart with:
uv run python -m src.zulipchat_mcp.server \
  --zulip-email $ZULIP_EMAIL \
  --zulip-api-key $ZULIP_API_KEY \
  --zulip-site $ZULIP_SITE
```

### Graceful Degradation

**Cache Fallback**:
```python
# System automatically falls back to cached data when API fails
try:
    streams = await manage_streams("list", use_cache=False)  # Fresh data
except ConnectionError:
    streams = await manage_streams("list", use_cache=True)   # Cached data
    logger.warning("Using cached stream data due to connection error")
```

**Partial Results**:
```python
# Bulk operations continue processing even if some items fail
result = await bulk_operations("mark_read", narrow=[...])

successful = result["successful_operations"]
failed = result["failed_operations"]

# Process successful results, handle failures separately
```

## Monitoring & Alerting

### Key Metrics to Monitor

**Availability Metrics**:
- Health check status
- Uptime percentage  
- Error rate (should be <5%)
- Authentication success rate

**Performance Metrics**:
- Response time percentiles (p50, p95, p99)
- Throughput (requests per second)
- Cache hit rates (should be >80%)
- Queue depths

**Resource Metrics**:
- Memory usage
- Connection pool utilization
- File storage usage

### Alerting Thresholds

**Critical Alerts** (immediate attention):
- Health check failure
- Error rate >10%
- Authentication failure
- Response time p95 >10 seconds

**Warning Alerts** (investigation needed):
- Error rate >5%
- Cache hit rate <50%
- Response time p95 >5 seconds
- Memory usage >80%

### Monitoring Setup

**Prometheus Integration**:
```python
# Metrics are automatically exported in Prometheus format
# Available at: http://localhost:3000/metrics

# Key metrics:
# - zulipchat_mcp_requests_total
# - zulipchat_mcp_request_duration_seconds  
# - zulipchat_mcp_errors_total
# - zulipchat_mcp_cache_hits_total
```

**Log Monitoring**:
```bash
# Monitor error logs
tail -f logs.json | grep '"level":"error"'

# Monitor performance issues  
tail -f logs.json | jq 'select(.duration_ms > 1000)'

# Monitor authentication issues
tail -f logs.json | grep -i auth
```

## Support Resources

### Self-Diagnosis Tools

**System Status Check**:
```bash
# Quick system status
python -c "
from src.zulipchat_mcp.utils.health import perform_health_check
import asyncio
result = asyncio.run(perform_health_check()) 
print(f'Status: {result[\"status\"]}')
"
```

**Configuration Audit**:
```bash
# Check configuration completeness
python -c "
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
issues = config.validate_config()
print('Configuration issues:', issues or 'None')
"
```

**Connectivity Test**:
```bash
# Test Zulip API connectivity
python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
try:
    client = ZulipClientWrapper()
    profile = client.client.get_profile()
    print(f'✅ Connected as {profile[\"full_name\"]}')
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

### Getting Help

**Information to Provide**:
When reporting issues, include:
- Error messages (full stack trace if available)
- Configuration (sanitized, no API keys)
- Health check output
- Recent log entries
- Steps to reproduce the issue

**Log Sanitization**:
```bash
# Remove sensitive information from logs before sharing
grep -v "api_key\|password\|secret" logs.json | \
sed 's/[a-zA-Z0-9._%+-]\+@[a-zA-Z0-9.-]\+\.[a-zA-Z]\{2,\}/***EMAIL***/g'
```

### Emergency Procedures

**Service Degradation**:
1. Check health status and error rates
2. Review recent configuration changes
3. Check Zulip server status
4. Restart service if necessary
5. Enable cache fallback mode

**Complete Service Failure**:
1. Verify basic connectivity (DNS, HTTPS)
2. Check authentication credentials  
3. Review configuration for errors
4. Restart with debug logging enabled
5. Check for breaking changes in Zulip API

**Security Incident**:
1. Rotate API keys immediately
2. Review access logs for suspicious activity
3. Check for unauthorized configuration changes
4. Enable additional authentication if available
5. Contact security team if breach suspected

---

This troubleshooting guide covers the most common issues with ZulipChat MCP v2.5.0. For additional help, consult the [API Reference](api-reference/) documentation or seek community support.

**Related**: [Configuration Guide](user-guide/configuration.md) | [Migration Guide](migration-guide.md)