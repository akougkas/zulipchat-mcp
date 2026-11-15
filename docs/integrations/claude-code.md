# Claude Code

## Add the MCP server

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
claude mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot \
  --extended-tools
```

## Export a Claude package

`zulipchat-mcp-integrate export --client claude-code` writes the server
declaration and the packaged `zulipchat` skill. It writes no hooks and no
`settings.json`. `--extended-tools`, `--tool-profile` and `--server-id` apply
to the exported declaration.

### Standalone project assets

Export into a project root. An existing `.mcp.json` is merged: the server entry
is added beside the other servers, and a different existing entry with the same
id needs `--force` to be replaced.

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export \
  --client claude-code \
  --mode standalone \
  --output-dir . \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Installed assets:

- `.mcp.json`
- `.claude/skills/zulipchat/SKILL.md`

### Plugin package

Export a Claude plugin directory when you want a namespaced, shareable package.

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export \
  --client claude-code \
  --mode plugin \
  --output-dir ./zulipchat-plugin \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

That writes:

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `skills/zulipchat/SKILL.md`

Load it locally with:

```bash
claude --plugin-dir ./zulipchat-plugin
```

## Talk to Claude from Zulip

The MCP server cannot wake Claude. To message a Claude Code agent from Zulip,
run the agent bridge `zulipchat-mcp-agents` with `claude-agent-acp`; see
[Agent bots](agent-bots.md). The bridge holds Claude to its ACP mode `default`,
so it asks the owner in Zulip before edits and commands, unless the agent file
names another `mode`.

## One-command repo install

From this repository checkout:

```bash
./integrations/claude-code/install.sh
```

That script exports the standalone assets above into the current directory (or
the directory given as its first argument), pinned to this version. It does not
also run `claude mcp add`, which would declare the server twice.

## Notes

- Claude Code supports `claude mcp add`, `claude mcp list`, and `claude mcp remove`.
- Use `--` before the MCP command.
- Template package: `integrations/claude-code/`.
