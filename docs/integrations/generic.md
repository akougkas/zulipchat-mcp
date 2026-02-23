# Generic MCP Client

Most MCP clients accept one of these two JSON shapes.

## Shape A (`mcpServers`)

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

## Shape B (`servers`)

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

## Optional flags

- dual identity: add `--zulip-bot-config-file /home/you/.zuliprc-bot`
- full tool surface: add `--extended-tools`
- debug logs: add `--debug`
