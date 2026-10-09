# Clio Coder

The v0.7.4 integration was checked against the local Clio Coder v0.6.2-rc.3
configuration parser, plugin validator, and real stdio MCP client. It negotiated
MCP 2025-06-18, discovered all 60 extended tools, and called `server_info` using
fake credentials, then registered an agent profile and bound a session using
local state. Source and installed-wheel checks use Clio's actual TypeScript
client. No changes to the Clio repository are required.

A later, authorized experiment also exercised the installed interactive Clio
TUI against live Zulip using a local v0.7.4 wheel in a temporary project. Both
the configured Codex target and a smaller local Dynamo Qwopus target discovered
the server and called the reviewed account, channel, search, and message reads.
The local model also constructed narrows and summarized the retrieved discussion.
This establishes those read operations, not every discovered tool or the write
and approval workflows. See the [experiment notes](../testing/clio-live-readonly.md).

A subsequent Generic-bot experiment used **Luna** in a dedicated visible TUI.
Three normal owner mentions woke Clio and produced one bot reply each in the
source topic. Its host adapter and native approvals were scoped to that private
project; see [live bot mentions](../testing/clio-bot-mentions.md). The MCP exporter
does not install an unattended launcher.

## Configure a project

From this unpublished checkout:

```bash
uv run zulipchat-mcp-integrate export --client clio-coder \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc \
  --zulip-bot-config-file /absolute/path/to/.zuliprc-bot --extended-tools
```

After publication use
`uvx --from zulipchat-mcp zulipchat-mcp-integrate` for the same export. The
generated `.clio-coder/mcp.yaml` has Clio's strict version 1 schema:

```yaml
version: 1
servers:
  - id: zulipchat
    command: uvx
    args:
      - zulipchat-mcp
      - --zulip-config-file
      - /absolute/path/to/.zuliprc
      - --extended-tools
    timeoutMs: 900000
```

The timeout accommodates the approval-wait tool. Prefer short, repeated
`wait_for_response` calls during interactive work so the host remains responsive.
The export also installs four instructions into `.clio-coder/skills`.
It does not approve execution. Inside that project inspect the declaration and
trust it using Clio's operator command:

```bash
clio-coder mcp list --json
clio-coder mcp trust zulipchat --action-class execute
```

ZulipChat has write tools, so the declaration must not be classified as
read-only. Project YAML cannot grant itself an action class. The operator's
trust record authorizes the exact server declaration; changing it needs a new
trust decision. Use a user-owned bot or user credential file with appropriate
organization permissions.

## Drive the server

Discover through Clio's gateway:

```text
gateway(op="find", server="zulipchat")
gateway(op="describe", capability="mcp_zulipchat__server_info")
gateway(op="call", capability="mcp_zulipchat__server_info", args={})
```

Inspect each tool's actual schema before calling it. Register with
`agent_type="clio-coder"`, retain `agent_id`, bind with `ensure_agent_session`,
and retain `session_id`. Use `agent_message` for results, `poll_agent_events`
for owner steering, and `request_user_input` plus bounded `wait_for_response`
for decisions. Use the [workflow example](agent-workflow.md) and bundled skills.

For mention-driven work, a separate host adapter reads
`poll_agent_events(mentions_stream="Agents-Channel", after_message_id=cursor,
auto_ack=False, wait_seconds=20)`. This reads a local event-fed inbox and does
not require an existing session. Validate numeric bot/sender/channel IDs,
listener health and cursor continuity before queuing work. Retain a stable
agent/topic binding for subsequent mentions; source message IDs identify tasks,
not new external sessions. Reply in the source topic with the configured bot.
Ordinary conversation does not use `/reply`. Explicit questions and approvals
remain correlated by request ID. See [API efficiency and host ownership](../developer-guide/zulip-api-proxy.md).

## Plugin content

Plugin mode exports an Agent Plugins 1.0.0 package that Clio can validate with
`clio-coder library validate ./zulipchat-plugin --json`. Clio's current plugin
loader preserves `mcp.json` but reports that it does not execute it. Install
or register the content through Clio's library workflow and configure/trust
the native MCP YAML separately. A content plugin does not install hooks or
bypass host permissions. Clio's current stdio client uses the legacy protocol;
the server preserves that compatibility alongside the modern protocol.

## Constrained read-only experiments

Clio v0.6.2-rc.3 supports per-tool `toolActionClasses` in the declaration. Review
and classify individual read operations; keep the full server's trust class as
`execute` because it also exposes writes. The declaration digest includes these
overrides, so changing them requires a new trust decision.

The headless `--allow-tools` option currently prevents server-specific MCP
discovery even when the named MCP capabilities are admitted. The normal TUI
can discover the trusted server. An instruction to perform only reads does not
disable the MCP write tools: the live experiment additionally used a temporary
server middleware allowlist and an HTTP guard. Clio's `run --read-only` flag
applies to fleet dispatch with `--agent`, not the main agent.

## Repeat the fake-only integration check

With Clio's development dependencies installed, run this from the ZulipChat
checkout. Replace the executable paths with those of the source environment or
a clean environment containing the built wheel:

```bash
node --import /absolute/path/to/clio-coder/node_modules/tsx/dist/loader.mjs \
  scripts/clio_mcp_smoke.mjs \
  --clio-repo /absolute/path/to/clio-coder \
  --server-command /absolute/path/to/venv/bin/zulipchat-mcp \
  --integrate-command /absolute/path/to/venv/bin/zulipchat-mcp-integrate \
  --expected-version 0.7.4
```

The check creates and removes its own temporary project and fake credentials.
It validates both export formats, negotiates the legacy protocol, discovers
tools, reads server information, and exercises local profile/session binding.
It does not connect to Zulip or change Clio's configuration or trust records.
