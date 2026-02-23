# Gemini CLI

## Add server from CLI

```bash
gemini mcp add zulipchat uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --scope user
```

## Manual config (`~/.gemini/settings.json`)

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

Add `--extended-tools` in `args`.

## Notes

- Gemini CLI supports MCP server management commands such as `gemini mcp add` and `gemini mcp list`.
- Template package: `integrations/gemini-cli/`.
