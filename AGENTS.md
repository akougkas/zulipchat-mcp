# AGENTS.md

## Purpose & Agent Behavior

- This file is the single source of truth for coding agents working on `zulipchat-mcp`.
- Always use `uv` for Python operations; never use `pip` directly.
- Before committing, automatically run formatting, linting, type checks, and tests. Do not commit unless all are green.
- Follow MCP specification, project rules, and security guidance exactly. Prefer editing existing files over creating new ones.
- Precedence: the nearest `AGENTS.md` applies; explicit user prompts override repository guidance.
- Handle secrets via environment variables; never commit credentials or sensitive data.

Reference: [AGENTS.md standard](https://agents.md/)

## Table of Contents

- [Project Overview](#project-overview)
- [Quick Start](#quick-start)
- [Current Status & Next Priorities](#current-status--next-priorities)
- [Development Guidelines](#development-guidelines)
  - [Python Environment](#python-environment)
  - [MCP Protocol Standards](#mcp-protocol-standards)
  - [Zulip API Best Practices](#zulip-api-best-practices)
- [Development Workflow](#development-workflow)
- [Code Style & Standards](#code-style--standards)
  - [Essential Rules](#essential-rules)
- [Testing Requirements](#testing-requirements)
  - [Before EVERY Commit](#before-every-commit)
  - [Test Patterns](#test-patterns)
- [Agent-First Development](#agent-first-development)
  - [Intelligent Task Delegation](#intelligent-task-delegation)
  - [Workflow Patterns](#workflow-patterns)
  - [Agent Discovery for Multi-Platform AI Systems](#agent-discovery-for-multi-platform-ai-systems)
- [Common Tasks](#common-tasks)
  - [Adding a New MCP Tool](#adding-a-new-mcp-tool)
  - [Debugging MCP Issues](#debugging-mcp-issues)
- [Important Reminders](#important-reminders)
- [Environment Variables](#environment-variables)
- [Quick Links](#quick-links)
- [Security & Safety](#security--safety)
  - [NEVER Commit](#never-commit)
- [Performance Guidelines](#performance-guidelines)
  - [Keep It Simple](#keep-it-simple)
- [Report Checklist](#report-checklist)
- [Troubleshooting](#troubleshooting)
  - [Environment Issues](#environment-issues)
  - [Common Errors](#common-errors)
- [Final Reminders](#final-reminders)

## Project Overview

ZulipChat MCP is a **professional Model Context Protocol server** enabling AI agents to communicate with humans via Zulip. **v2.0 architectural refactor COMPLETE** with sophisticated bot identity system and optimized performance.

**Current State**: v1.5.0 - Enhanced with project management documentation and bug tracking
**Architecture**: Clean `core/utils/services/tools/integrations` pattern with 59ms average latency
**Bot Identity**: ✅ Sophisticated dual-credential system (user + bot identity)
**Status**: ✅ Comprehensive testing complete, ✅ Documentation updated, 🎯 Ready for public release
**Philosophy**: Follow MCP standards, simple user experience, professional architecture

**Documentation**: ✅ ROADMAP.md (scheduling features planned), ✅ BUGS.md (5 known issues tracked)

## Quick Start

```bash
# 1. Setup environment (uv handles everything)
uv sync                       # Install dependencies + create venv
# Note: .env credentials auto-loaded from environment

# 2. Test server startup
uv run zulipchat-mcp         # Server initializes DuckDB + starts MCP

# 3. Connect Claude Code to MCP
claude mcp add zulipchat uv run zulipchat-mcp

```

## Current Status & Next Priorities

### ✅ **COMPLETED (v2.0 Refactor)**

1. **Architecture**: Clean `core/utils/services/tools/integrations` structure
2. **Database**: DuckDB persistence with proper migrations and tables
3. **Server**: FastMCP stdio-only server with core MCP tools
4. **Integration**: Claude Code successfully connected (`claude mcp add zulipchat`)
5. **Tools Working**: Core messaging, agent registration, database operations
6. **Documentation**: Professional project management with ROADMAP.md and BUGS.md

### 📋 **DOCUMENTED ISSUES & ROADMAP**

See **BUGS.md** for complete issue tracking and **ROADMAP.md** for planned enhancements:
- Comprehensive bug documentation and workarounds
- Message scheduling features planned for v2.0
- Enhanced user interaction system roadmap

## Development Guidelines

### Python Environment

- **ALWAYS** use `uv run` for Python operations (never use pip directly)
- Use `uv add <package>` to install dependencies
- Use `uv sync` to synchronize environment
- Maintain `pyproject.toml` as single source of truth

### MCP Protocol Standards

- Follow official MCP specification for all tool implementations
- Ensure proper error handling and schema validation
- Implement comprehensive logging for debugging
- Use async/await patterns for all I/O operations

### Zulip API Best Practices

- Implement rate limiting and backoff strategies
- Cache frequently accessed data (streams, users)
- Use bulk operations where available
- Handle authentication securely via environment variables

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

## Agent-First Development

### Intelligent Task Delegation

Our optimized agent team uses compute efficiently:

- **Opus (High Reasoning)**: orchestrator, code-architect, debugger
- **Sonnet (Balanced)**: code-writer, test-implementer  
- **Haiku (Fast Execution)**: api-researcher, pattern-analyzer

### Workflow Patterns

1. **Research Phase**: Launch lightweight agents in parallel
2. **Design Phase**: Engage architect for system design
3. **Implementation**: Sequential code writing and testing
4. **Validation**: Debug and optimize

### Agent Discovery for Multi-Platform AI Systems

When working with AI assistants (Claude, Gemini, GPT), specialized subagents are available in the `.claude/agents/` directory (or equivalent for your platform). Each agent is optimized for specific computational needs:

- **High-Reasoning (Opus)**: orchestrator, code-architect, debugger
- **Balanced (Sonnet)**: code-writer, test-implementer
- **Fast (Haiku)**: api-researcher, pattern-analyzer

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

## Important Reminders

- **NEVER** create files unless necessary - prefer editing
- **ALWAYS** validate against MCP specification
- **VERIFY** Zulip API responses and handle errors
- **DOCUMENT** architectural decisions in code
- **TEST** every new feature comprehensively

## Environment Variables

Required for operation:

```bash
ZULIP_EMAIL=bot@example.com
ZULIP_API_KEY=your-api-key
ZULIP_SITE=https://your-domain.zulipchat.com
```

## Quick Links

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Zulip API Documentation](https://zulip.com/api/)
- [Project Repository](https://github.com/user/zulipchat-mcp)

## Security & Safety

### NEVER Commit

- `.env` files with real credentials
- API keys in code
- Personal information in tests
- Debug print statements
- Attribution to Claude Code or Anthropic

## Performance Guidelines

### Keep It Simple

- **No premature optimization** - Clarity > Performance
- **Synchronous by default** - Async only when proven necessary
- **File-based state** - JSON files are fine for our scale
- **Batch when obvious** - But don't over-engineer

## Report Checklist

Before declaring completion of any task:

- [ ] Code formatted with `black`
- [ ] Linting passes with `ruff`
- [ ] Type checking passes with `mypy`
- [ ] All tests pass
- [ ] No files >500 lines
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

## Final Reminders

1. **Simplicity is the goal** - Every line should justify its existence
2. **Test everything** - Untested code is broken code
3. **Commit atomically** - Each commit should be one logical change
4. **Document why, not what** - Code shows what, comments explain why
5. **When in doubt, don't add it, ASK USER** - Features are easy to add, hard to remove
