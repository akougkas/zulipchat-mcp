# Antigravity

Antigravity's MCP integration surface is still evolving publicly.

## Recommended config template

```json
{
  "mcpServers": {
    "zulipchat": {
      "command": "uvx",
      "args": [
        "zulipchat-mcp",
        "--zulip-config-file",
        "/home/you/.zuliprc"
      ]
    }
  }
}
```

Community integrations currently use paths such as:

- `~/.gemini/antigravity/mcp_config.json`
- workspace-level `mcp.json`

## Extended mode

Append `"--extended-tools"` to `args`.

## Notes

- Verify exact file path and key names against your Antigravity build.
- Template package: `integrations/antigravity/`.
