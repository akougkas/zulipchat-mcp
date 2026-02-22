---
name: Bug Report
about: Something isn't working as expected
title: ""
labels: bug, needs-triage
assignees: ""
---

## Summary

A clear description of the bug.

## Steps to Reproduce

1. Install via `uvx zulipchat-mcp` (version: X.Y.Z)
2. Configure with `--zulip-config-file ~/.zuliprc`
3. Call tool `...` with parameters:

```json
{
  "example": "params"
}
```

4. Observe error

## Expected Behavior

What should happen.

## Actual Behavior

What happens instead. Include the full error message/traceback if available.

## Environment

- **zulipchat-mcp version**: (run `uvx zulipchat-mcp --version` or check PyPI)
- **Python version**:
- **OS**:
- **MCP client**: (Claude Code / Cursor / other)
- **Zulip server version**: (Settings → Organization → Zulip version)
