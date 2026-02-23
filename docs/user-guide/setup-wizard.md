# Setup Wizard

`zulipchat-mcp-setup` is an interactive onboarding flow.

## Run

```bash
uvx zulipchat-mcp-setup
```

## What it does

1. Scans for candidate `zuliprc` files.
2. Validates credentials by calling Zulip profile API.
3. Lets you configure optional bot identity.
4. Lets you choose tool mode: core (19) or extended (55).
5. Generates config snippets for:
   - Claude Code
   - Claude Desktop
   - Gemini CLI
   - Codex
   - Cursor
   - Windsurf
   - VS Code / GitHub Copilot
   - OpenCode
   - Antigravity
   - Generic MCP JSON

## Output formats

- CLI add command (`claude mcp add ...`)
- JSON config snippets (`mcpServers` or `servers` shape)
- TOML snippet for Codex (`[mcp_servers.zulipchat]`)

## Notes

- The wizard is terminal-interactive; do not pipe empty stdin.
- For JSON-writing clients, it can optionally write config files and create backups.
- Generated runtime command uses `uvx` by default for distribution-friendly installs.
