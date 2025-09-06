# AGENTS.md

AI agent instructions for ZulipChat MCP Server development.

## Project Overview

ZulipChat MCP is a **lean Model Context Protocol server** enabling bidirectional communication between AI agents and humans via Zulip. **v2.0 architectural refactor is COMPLETE** with clean separation of concerns and DuckDB persistence.

**Current State**: v2.0 - Clean architecture with 19 MCP tools registered
**Architecture**: `core/utils/services/tools/integrations` pattern with DuckDB persistence
**Status**: ✅ MCP connection works, ❌ Some tool implementations need debugging
**Philosophy**: Simple, maintainable, database-backed persistence

## Quick Start

```bash
# 1. Setup environment (uv handles everything)
uv sync                       # Install dependencies + create venv
# Note: .env credentials auto-loaded from environment

# 2. Test server startup
uv run zulipchat-mcp         # Server initializes DuckDB + starts MCP

# 3. Connect Claude Code to MCP
claude mcp add zulipchat uv run zulipchat-mcp

# 4. Test in Claude Code - try these tools:
# - get_streams (works) ✅
# - register_agent (works) ✅ 
# - get_messages (needs debugging) ❌
```

## Current Status & Next Priorities

### ✅ **COMPLETED (v2.0 Refactor)**

1. **Architecture**: Clean `core/utils/services/tools/integrations` structure
2. **Database**: DuckDB persistence with proper migrations and tables
3. **Server**: FastMCP stdio-only server with 19 registered tools
4. **Integration**: Claude Code successfully connected (`claude mcp add zulipchat`)
5. **Tools Working**: `get_streams`, `register_agent`, database operations

### ❌ **NEEDS DEBUGGING (HIGH PRIORITY)**

1. **Message Tools**: `get_messages`, `search_messages` return generic "unexpected error"
2. **Error Handling**: Tools catch all exceptions and hide real error details
3. **Zulip API**: Core `ZulipClientWrapper` methods may be broken/missing
4. **Authentication**: Environment variables may not be loading correctly

### 🎯 **DEBUGGING PRIORITIES**

**CRITICAL**: Fix message retrieval tools - they're the core functionality

### 🎯 Core Design Principles

- **Single Channel**: All agents use "Agents-Channel" stream
- **Structured Topics**: `agent_type/YYYY-MM-DD/session_id`
- **Runtime AFK**: In-memory flag, not persisted
- **Blocking Wait**: No timeouts on `wait_for_response()`
- **Thin Server**: MCP is protocol layer, not application

## Development Workflow

### Recommended Approach: Explore → Plan → Implement → Test → Commit

```bash
# 1. EXPLORE - Understand current state
tree -I "__pycache__|.git" -L 2    # View structure
grep -r "TODO\|FIXME" src/         # Find issues
uv run pytest --co -q              # List tests

# 2. PLAN - Think before coding
# Create a checklist of changes
# Identify files to modify
# Consider test implications

# 3. IMPLEMENT - Make focused changes
uv run black src/ tests/           # Format first
# Make your changes
uv run ruff check --fix           # Fix linting

# 4. TEST - Verify nothing broke
uv run pytest tests/test_server.py -xvs  # Test specific file
uv run pytest                             # Full test suite

# 5. COMMIT - Clear, atomic commits
git add -p                         # Review changes
git commit -m "type: description" # Use conventional commits
```

## Code Style & Standards

### Essential Rules

```python
# ALWAYS use type hints
def send_message(content: str, require_response: bool = False) -> dict[str, Any]:
    """Clear docstring explaining purpose."""
    
# NEVER exceed 500 lines per file
# If approaching limit, split into logical modules

# ALWAYS handle errors explicitly
try:
    result = client.send_message(...)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    return {"status": "error", "error": "Invalid input"}

# NEVER use print() - use logger
logger.info("Processing message")  # ✓
print("Processing message")        # ✗
```

### Current Architecture (v2.0)

```
src/zulipchat_mcp/
├── server.py                    # Entry point - registers tools only
├── core/                        # Domain logic and primitives
│   ├── client.py               # ZulipClientWrapper (may need debugging)
│   ├── commands/
│   │   ├── engine.py           # Command chain system
│   │   └── workflows.py        # Common workflow patterns
│   ├── agent_tracker.py        # Session tracking
│   ├── security.py             # Input validation
│   ├── exceptions.py           # Custom exceptions
│   └── cache.py               # Caching utilities
├── utils/                       # Cross-cutting utilities
│   ├── database.py             # DuckDB persistence (✅ working)
│   ├── logging.py              # Structured logging
│   ├── metrics.py              # Performance tracking
│   └── health.py              # Health checks
├── services/                    # Long-lived services
│   └── scheduler.py            # Message scheduling
├── tools/                       # MCP tool registrars (19 tools)
│   ├── messaging.py            # send_message, edit_message, add_reaction, get_messages
│   ├── streams.py              # get_streams (✅), create_stream, etc.
│   ├── agents.py               # register_agent (✅), agent lifecycle tools
│   └── search.py               # search_messages, get_daily_summary
└── integrations/                # Agent-specific installers
    ├── registry.py             # CLI: zulipchat-mcp-integrate
    └── claude_code/            # Generates .claude/commands/*.json
```

## Testing Requirements

### Before EVERY Commit

```bash
# 1. Format code
uv run black src/ tests/

# 2. Fix linting
uv run ruff check src/ tests/ --fix

# 3. Type check
uv run mypy src/zulipchat_mcp/

# 4. Run tests
uv run pytest

# 5. Clean artifacts
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

### Test Patterns

```python
# Write focused unit tests
def test_agent_registration():
    """Test that agents get assigned correct topics."""
    result = register_agent("claude-code")
    assert result["stream"] == "Agents-Channel"
    assert "claude-code" in result["topic"]

# Use integration markers
@pytest.mark.integration
def test_full_message_flow():
    """Test complete agent message flow."""
    # Test realistic scenarios
```

## Common Tasks

### Adding a New MCP Tool

```python
# 1. Add to appropriate tools/ file (not server.py!)
@mcp.tool(description="Clear, specific description for agents")
def your_tool(param: str, optional: int = None) -> dict[str, Any]:
    """
    Detailed docstring for other developers.
    
    Args:
        param: What this parameter does
        optional: Optional with sensible default
    """
    # Validate inputs first
    if not validate_input(param):
        return {"status": "error", "error": "Invalid input"}
    
    # Single responsibility - do one thing well
    result = perform_operation(param)
    
    return {"status": "success", "data": result}

# 2. Add test in tests/test_[module].py
def test_your_tool():
    result = your_tool("valid_input")
    assert result["status"] == "success"

# 3. Update documentation
# - Add to README.md tool list
# - Update CHANGELOG.md if significant
```

### Debugging MCP Issues

```bash
# Enable debug logging
export MCP_DEBUG=true

# Test tool directly
uv run python -c "
from src.zulipchat_mcp.tools.agents import register_agent
print(register_agent('test'))
"

# Check MCP server output
uv run zulipchat-mcp 2>&1 | grep -i error
```

## Security & Safety

### NEVER Commit

- `.env` files with real credentials
- API keys in code
- Personal information in tests
- Debug print statements

### ALWAYS Validate

```python
# Sanitize all user inputs
content = sanitize_input(user_content)

# Validate before processing
if not validate_stream_name(stream):
    raise ValidationError(f"Invalid stream: {stream}")

# Use specific exceptions
except ValidationError:  # ✓ Specific
except Exception:       # ✗ Too broad
```

## Performance Guidelines

### Keep It Simple

- **No premature optimization** - Clarity > Performance
- **Synchronous by default** - Async only when proven necessary
- **File-based state** - JSON files are fine for our scale
- **Batch when obvious** - But don't over-engineer

### Resource Management

```python
# Use context managers
with open(file_path) as f:
    data = json.load(f)

# Clean up explicitly
finally:
    if client:
        client.close()
```

## PR Checklist

Before submitting any PR:

- [ ] Code formatted with `black`
- [ ] Linting passes with `ruff`
- [ ] Type checking passes with `mypy`
- [ ] All tests pass
- [ ] No files >500 lines
- [ ] Clear commit messages
- [ ] Documentation updated if needed
- [ ] No debug code left

## Troubleshooting

### Environment Issues

```bash
# Reset everything
rm -rf .venv .pytest_cache .ruff_cache
uv sync --force-reinstall

# Verify setup
uv run python -c "import zulipchat_mcp; print('✓ Import works')"
```

### Common Errors

| Error | Solution |
|-------|----------|
| "No Zulip email found" | `export $(cat .env \| xargs)` |
| "Stream not found" | Create "Agents-Channel" manually in Zulip |
| Import errors | Check `uv sync` completed successfully |
| Test failures | Run `uv run pytest -xvs` for details |

## Agent-Specific Instructions

### For Claude Code

1. **Always register first**: `register_agent("claude-code")`
2. **Check AFK before sending**: Messages only send when user is away
3. **Use require_response**: When you need human input
4. **Block on responses**: Use `wait_for_response()` - it will wait

### For Complex Tasks

1. **Break into phases** - Don't try to do everything at once
2. **Commit frequently** - After each working change
3. **Test incrementally** - Verify each phase works
4. **Document decisions** - Explain non-obvious choices

### Workflow Example

```python
# Good: Clear phases with testing
# Phase 1: Restructure
move_files()
test_imports()
commit("refactor: reorganize module structure")

# Phase 2: Implement feature
add_new_tool()
add_tests()
commit("feat: add new_tool functionality")

# Bad: Everything at once
restructure_and_add_features_and_fix_bugs()  # Too much!
```

## Key Files for Next Session

### 🔧 **Files Needing Debug/Investigation**
- `src/zulipchat_mcp/core/client.py` - ZulipClientWrapper.get_messages() method
- `src/zulipchat_mcp/tools/messaging.py` - get_messages tool (line ~120)
- `src/zulipchat_mcp/tools/search.py` - search_messages tool  
- `src/zulipchat_mcp/config.py` - Environment variable loading

### ✅ **Files Working Correctly**
- `src/zulipchat_mcp/server.py` - Clean, registers 19 tools correctly
- `src/zulipchat_mcp/utils/database.py` - DuckDB operations working
- `src/zulipchat_mcp/tools/streams.py` - get_streams() working perfectly
- `src/zulipchat_mcp/tools/agents.py` - register_agent() working
- `.mcp/zulipchat/zulipchat.duckdb` - Database with all required tables

## Final Reminders

1. **Simplicity is the goal** - Every line should justify its existence
2. **Test everything** - Untested code is broken code
3. **Commit atomically** - Each commit should be one logical change
4. **Document why, not what** - Code shows what, comments explain why
5. **When in doubt, don't add it** - Features are easy to add, hard to remove

---

*Following [agents.md](https://agents.md) standard and [Claude Code best practices](https://www.anthropic.com/engineering/claude-code-best-practices)*