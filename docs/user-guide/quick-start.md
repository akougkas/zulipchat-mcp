# Quick Start

This guide gets a first-time user from zero to a working Zulip MCP connection in about two minutes.

## 1. Get a `zuliprc`

In Zulip: `Settings` -> `Personal settings` -> `Account & privacy` -> `API key` -> `Download .zuliprc`.

Save it as `~/.zuliprc`.

## 2. Start the server

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

If your client manages MCP servers for you, use the same command in client config.

## 3. Connect a client

Example with Claude Code:

```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Then ask the assistant to call `server_info`.

## Optional: setup wizard

If you want an interactive flow:

```bash
uvx zulipchat-mcp-setup
```

The wizard scans for `zuliprc` files, validates credentials against Zulip, and prints client config snippets.

## Core vs extended tools

Default mode uses 19 core tools.

Enable the full 55-tool surface when needed:

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --extended-tools
```

## Dual identity (user + bot)

```bash
uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

The server starts as user identity. Use `switch_identity` to move between `user` and `bot`.

## Next

- [Configuration](configuration.md)
- [Installation](installation.md)
- [Setup Wizard](setup-wizard.md)
- [Integration docs](../integrations/README.md)
