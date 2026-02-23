# Integration Guide

Each page below includes copy-paste setup for one client.

- [Claude Code](claude-code.md)
- [Gemini CLI](gemini-cli.md)
- [Codex](codex.md)
- [OpenCode](opencode.md)
- [VS Code + GitHub Copilot](vscode-copilot.md)
- [Cursor](cursor.md)
- [Windsurf](windsurf.md)
- [Antigravity](antigravity.md)
- [Generic MCP Client](generic.md)

## Shared baseline command

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Optional flags

- `--zulip-bot-config-file ~/.zuliprc-bot`
- `--extended-tools`
- `--unsafe`
- `--debug`

## Package templates

Ready-to-use package templates are in `integrations/` at repository root.
