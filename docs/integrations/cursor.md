# Cursor

Cursor uses MCP JSON configuration compatible with stdio MCP servers.

## Config (`~/.cursor/mcp.json`)

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

## Extended mode

Append `"--extended-tools"` to `args`.

## Notes

- Cursor CLI MCP management is available in recent builds (`cursor-agent mcp ...`).
- Template package: `integrations/cursor/`.
