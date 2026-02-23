# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current Status (v0.6.1)

**Published**: [PyPI](https://pypi.org/project/zulipchat-mcp/) | [TestPyPI](https://test.pypi.org/project/zulipchat-mcp/)

Install: `uvx zulipchat-mcp --zulip-config-file ~/.zuliprc`

## Project Overview

ZulipChat MCP Server v0.6.1 - A Model Context Protocol (MCP) server that enables AI assistants to interact with Zulip Chat workspaces. The project uses FastMCP framework with DuckDB for persistence and async-first architecture.

## Essential Development Commands

### Environment Setup
```bash
# Install dependencies (NEVER use pip - always use uv)
uv sync

# Run the MCP server locally
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc

# Quick run via uvx
uvx zulipchat-mcp
```

### Testing & Quality Assurance
```bash
# Run tests (60% coverage gate)
uv run pytest -q

# Skip slow/integration tests for faster feedback
uv run pytest -q -m "not slow and not integration"

# Full coverage report
uv run pytest --cov=src

# Linting and formatting
uv run ruff check .
uv run black .
uv run mypy src

# Security checks (optional)
uv run bandit -q -r src
uv run safety check
```

### Development Testing
```bash
# Test connection to Zulip
uv run python -c "
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.config import ConfigManager
config = ConfigManager()
client = ZulipClientWrapper(config)
print(f'Connected! Identity: {client.identity_name}')
"

# Import validation
uv run python -c "from src.zulipchat_mcp.server import main; print('OK')"
```

## Architecture Overview

### Core Structure
```
src/zulipchat_mcp/
├── core/           # Business logic (client, identity, commands, batch processing)
├── tools/          # MCP tool implementations (messaging, streams, search, events, users, files)
├── utils/          # Shared utilities (logging, database, health, metrics)
├── services/       # Background services (scheduler, message listener)
├── integrations/   # AI client integrations
└── config.py       # Configuration management
```

### Key Components

- **Entry Point**: `src/zulipchat_mcp/server.py` - Main MCP server with CLI argument parsing
- **Client Wrapper**: `src/zulipchat_mcp/core/client.py` - Dual identity Zulip API wrapper with caching
- **Tools**: `src/zulipchat_mcp/tools/*.py` - MCP tool implementations
- **Configuration**: `src/zulipchat_mcp/config.py` - Environment/CLI configuration management
- **Database**: DuckDB integration for persistence and caching

### Dual Identity System
The client supports both user and bot credentials:
- User identity for reading/search operations
- Bot identity for posting messages and administrative tasks
- Identity switching via `switch_identity` tool

### Import Patterns (v0.4)
All imports follow the new modular structure:
```python
from src.zulipchat_mcp.core.client import ZulipClientWrapper
from src.zulipchat_mcp.tools.messaging import register_messaging_tools
```

**Important**: The codebase underwent complete v0.4 architectural refactor. Previous flat imports like `from zulipchat_mcp.client import` are deprecated.

## Tool Registration Pattern

Each tool module exports a registration function:
```python
# Pattern used across tool modules
def register_*_tools(mcp: FastMCP) -> None:
    """Register tools with the MCP server."""
    # Tool implementations here
```

## Development Guidelines

### Core Philosophy: Less is More
- **Elegant simplicity is the primary success metric**
- Achieve goals with minimal code - every line must justify its existence
- Prefer leveraging Zulip's native capabilities over custom implementations
- Remove complexity rather than managing it
- If a solution feels complicated, it probably is - find a simpler way

### Python Environment
- **Critical**: NEVER use pip - always use `uv run` for all Python operations
- Python 3.10+ required
- Use `uv add <package>` for dependencies, `uv sync` to synchronize

### Code Style
- Black formatting (line length 88)
- Ruff linting with pycodestyle, pyflakes, isort, bugbear, pyupgrade
- Type hints required for all public APIs
- Prefer async/await for I/O operations
- 4-space indentation, snake_case for functions/variables, CamelCase for classes
- **Minimize abstractions** - direct, clear code over clever patterns

### Testing Strategy
- Tests in `tests/` directory following pytest conventions
- Mark slow tests with `@pytest.mark.slow`, integration tests with `@pytest.mark.integration`
- Mock Zulip API calls to keep tests network-free
- 60% coverage gate enforced (`--cov-fail-under=60` in pyproject.toml)
- Use `uv run pytest` exclusively (no direct Python)

### File Operations
- **Always prefer editing existing files over creating new ones**
- **Consider deletion before addition** - can we solve this by removing code?
- Use Read tool before any file modifications
- Maintain existing code patterns and conventions

## Configuration

### Environment Variables
```bash
ZULIP_EMAIL=your@email.com
ZULIP_API_KEY=your_api_key
ZULIP_SITE=https://yourorg.zulipchat.com
ZULIP_BOT_EMAIL=bot@yourorg.zulipchat.com  # Optional
ZULIP_BOT_API_KEY=bot_api_key              # Optional
```

### CLI Integration
For Claude Code integration (tested syntax):
```bash
# From PyPI (once published)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx zulipchat-mcp

# From GitHub (available now)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp

# From TestPyPI (for testing)
claude mcp add zulipchat -e ZULIP_EMAIL=bot@your-org.zulipchat.com -e ZULIP_API_KEY=your-api-key -e ZULIP_SITE=https://your-org.zulipchat.com -- uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp
```

**Important**: Use the `--` separator to properly pass uvx arguments to Claude Code. Environment variables must come before the `--` separator.

## Security Notes
- Never commit credentials to repository
- Use `.env` file (gitignored) for local development
- Administrative tools removed from AI access in v0.4 for security
- All credentials handled via environment variables or CLI arguments

## MCP Sampling & LLM Analytics

### Context Parameter (Required, Not Optional)
All LLM-powered tools require the `Context` parameter injected by FastMCP. Do NOT make it optional:

```python
from fastmcp import Context, FastMCP

@mcp.tool
async def analyze_with_llm(query: str, ctx: Context) -> dict[str, Any]:
    """LLM analysis tool - Context is REQUIRED, not optional."""
    # FastMCP automatically injects ctx when called
    result = await ctx.sample(f"Analyze: {query}")
    return {"analysis": result.text}
```

**Key Points:**
- ✅ `ctx: Context` (required) - FastMCP auto-injects
- ❌ `ctx: Context | None = None` (optional) - breaks sampling
- Use `await ctx.sample(prompt)` to request LLM completions
- Client controls model selection and permissions

### Approved Emoji for Agent Reactions
Agents should use only these 12 emoji for consistency and quick responses:
- `thumbs_up`, `heart`, `rocket`, `fire`, `tada`, `check_mark`
- `warning`, `thinking`, `bulb`, `wrench`, `star`, `zap`

Invalid emoji (e.g., `thumbsup` without underscore) will fail at runtime. See `src/zulipchat_mcp/core/emoji_registry.py`.

### Agent-to-User Bidirectional Communication
Complete implementation exists at `src/zulipchat_mcp/tools/agents.py`:
- Agents can send messages: `agent_message(content, require_response=True)`
- Agents can request input: `request_user_input(question, options)`
- Agents can wait for responses: `wait_for_response(request_id)`
- Background MessageListener processes Zulip replies automatically
- AFK mode gates notifications unless `ZULIP_DEV_NOTIFY=1` override set

### Command Chains (execute_chain)
Workflow automation with context passing between operations:
```python
execute_chain([
    {"type": "search_messages", "params": {"query_key": "search_query"}},
    {"type": "conditional_action", "params": {
        "condition": "len(context['search_results']) > 0",
        "true_action": {"type": "send_message", "params": {...}}
    }}
])
```

## Common Issues

### Import Errors
Ensure using v0.4 import paths:
```python
# Correct (v0.4)
from src.zulipchat_mcp.core.client import ZulipClientWrapper

# Incorrect (legacy)
from zulipchat_mcp.client import ZulipClientWrapper
```

### Coverage Issues
Clean environment before major test runs:
```bash
rm -rf .venv .pytest_cache **/__pycache__ htmlcov .coverage* coverage.xml .uv_cache
uv sync --reinstall
```

### Connection Testing
Always test Zulip connection with provided test snippet before implementing features.

### LLM Analytics Not Working
If you see "Client does not support sampling":
- Ensure `ctx: Context` is REQUIRED (not optional with `| None`)
- Remove null checks that guard against None context
- FastMCP handles injection automatically
- Client (Claude Code, Gemini) must have sampling capability enabled

## Release Process

Full checklist in [RELEASING.md](RELEASING.md). Summary:

```bash
# 1. Bump version across scripted version locations
uv run python scripts/bump_version.py X.Y.Z

# 2. Update CHANGELOG.md with new section (manual)

# 3. Run automated release preflight and smoke
uv run python scripts/release_preflight.py --version X.Y.Z
scripts/pre_release_smoke.sh --version X.Y.Z

# 4. Run full checks
uv run pytest -q && uv run ruff check . && uv run mypy src

# 5. Commit, tag, push
git add -A && git commit -m "chore: bump version to X.Y.Z"
git tag vX.Y.Z && git push && git push --tags

# 6. Create GitHub release (auto-publishes to PyPI via publish.yml)
gh release create vX.Y.Z --title "vX.Y.Z — Title" --notes "..." --latest
```

**Critical rules:**
- Version must match across pyproject.toml, `__init__.py`, system.py, `server.json`, and release docs. Use `scripts/release_preflight.py` to verify before tagging.
- **Never** create a GitHub release as draft and forget to publish it. The `publish.yml` workflow only triggers on `published` releases.
- Tag must match pyproject.toml version exactly (`v0.6.0` tag ↔ `version = "0.6.0"`).
- After publishing, verify: GitHub release shows "Latest", PyPI shows new version, `uvx zulipchat-mcp` installs it.

## Open Source & Community Practices

This is a public open-source project. Follow these practices when handling community interactions:

### Responding to Issues
- Acknowledge new issues within 48 hours, even if just "Looking into this."
- Apply labels on triage: `bug`, `enhancement`, `good first issue`, `help wanted`, `needs-triage`, `community`, `dependencies`, `fastmcp`, `mcp-tools`, `breaking-change`.
- When closing, explain what was fixed and which version contains the fix.
- Credit the reporter in release notes.

### Responding to Pull Requests
- **Respond within 48 hours.** Silence kills contributor motivation.
- Prefer merging community PRs over reimplementing the same fix independently. Contributors get credit in their GitHub contribution graph.
- If changes are needed, request them on the PR — don't close and reimplement.
- If a fix was already applied independently, close the PR with explicit credit and acknowledgment. Explain what happened.
- Label community PRs with `community`.

### Release Notifications
- After publishing a release, comment on all issues fixed in that release.
- Mention the version number, what was fixed, and how to upgrade.
- Invite reporters to try the new version and provide feedback.

## GSD Integration (Get Shit Done)

This project uses GSD for structured development workflows with Claude Code.

### Core Workflow

```
/gsd:plan-phase N    → Create detailed plan
/gsd:execute-phase N → Execute with parallel agents
/gsd:verify-work N   → UAT validation
/clear               → Reset context between phases
```

### Key Commands

| Command | Purpose |
|---------|---------|
| `/gsd:progress` | Check status, route to next action |
| `/gsd:quick` | Small tasks (skip researcher/verifier) |
| `/gsd:pause-work` | Create handoff mid-phase |
| `/gsd:resume-work` | Continue from previous session |
| `/gsd:debug` | Persistent debug sessions |
