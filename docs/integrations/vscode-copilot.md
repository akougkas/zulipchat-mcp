# VS Code + GitHub Copilot

Use an MCP config file in workspace or user scope.

## Workspace config (`.vscode/mcp.json`)

```json
{
  "servers": {
    "zulipchat": {
      "type": "stdio",
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

- You can create this via VS Code's MCP server commands or by editing JSON directly.
- Template package: `integrations/vscode-copilot/`.
