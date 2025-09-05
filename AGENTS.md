# AGENTS.md

AI agent instructions for ZulipChat MCP Server development.

## Project Overview

ZulipChat MCP is a **lean Model Context Protocol server** enabling bidirectional communication between AI agents and humans via Zulip. After v2.0 refactoring, the codebase is 70% simpler while maintaining essential functionality.

**Current State**: v1.4.0 (needs v2.0 restructuring per IMPLEMENTATION_PHASES.md)
**Architecture**: Thin MCP layer exposing Zulip functionality
**Philosophy**: Simple, maintainable, no over-engineering

## Quick Start

```bash
# 1. Setup environment
uv sync                       # Install dependencies
cp .env.example .env         # Configure credentials
export $(cat .env | xargs)   # Load environment

# 2. Test connection
uv run python -c "from src.zulipchat_mcp.config import ConfigManager; ConfigManager().validate_config()"

# 3. Run server
uv run zulipchat-mcp
```

## Critical Context for AI Agents

### ⚠️ BEFORE YOU CODE

1. **Read IMPLEMENTATION_PHASES.md** - Contains the v2.0 restructuring plan
2. **Current state is messy** - 1000+ line server.py needs splitting
3. **Keep it simple** - Resist adding features, focus on removing complexity
4. **Project-local state only** - Use `.mcp/` folder, never `~/.config/`

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

### File Organization

```
src/zulipchat_mcp/
├── server.py          # <100 lines - entry point ONLY
├── tools/
│   ├── messaging.py   # ~200 lines - message operations
│   ├── streams.py     # ~150 lines - stream management
│   ├── agents.py      # ~250 lines - agent communication
│   └── search.py      # ~200 lines - search/summaries
└── core/
    └── agent_tracker.py  # Minimal session tracking
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

## Key Files to Know

- `IMPLEMENTATION_PHASES.md` - v2.0 restructuring plan
- `src/zulipchat_mcp/server.py` - Currently bloated, needs splitting
- `src/zulipchat_mcp/agent_tracker.py` - Core agent session logic
- `.mcp/` - Project-local state directory
- `tests/test_integration.py` - End-to-end testing

## Final Reminders

1. **Simplicity is the goal** - Every line should justify its existence
2. **Test everything** - Untested code is broken code
3. **Commit atomically** - Each commit should be one logical change
4. **Document why, not what** - Code shows what, comments explain why
5. **When in doubt, don't add it** - Features are easy to add, hard to remove

---

*Following [agents.md](https://agents.md) standard and [Claude Code best practices](https://www.anthropic.com/engineering/claude-code-best-practices)*