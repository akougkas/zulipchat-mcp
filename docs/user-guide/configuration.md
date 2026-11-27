# Configuration

This page documents runtime configuration for ZulipChat MCP v0.8.3.

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

If neither `--zulip-config-file` nor `ZULIP_CONFIG_FILE` is given, the server checks:

1. `~/.zuliprc`
2. `~/.config/zulip/zuliprc`

A `zuliprc` in the working directory is not picked up on its own, because hosts
start the server inside whatever project is open. Name it explicitly to use it.

## CLI flags

```bash
zulipchat-mcp [options]
```

- `--zulip-config-file PATH`: User `zuliprc`
- `--zulip-bot-config-file PATH`: Bot `zuliprc` for dual identity
- `--extended-tools`: Register all 53 tools instead of the 13-tool core set
- `--tool-profile {full,read-only,ask-owner}`: Enforce the selected Zulip tool surface (`full` by default). `ask-owner` exposes only `ask_owner`, for agents launched by `zulipchat-mcp-agents`.
- `--ephemeral-state`: Write no files. Read caches stay in memory instead of the account cache directory. Use it where the state directory is not writable, such as a sandboxed worker.
- `--transport {stdio,http}`: Transport protocol (`stdio` default, `http` for streamable-HTTP)
- `--host HOST`: Bind host for `--transport http` (default: `127.0.0.1`)
- `--port PORT`: Bind port for `--transport http` (default: `8000`)
- `--auth-token TOKEN`: Bearer authentication token for HTTP transport
- `--allowed-host HOST`: Additional trusted HTTP hostname (repeatable)
- `--allowed-origin URL`: Additional trusted browser origin (repeatable)
- `--file-root DIR`: The only directory `upload_file` may read and `download_file` may write over stdio (default: `ZULIPCHAT_FILE_ROOT`, else the server's working directory)
- `--unsafe`: Enable destructive operations that are otherwise blocked
- `--debug`: Enable debug logging

`--enable-listener`, `--associate-existing-db` and `--mention-allow` belonged
to the agent session tools removed in 0.8.0. They are still accepted so 0.7
host configurations start, and the server logs a warning that it ignores them.
To reach an agent from Zulip, use the [agent bridge](../integrations/agent-bots.md).

## Read-only tool profile

For bounded discovery and Zulip reads, use:

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc --tool-profile read-only
```

The profile exposes seven core reads, or 23 with `--extended-tools`. Discovery
omits writes and mixed-operation tools. A direct call to an excluded tool is
also rejected with `isError=true`, `error.code="POLICY_DENIED"`, and
`error.retryable=false`, before the operation executes. `resolve_user` is a read and
remains available. Event tools are excluded because they register remote
event queues. The profile rejects `--unsafe` at startup.

`server_info.capabilities` reports the effective tool names and count, profile,
transport, and availability of identity switching. Use this information and
the current tool schemas to plan calls. The profile covers the configured
account; it does not confine reads to one channel, sandbox the coding host, or
make the server's local caches immutable. The `full` profile retains the
13/53-tool surface and existing safety checks.

Application failures now set MCP `isError=true` while preserving structured
error details. Partial delivery retains its message IDs and is not converted
to an execution error.

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

### HTTP Transport & Security

- `ZULIPCHAT_HTTP_AUTH_TOKEN`: Bearer token required for `--transport http` requests

Non-loopback binds require a token; blank or whitespace-bearing tokens are rejected.
Host and Origin checks are always enabled. Add the public hostname with
`--allowed-host` when using a reverse proxy. Use TLS for remote connections.
Each instance serves one trusted account; bearer authentication does not map
callers to separate Zulip users. See the [HTTP deployment notes](../../README.md#remote-http-transport).

### Runtime

- `ZULIPCHAT_EXTENDED_TOOLS=1`: enable extended tool registration
- `ZULIPCHAT_FILE_ROOT=DIR`: local file root when `--file-root` is not given
- `MCP_DEBUG=true`: debug logging
- `MCP_PORT=3000`: internal port metadata value

`ZULIPCHAT_DB_PATH` and `ZULIPCHAT_MENTION_ALLOW` are no longer read.

## Persistent state and account migration

The server keeps no account database. Read caches live in
`$XDG_STATE_HOME/zulipchat-mcp/accounts/ACCOUNT_FINGERPRINT/cache` (normally
`~/.local/state/...`), shared by every project and host using that account.
The fingerprint is a non-secret SHA-256 of the normalized realm and effective
user/bot principals. Key rotation does not change it; a different realm or
principal uses a different directory, so changing organization starts a fresh
cache rather than migrating one. `--ephemeral-state` keeps the caches in
memory. Nothing in the server's working directory is picked up as state.

A DuckDB database left by 0.7.x (`zulipchat.duckdb` under the same account
directory, or `.mcp/zulipchat/` in a project) is no longer read. Delete it when
you no longer need its history. Named organization profiles remain a separate
[proposed feature](../developer-guide/organization-profiles.md).

## Configuration precedence

For file-path settings, environment variables are checked first, then CLI values.

Once a `zuliprc` is selected, its email, key, and site are loaded together and
take precedence over ambient credential environment variables. This applies
separately to the user and bot files. Without a selected file, environment
credentials are used. A malformed selected file fails explicitly; it does not
silently switch to another account. File paths expand `~`.

Clients and caches are isolated by configuration and user/bot identity. Restart
the server after changing credential files so cached clients reload them.

## Write delivery

SDK automatic retries are disabled so an ambiguous failed write is not silently
sent again. After a failed send, check Zulip before retrying it manually.

## Safety model

- Default mode is safe.
- `--unsafe` enables attachment deletion in `delete_file`.
- HTTP disables local file paths. Use inline uploads or returned download URLs; use stdio for local file operations.
- Over stdio, `upload_file` reads and `download_file` writes only inside the
  file root: `--file-root DIR`, else `ZULIPCHAT_FILE_ROOT`, else the directory
  the server was started in. Paths that resolve outside it, including through
  symlinks, are refused with `PATH_OUTSIDE_ROOT`. Downloads never overwrite an
  existing file.

## Dual identity

Dual identity is optional.

```bash
uvx zulipchat-mcp \
  --zulip-config-file ~/.zuliprc \
  --zulip-bot-config-file ~/.zuliprc-bot
```

Use `switch_identity` at runtime over stdio. HTTP uses the configured user identity
and rejects process-wide identity changes.

## Test configuration quickly

Run the server and call `server_info` from your MCP client.

## Related docs

- [Quick Start](quick-start.md)
- [Installation](installation.md)
- [Setup Wizard](setup-wizard.md)
- [Security Policy](../../SECURITY.md)
