---
name: Claude Code + Zulip MCP Guide
description: Unified guide for Claude Code coordination and Zulip MCP development for this repository.
reference: $PROJECT_DIR/AGENTS.md
---

# CLAUDE-MERGE.md

> ROLE: Master coordinator for multi-agent workflows powering development of the ZulipChat MCP server. Launches parallel agents, coordinates via concise handoffs, and provides actionable feedback.

## Source of Truth & Fit for This Repo

- Treat `AGENTS.md` as the canonical project playbook. Follow its workflow and conventions.
- Always use `uv` for Python operations; never use `pip` directly.
- Prefer minimal, reversible edits; keep diffs focused.
- Reset context between tasks; use `/clear` before switching goals.

## Agent Team and Chaining

- Research (parallel):
  - api-researcher (Sonnet): API docs, auth patterns, best practices
  - pattern-analyzer (Haiku): Codebase patterns, architecture conventions
- Implementation (sequential):
  - code-architect (Opus): Technical design and blueprints (chains to both foundations)
  - code-writer (Sonnet): Production Python code (chains to api-researcher)
  - test-implementer (Sonnet): Test suite (chains to pattern-analyzer)
- Validation:
  - debugger (Opus): Systematic error analysis (chains to foundations)
- Master layer: Claude Code coordinates all agents.

## Operating Rules

- Use `uv` for all Python tasks; `Edit/MultiEdit` for code; `Bash` for tooling.
- Explain intent before commands that modify files or state.
- Summarize decisions in 1–3 sentences after each major step.
- Keep scope tight: pull only relevant files/logs; cite paths and line ranges.
- Deny access to `.env*` and `**/secrets/**` by default; scope `/permissions` narrowly.

## Development Guidelines

- Python Environment
  - `uv run` for execution, `uv add` for deps, `uv sync` for sync
  - `pyproject.toml` is the single source of truth
- MCP Protocol Standards
  - Follow spec, validate schemas, comprehensive logging
  - Async/await where I/O-bound; apply rate limiting/backoff for external APIs
- Zulip API Best Practices
  - Cache frequent data (streams, users), use bulk ops when possible
  - Handle auth via env vars; verify responses and handle errors

## Session Flow

1. Explore (fast, read-only):

   ```bash
   # quick inventory
   uv run python -V
   uv run python -c "import sys; print(sys.version)"

   # project overview
   uv run python -c "import os; print(os.getcwd())" | cat

   tree -I "__pycache__|.git" -L 2 | cat

   # hotspots and test discovery
   grep -r "TODO\|FIXME" src/
   uv run pytest --co -q
   ```

2. Plan: Write a short checklist of edits and tests.
3. Implement: Apply focused edits; adhere to code style; keep diffs small.
4. Verify: Format, lint, type-check (if applicable), run targeted then full tests.
5. Commit: Conventional commits; one logical change per commit.

## Tool Permissions & Safety

- Pre-allowed (see `.claude/settings*.json`): `Bash`, `Read`, `Write`, `Edit`, `MultiEdit`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, selected MCP tools (e.g., `mcp__context7__*`, `mcp__zulipchat__get_messages`).
- Denied by default: reading/writing `.env*` and `**/secrets/**`.
- Scope `/permissions` requests narrowly; prefer allowing specific command patterns.

## Quick Commands (Repo-Aware)

```bash
# Environment setup
uv sync

# Format & lint
uv run black src/zulipchat_mcp/
uv run ruff check src/zulipchat_mcp/

# Tests (targeted → full)
uv run pytest -q
uv run pytest --cov=src/zulipchat_mcp

# Import smoke checks
uv run python -c "from zulipchat_mcp.tools.agents import wait_for_response; print('\u2713')"

# Server quick start (5s timeout)
timeout 5 uv run python -m zulipchat_mcp.server \
  --zulip-email test@example.com \
  --zulip-api-key test-key \
  --zulip-site https://test.zulipchat.com

# Listener & AFK quick checks
uv run python -c "from zulipchat_mcp.tools.agents import enable_afk_mode; print(enable_afk_mode())"
uv run python -c "from zulipchat_mcp.tools.agents import agent_message; print(agent_message('hello from agent'))"
uv run python -c "from zulipchat_mcp.tools.agents import poll_agent_events; print(poll_agent_events())"
```

## Project Structure (this repository)

```text
zulipchat-mcp/
├── src/zulipchat_mcp/
│   ├── server.py
│   ├── config.py
│   ├── core/
│   │   ├── agent_tracker.py
│   │   ├── cache.py
│   │   ├── client.py
│   │   ├── commands/
│   │   │   ├── engine.py
│   │   │   └── workflows.py
│   │   ├── exceptions.py
│   │   └── security.py
│   ├── integrations/
│   │   ├── claude_code/
│   │   ├── gemini_cli/
│   │   └── opencode/
│   ├── services/
│   │   ├── message_listener.py
│   │   └── scheduler.py
│   ├── tools/
│   │   ├── agents.py
│   │   ├── commands.py
│   │   ├── messaging.py
│   │   ├── search.py
│   │   └── streams.py
│   └── utils/
│       ├── database_manager.py
│       ├── database.py
│       ├── health.py
│       ├── logging.py
│       ├── metrics.py
│       └── topics.py
├── tests/
└── pyproject.toml
```

## Environment Variables

```bash
ZULIP_EMAIL=bot@example.com
ZULIP_API_KEY=your-api-key
ZULIP_SITE=https://your-domain.zulipchat.com
```

## Quality & Testing Standards

- Type hints for public APIs; maintain readable, high-verbosity code.
- Comprehensive error handling; never raise to MCP layer; always return error dicts.
- Prefer async for I/O-bound tasks.
- Full test coverage over time (unit, integration, e2e as feasible).

## Orchestration & Handoff Protocol

- Parallel research: run api-researcher + pattern-analyzer; merge findings.
- Sequential implementation: code-architect → code-writer → test-implementer.
- Validation: debugger inspects failures and regressions.
- Handoff packet includes: goal, constraints, key findings, planned edits/tests, next action.

## Helpful Links

- MCP Specification: [modelcontextprotocol.io/specification](https://modelcontextprotocol.io/specification)
- Zulip API Documentation: [zulip.com/api](https://zulip.com/api/)
- Project Reference: `AGENTS.md`
