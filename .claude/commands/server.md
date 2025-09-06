---
description: Start the Zulip MCP server for testing
allowed-tools: Bash
---

Start the Zulip MCP server and show its initialization.

Environment check: !`env | grep ZULIP`
Server startup: !`uv run zulipchat-mcp`