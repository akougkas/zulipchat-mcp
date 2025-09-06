---
description: Run Zulip MCP tests with coverage
allowed-tools: Bash
---

Run the test suite for Zulip MCP and show me the results with coverage information.

Current directory: !`pwd`
Test results: !`uv run pytest --cov=src/zulipchat_mcp --cov-report=term-missing -v`