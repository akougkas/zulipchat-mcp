# Known Issues - ZulipChat MCP v2.5.0

**Status**: Non-blocking issues for future enhancement  
**Purpose**: Document advanced functionality limitations and edge cases  
**Priority**: Post-ship improvements

## Advanced Feature Limitations

### ISSUE-001: Complex Search Aggregations
**Impact**: Limited analytical capabilities for power users  
**Category**: Enhancement

**Description**: Advanced search with multiple aggregation types may have performance or accuracy limitations when processing large message datasets.

**Affected**: `advanced_search` with complex `aggregations` parameter combinations

### ISSUE-002: Event System Scalability  
**Impact**: Performance degradation under high message volume  
**Category**: Performance

**Description**: Event registration and polling may not scale efficiently for organizations with high message throughput (>1000 messages/hour).

**Affected**: `register_events`, `listen_events` with long-running subscriptions

### ISSUE-003: File Upload Progress Tracking
**Impact**: Limited visibility during large file operations  
**Category**: UX Enhancement

**Description**: File upload operations lack granular progress reporting for files >10MB.

**Affected**: `upload_file` with large attachments

### ISSUE-004: Cross-Stream Analytics Correlation
**Impact**: Limited multi-stream insights  
**Category**: Analytics Enhancement

**Description**: Analytics tools process streams independently, lacking cross-stream correlation metrics for organization-wide insights.

**Affected**: `analytics`, `stream_analytics` with multiple stream analysis

### ISSUE-005: Bulk Operation Batching Limits
**Impact**: May hit API rate limits on large operations  
**Category**: Scalability

**Description**: Bulk operations on >100 items may exceed API rate limits or timeout constraints.

**Affected**: `bulk_operations` with large message ID arrays

### ISSUE-006: Custom Emoji Support Gaps
**Impact**: Limited emoji ecosystem integration  
**Category**: Feature Gap

**Description**: Custom organization emoji management and validation may have edge cases with non-standard emoji formats.

**Affected**: `add_reaction`, custom emoji operations

### ISSUE-007: Admin Operation Error Recovery
**Impact**: Incomplete rollback on failed admin operations  
**Category**: Robustness

**Description**: Complex admin operations (user role changes, stream restructuring) may leave partial state if interrupted.

**Affected**: `admin_operations_tool` with multi-step operations

## Planned Enhancements

- **Message Threading**: Enhanced support for message thread navigation
- **Rich Media Handling**: Improved processing of embedded content and attachments  
- **Mobile Optimization**: Performance tuning for mobile Claude Code usage
- **Webhook Integration**: Real-time webhook support for external integrations

## Notes

These issues represent opportunities for future enhancement rather than blocking bugs. The core MCP functionality remains solid for standard use cases. Priority should be given to resolving issues in BUGS.md before addressing these enhancements.