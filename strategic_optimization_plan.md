# ZulipChat MCP v2.5.1 Tool Reliability Optimization

## Mission
Fix tool invocation failures in ZulipChat MCP by addressing type validation, user resolution, and parameter ambiguity issues. Create v2.5.1 on a new branch with comprehensive fixes.

**Core Principle**: Less is more - achieve elegant solutions with minimal code. Every line must justify its existence.

## Current Problems and Bugs

### 1. Type Validation Failures
**Location**: `src/zulipchat_mcp/utils/narrow_helpers.py`
**Problem**: Soft type conversion causes silent failures when AI sends string parameters
**Example**:
```
Input: search_messages(last_days="7")
Error: '7' is not valid under any of the given schemas
```
**Desired Behavior**: Accept both string and integer inputs, validate and convert explicitly with clear error messages

### 2. User Resolution Failures
**Location**: `src/zulipchat_mcp/tools/search_v25.py` (line 307+)
**Problem**: Strict name/email matching - no fuzzy search or partial matches
**Example**:
```
Input: search_messages(sender="Jaime")
Error: Invalid narrow operator: unknown user Jaime
```
**Desired Behavior**: Resolve "Jaime" to "jcernudagarcia@hawk.iit.edu" through fuzzy matching or user lookup
**Zulip API Reality**: The narrow `sender` operator ONLY accepts email addresses, not names (see research in `/tmp/zulip_message_api_analysis.md`)

### 3. Parameter Overload and Ambiguity
**Location**: `src/zulipchat_mcp/tools/messaging_v25.py`, `search_v25.py`
**Problem**: Tools have 15+ optional parameters causing AI confusion
**Example**: `search_messages` has parameters for simple search, advanced search, and narrow filters all mixed together
**Desired Behavior**: Separate focused tools for specific use cases

### 4. Non-Actionable Error Messages
**Location**: Throughout all tool files
**Problem**: Generic error returns without recovery guidance
**Example**:
```
return {"status": "error", "error": "Invalid narrow operator"}
```
**Desired Behavior**: Include suggestions, alternative tools, and parameter corrections

### 5. Identity Confusion
**Context**: From CLAUDE.md - "I am the user Anthony akougkas@iit.edu... YOU are the Claude Code bot and must register to get your own Bot ID"
**Problem**: Tools don't clearly distinguish between user identity and bot identity
**Desired Behavior**: Clear separation of user context vs bot operations

## Expected Outcomes

### Search Operations
- `search_messages(sender="Jaime", last_days=7)` → Returns Jaime's messages from past week
- `search_messages(sender="partial_name")` → Resolves to full user or suggests matches
- `search_messages(time="1 week")` → Parses natural language time expressions

### Error Recovery
- Failed user lookup → Returns list of similar users
- Invalid parameters → Suggests correct format with examples
- Missing required fields → Progressive validation with specific field guidance

### Tool Selection
- AI consistently chooses the right tool variant for the task
- Clear tool descriptions prevent ambiguity
- Focused tools reduce parameter confusion

## Zulip API Research Findings

### Critical Insights from API Investigation
1. **Narrow System Reality** (from `/tmp/zulip_message_api_analysis.md`):
   - The `sender` operator in narrow ONLY accepts email addresses
   - User resolution must happen BEFORE building the narrow
   - Time filters use `after:` and `before:` operators with timestamps
   - Full-text search uses the `search` operator

2. **Type Flexibility** (from `/tmp/zulip_search_patterns.md`):
   - Zulip API is flexible with type conversion
   - Our implementation already has robust type conversion utilities
   - The issue is in our MCP layer, not the Zulip client layer

3. **Missing Features** (from `/tmp/zulip_advanced_features.md`):
   - Scheduled messages are partially implemented but not fully exposed
   - Dual identity (user vs bot) is supported but not clearly distinguished
   - Many advanced features exist but are hidden behind complex parameters

### Simplification Opportunities
- Remove complex type conversion wrappers - Zulip handles this well
- Use Zulip's native search operators directly
- Leverage the `/users` endpoint for name resolution
- Expose scheduled messages as a simple, focused tool

## Implementation Instructions

### Branch Setup
1. Create new branch `feature/v2.5.1-tool-reliability`
2. Target release: v2.5.1 with TestPyPI publishing
3. Maintain backward compatibility with deprecation warnings

### Key Files to Modify

#### Type Validation System
- `src/zulipchat_mcp/utils/narrow_helpers.py` - Fix type conversion
- Add explicit validation with helpful errors
- Support string-to-int conversion for common parameters

#### User Resolution System
- `src/zulipchat_mcp/tools/search_v25.py` - Add user resolution helper
- Implement fuzzy matching for sender names
- Cache user list for performance

#### Tool Simplification
- Create new file: `src/zulipchat_mcp/tools/simple_search.py`
- Extract focused tool variants from complex tools
- Keep original tools with deprecation notices

#### Error Enhancement
- Update all tool return statements in `tools/` directory
- Implement structured error format with recovery hints
- Add suggestion system for common mistakes

### Testing Requirements

Create test file: `tests/test_tool_reliability.py`
Test cases must cover:
1. String parameter conversion ("7" → 7)
2. Fuzzy user matching ("Jaime" → full email)
3. Error message actionability
4. Tool selection accuracy
5. Identity context (user vs bot operations)

### Documentation Updates

- Update tool descriptions with clear examples
- Add parameter interaction documentation
- Document identity model (user vs bot)
- Update README with v2.5.1 improvements

## Version Management

1. Update `pyproject.toml` version to 2.5.1
2. Create comprehensive changelog
3. Tag as v2.5.1 after testing
4. Publish to TestPyPI first, then PyPI

## Success Criteria

- Tool invocation failure rate < 10% (from current ~40%)
- All example queries from this document work correctly
- Backward compatibility maintained
- Tests pass with >90% coverage
- Successfully published to TestPyPI

---

## Appendix: Technical Context and Code Patterns

### Current Type Conversion Pattern (Problematic)
```python
# In narrow_helpers.py
def convert_param(value):
    return int(value) if isinstance(value, str) else value  # Silent failure risk
```

### Suggested Validation Pattern
```python
def validate_and_convert(value, expected_type, param_name):
    """Explicit validation with clear errors."""
    if expected_type == int and isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"{param_name} must be a number, got '{value}'")
    return value
```

### User Resolution Helper Concept
```python
async def resolve_user_identifier(identifier: str, client) -> dict:
    """Resolve partial names, emails, or IDs to full user info."""
    # Try exact email match
    if "@" in identifier:
        return {"email": identifier}

    # Fuzzy match against user list
    users = await client.get_users()
    matches = fuzzy_match(identifier, users)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise AmbiguousUserError(f"Multiple matches for '{identifier}'", matches)
    else:
        raise UserNotFoundError(f"No user matching '{identifier}'")
```

### Focused Tool Variant Example
```python
# Instead of one complex tool, create focused variants
@mcp.tool(description="Get messages from a specific person in the last N days")
async def get_user_messages(sender_name: str, days: int = 7):
    """Simplified, focused tool for common use case."""
    # Implementation details...
```

### Structured Error Format
```python
{
    "status": "error",
    "error": {
        "code": "USER_NOT_FOUND",
        "message": "Could not find user 'Jaime'",
        "suggestions": [
            "Did you mean: Jaime Garcia (jcernudagarcia@hawk.iit.edu)?",
            "Use 'list_users' tool to see all available users"
        ],
        "recovery": {
            "tool": "list_users",
            "params": {"search": "Jaime"}
        }
    }
}
```

### MCP Best Practices References
- Official MCP Spec: https://modelcontextprotocol.io/specification
- FastMCP Documentation: https://github.com/jlowin/fastmcp
- Successful MCP examples: filesystem, git, github MCPs

### Current Tool Registration Pattern
```python
# In server.py
from .tools import register_search_v25_tools
register_search_v25_tools(mcp)  # Complex tools with many parameters
```

### Identity Model Clarification
Per CLAUDE.md requirements:
- User identity: akougkas@iit.edu (message recipient/sender)
- Bot identity: Claude Code bot (needs separate registration)
- Tools must respect this dual identity model