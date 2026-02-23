# Claude Code

## Add server

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Dual identity

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

## Extended tool mode

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --extended-tools
```

## Notes

- Claude Code supports `claude mcp add`, `claude mcp list`, and `claude mcp remove`.
- Use `--` before the MCP command.
- Template package: `integrations/claude-code/`.
