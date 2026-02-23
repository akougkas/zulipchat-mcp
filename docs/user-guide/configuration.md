# Configuration

This page documents all runtime configuration for ZulipChat MCP v0.6.0.

## Recommended setup

Use a `zuliprc` file and pass it explicitly:

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Credential sources

The server accepts either:

1. A `zuliprc` file (preferred)
2. Environment variables (`ZULIP_EMAIL`, `ZULIP_API_KEY`, `ZULIP_SITE`)

## `zuliprc` auto-discovery

If `--zulip-config-file` is not passed, the server checks:

1. `./zuliprc`
2. `~/.zuliprc`
3. `~/.config/zulip/zuliprc`

## CLI flags

```bash
zulipchat-mcp [options]
```

- `--zulip-config-file PATH`: User `zuliprc`
- `--zulip-bot-config-file PATH`: Bot `zuliprc` for dual identity
- `--extended-tools`: Register all 55 tools instead of the 19-tool core set
- `--unsafe`: Enable destructive operations that are otherwise blocked
- `--debug`: Enable debug logging
- `--enable-listener`: Backward-compatibility flag

Note: listener services are started automatically in v0.6.0. The `--enable-listener` flag remains for compatibility.

## Environment variables

### Credentials

- `ZULIP_EMAIL`
- `ZULIP_API_KEY`
- `ZULIP_SITE`
- `ZULIP_BOT_EMAIL`
- `ZULIP_BOT_API_KEY`

### Config file overrides

- `ZULIP_CONFIG_FILE`
- `ZULIP_BOT_CONFIG_FILE`

### Runtime

- `ZULIPCHAT_EXTENDED_TOOLS=1`: enable extended tool registration
- `MCP_DEBUG=true`: debug logging
- `MCP_PORT=3000`: internal port metadata value
- `ZULIP_DEV_NOTIFY=1`: bypass AFK notification gating for agent tools

## Configuration precedence

For file-path settings, environment variables are checked first, then CLI values.

For credentials, `zuliprc` is the intended primary path. Environment credentials are supported as a fallback.

## Safety model

- Default mode is safe.
- `--unsafe` enables destructive operations currently guarded in tool logic (for example topic deletion in `agents_channel_topic_ops`).

## Dual identity

Dual identity is optional.

```bash
uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Use `switch_identity` at runtime.

## Test configuration quickly

Run the server and call `server_info` from your MCP client.

## Related docs

- [Quick Start](quick-start.md)
- [Installation](installation.md)
- [Setup Wizard](setup-wizard.md)
- [Security Policy](../../SECURITY.md)
