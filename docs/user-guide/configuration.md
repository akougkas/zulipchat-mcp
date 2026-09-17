# Configuration

This page documents runtime configuration for ZulipChat MCP v0.7.3.

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
- `--extended-tools`: Register all 60 tools instead of the 20-tool core set
- `--transport {stdio,http}`: Transport protocol (`stdio` default, `http` for streamable-HTTP)
- `--host HOST`: Bind host for `--transport http` (default: `127.0.0.1`)
- `--port PORT`: Bind port for `--transport http` (default: `8000`)
- `--auth-token TOKEN`: Bearer authentication token for HTTP transport
- `--allowed-host HOST`: Additional trusted HTTP hostname (repeatable)
- `--allowed-origin URL`: Additional trusted browser origin (repeatable)
- `--unsafe`: Enable destructive operations that are otherwise blocked
- `--debug`: Enable debug logging
- `--enable-listener`: Backward-compatibility flag

Note: listener services are lazy-started by tools that need them. The
`--enable-listener` flag starts the listener eagerly and remains for
compatibility.

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

### Server-side LLM Provider

- `ANTHROPIC_API_KEY`: API key for server-side AI analytics tools (`analyze_stream_with_llm`, `analyze_team_activity_with_llm`, `intelligent_report_generator`)
- `ANTHROPIC_MODEL`: Optional model override (default: `claude-opus-5`)

### HTTP Transport & Security

- `ZULIPCHAT_HTTP_AUTH_TOKEN`: Bearer token required for `--transport http` requests

Non-loopback binds require a token; blank or whitespace-bearing tokens are rejected.
Host and Origin checks are always enabled. Add the public hostname with
`--allowed-host` when using a reverse proxy. Use TLS for remote connections.
Each instance serves one trusted account; bearer authentication does not map
callers to separate Zulip users. See the [HTTP deployment notes](../../README.md#remote-http-transport).

### Runtime

- `ZULIPCHAT_EXTENDED_TOOLS=1`: enable extended tool registration
- `ZULIPCHAT_DB_PATH`: DuckDB file path (default: `.mcp/zulipchat/zulipchat.duckdb`)
- `MCP_DEBUG=true`: debug logging
- `MCP_PORT=3000`: internal port metadata value
- `ZULIPCHAT_AGENT_STREAM=<stream>`: override the default control stream used for agent session topics
- `ZULIPCHAT_APPROVAL_TIMEOUT=<seconds>`: timeout for Claude hook approval waits

## Configuration precedence

For file-path settings, environment variables are checked first, then CLI values.

Once a `zuliprc` is selected, its email, key, and site are loaded together and
take precedence over ambient credential environment variables. This applies
separately to the user and bot files. Without a selected file, environment
credentials are used. A malformed selected file fails explicitly; it does not
silently switch to another account. File paths expand `~`.

Clients and caches are isolated by configuration and user/bot identity. Restart
the server after changing credential files so cached clients reload them.

## Approval and listener behavior

Owner approvals must name the request: `/approve REQUEST_ID` or
`/deny REQUEST_ID`. Bare `approve`/`deny` messages do not answer a pending
request. Once answered or cancelled, a request cannot be overwritten by a later
message. A `wait_for_response` polling timeout leaves the request pending so
another call can resume waiting. The Claude permission hook has a separate
approval deadline and denies execution on timeout or persistence failure.

The listener persists its cursor after processing each event. An interrupted
poll can take up to the 90-second HTTP timeout to finish; shutdown does not start
a replacement listener while the old one is still running. SDK automatic
retries are disabled so an ambiguous failed write is not silently sent again.
After a failed send, check Zulip before retrying it manually.

## Safety model

- Default mode is safe.
- `--unsafe` enables attachment deletion and topic deletion in `agents_channel_topic_ops`.
- HTTP disables local file paths and outbound event callbacks. Use inline uploads or returned download URLs; use stdio for local file operations.

## Dual identity

Dual identity is optional.

```bash
uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Use `switch_identity` at runtime over stdio. HTTP uses the configured user identity
for ordinary tools and rejects process-wide identity changes; session tools still
use the configured bot account where needed.

## Test configuration quickly

Run the server and call `server_info` from your MCP client.

## Related docs

- [Quick Start](quick-start.md)
- [Installation](installation.md)
- [Setup Wizard](setup-wizard.md)
- [Security Policy](../../SECURITY.md)
