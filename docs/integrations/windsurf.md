# Windsurf

## Config file

`~/.codeium/windsurf/mcp_config.json`

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

- Windsurf documents MCP setup through `mcp_config.json`.
- Template package: `integrations/windsurf/`.
