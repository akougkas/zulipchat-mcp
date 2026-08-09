# Architecture Overview

ZulipChat MCP is organized around a compact default tool surface, optional extended tooling, and a DuckDB-backed agent control plane for Zulip-bound sessions.

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

- Core mode: 20 tools
- Extended mode: 60 tools

## Identity model

- Runtime identity is global (`user` or `bot`), managed in `config.py`.
- Default identity is `user`.
- `switch_identity` updates the active identity.
- Bot identity is available only when bot credentials are configured.

## Startup flow

1. Apply protocol compatibility patch (`core/compat.py`).
2. Parse CLI flags (`--transport stdio|http`, `--host`, `--port`, `--auth-token`).
3. Initialize config manager.
4. Validate credentials (`zuliprc` or env fallback).
5. Set unsafe-mode context.
6. Initialize optional database/services.
7. Register FastMCP instance with SEP-2663 `TasksExtension`.
8. Register tools (core 20 or extended 60).
9. Warm user/stream caches.
10. Run FastMCP server (`stdio` or streamable `http`).

## Server-Side LLM Provider (`core/llm.py`)

Under the 2026-07-28 stateless protocol, MCP sampling is removed from the server API. AI analytics tools execute via a server-side Anthropic provider (`core/llm.py`) configured with `ANTHROPIC_API_KEY`. When unconfigured, tools report `llm_unavailable: true` and return raw structured summaries so calling agents can reason over data directly.

## Stateless HTTP Transport & Multi-Replica Caveat

`--transport http` enables streamable-HTTP serving. Requests are stateless and self-contained under the 2026-07-28 protocol, permitting round-robin load balancing.

> **Single-Writer DB Caveat**: DuckDB storage (`zulipchat.duckdb`) is single-writer. Multi-replica HTTP deployments must either assign distinct DB file paths per worker or operate as a single instance.

## Service behavior

- Listener services start through `ServiceManager`.
- The listener persists queue state and dispatches inbound topic messages into session events.
- Owner policy is enforced at the session-topic boundary, not via AFK state.

## Agent control plane

- Stable agent profiles live in DuckDB and are keyed by owner + agent type + agent name.
- Agent sessions bind one Zulip topic to one agent runtime session.
- Requests and approvals are persisted separately from raw inbound events.
- `zulipchat-mcp-hook` bridges Claude Code lifecycle hooks into the same session model.

## Security-related boundaries

- `--unsafe` is off by default.
- Bearer token authentication required on non-loopback HTTP binds (`--auth-token` / `ZULIPCHAT_HTTP_AUTH_TOKEN`).
- Destructive topic delete path is guarded in `agents_channel_topic_ops`.
- Agent emoji usage is validated against a fixed approved list.
