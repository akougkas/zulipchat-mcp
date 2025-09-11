---
description: Check code quality and fix formatting
allowed-tools: Bash
---

Check and fix code quality issues in the Zulip MCP codebase.

Linting results: !`uv run ruff check . --fix`
Formatting: !`uv run ruff format .`
Type checking: !`uv run mypy src/`