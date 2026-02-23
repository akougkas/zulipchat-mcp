# Architecture Overview

ZulipChat MCP v0.6.0 is organized around a small default tool surface and optional extended tooling.

## Top-level modules

```text
src/zulipchat_mcp/
├── server.py          # CLI entrypoint and tool registration mode
├── config.py          # zuliprc/env config loading + identity state
├── setup_wizard.py    # interactive setup helper
├── core/              # client wrapper, caching, security, command engine
├── tools/             # MCP tool implementations
├── services/          # listener/service manager
└── utils/             # logging, metrics, duckdb managers
```

## Tool registration model

`server.py` always calls:

1. `register_core_tools(mcp)`
2. `register_extended_tools(mcp)` only when `--extended-tools` or `ZULIPCHAT_EXTENDED_TOOLS=1`

This produces:

- Core mode: 19 tools
- Extended mode: 55 tools

## Identity model

- Runtime identity is global (`user` or `bot`), managed in `config.py`.
- Default identity is `user`.
- `switch_identity` updates the active identity.
- Bot identity is available only when bot credentials are configured.

## Startup flow

1. Parse CLI flags.
2. Initialize config manager.
3. Validate credentials (`zuliprc` or env fallback).
4. Set unsafe-mode context.
5. Initialize optional database/services.
6. Register tools.
7. Warm user/stream caches.
8. Run FastMCP stdio server.

## Service behavior

- Listener services start through `ServiceManager`.
- AFK gating affects agent notification tools, not all tool calls.

## Security-related boundaries

- `--unsafe` is off by default.
- Destructive topic delete path is guarded in `agents_channel_topic_ops`.
- Agent emoji usage is validated against a fixed approved list.
