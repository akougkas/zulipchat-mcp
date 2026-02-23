# OpenCode

OpenCode uses an `mcp` block in `opencode.json` (or your OpenCode config file).

## Config example

```jsonc
{
  "mcp": {
    "zulipchat": {
      "type": "local",
      "enabled": true,
      "command": [
        "uvx",
        "zulipchat-mcp",
        "--zulip-config-file",
        "/home/you/.zuliprc"
      ]
    }
  }
}
```

## Extended mode

Add `"--extended-tools"` to `command`.

## Notes

- OpenCode also supports CLI-based MCP server add/remove/list workflows.
- Template package: `integrations/opencode/`.
