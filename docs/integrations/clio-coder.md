# Clio Coder

The [fake-only integration check](#repeat-the-fake-only-integration-check)
drives this server through Clio Coder's own stdio MCP client against a mock
Zulip: export parsing, per-tool action classes, discovery of every exported
tool, profile and session binding, and a direct message sent by first name.
Earlier live experiments against a real organization, with tools since
removed, are described in [live read-only use](../testing/clio-live-readonly.md)
and [live bot mentions](../testing/clio-bot-mentions.md).

Clio loads MCP tools lazily through its `gateway` tool, so the number of tools
costs little; what costs tokens is calls per task and result size. This server
keeps both small: one call sends a direct message by name, reads are compact
Markdown, and every tool description leads with a sentence that stands alone in
`gateway(op="find")` results.

## Configure a project

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client clio-coder \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc \
  --zulip-bot-config-file /absolute/path/to/.zuliprc-bot --extended-tools
```

From a source checkout, `uv run zulipchat-mcp-integrate` performs the same
export. Clio has no `mcp add` command; the project declaration is the
generated `.clio-coder/mcp.yaml`, in Clio's strict version 1 schema:

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
    toolActionClasses:
      agent_message: execute
      delete_draft: destructive
      get_message: read
      # ... one entry for every exported tool
```

The timeout accommodates the approval-wait tool. Prefer short, repeated
`wait_for_response` calls during interactive work so the host remains responsive.
`toolActionClasses` classifies every tool from the server's own annotations:
tools in the server's read-only set are `read`, tools that edit or delete
existing content are `destructive`, and all others are `execute`. The export
also installs four instructions into `.clio-coder/skills`.

The export does not approve execution. Inside that project inspect the
declaration and trust it using Clio's operator command:

```bash
clio-coder mcp list --json
clio-coder mcp trust zulipchat --action-class execute --network
```

Project YAML cannot grant itself a server action class, but its per-tool classes
take effect once the operator trusts the declaration. The trust digest covers
them, so editing a class requires a new trust decision. `--network` lets the
server reach Zulip when Clio runs it inside a worker sandbox. Use a user-owned
bot or user credential file with appropriate organization permissions.

Check single calls without a model:

```bash
clio-coder mcp test zulipchat --call get_own_user --json
clio-coder mcp test zulipchat --call send_message --args '{"type":"stream","to":"general","topic":"t","content":"hi"}' --json
```

The read runs. The write is refused because it needs operator confirmation, as
in a headless run without approval.

### Several organizations

One server process serves one Zulip organization. Export once per organization
with a distinct `--server-id`; repeated exports merge into the same
`.clio-coder/mcp.yaml` and leave other servers unchanged:

```bash
for org in grc chronolog; do
  uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client clio-coder \
    --output-dir /absolute/path/to/project --server-id "zulipchat-$org" \
    --zulip-config-file "$HOME/.zuliprc-$org" --extended-tools
done
clio-coder mcp trust zulipchat-grc --action-class execute --network
clio-coder mcp trust zulipchat-chronolog --action-class execute --network
```

For every project, copy the same `servers` entries into Clio's user-level
`~/.config/clio-coder/mcp.yaml`, which Clio trusts by authorship, and the skills
into `~/.config/clio-coder/skills`. Each account's state lives under
`~/.local/state/zulipchat-mcp/accounts/`, so all projects share one database per
account.

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

## Invoke Clio from Zulip

Clio speaks ACP (`clio-coder acp`), so the [agent bridge](agent-bots.md) can
serve it behind its own Zulip bot:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-agents add clio \
  --owner-zuliprc ~/.zuliprc --cwd ~/projects
uvx --from zulipchat-mcp zulipchat-mcp-agents run
```

DM the bot, or mention it in a channel topic, and the bridge starts a Clio
session for that conversation. Clio runs under its own permission policy; an
ACP permission request appears in the conversation as a yes/no question. Only
the bot's owner and listed user IDs are heard.

From a running Clio session, `teleport_chat(agent="clio", message=...,
session_id=...)` hands the conversation to that bot; the owner continues it in
a DM with the bot.

## Plugin content

Plugin mode exports an Agent Plugins 1.0.0 package. For `--client clio-coder`
its `mcp.json` also carries Clio's `timeoutMs` and `toolActionClasses`; other
clients receive the plain schema. Clio executes plugin `mcp.json`
servers after operator trust:

```bash
clio-coder library validate ./zulipchat-plugin --json
clio-coder library install ./zulipchat-plugin --project
clio-coder mcp trust zulipchat --action-class execute --network
```

A content plugin does not install hooks or bypass host permissions.

## Read-only runs and workers

In `clio-coder run --read-only`, and in read-only workers, Clio starts and runs
only tools the operator classes `read`. The per-tool classes above make the
full server usable there: reads work and every write is refused before it
reaches Zulip.

A read-only worker runs its MCP servers in a sandbox where nothing persistent
is writable, so the server cannot open its account database. Export a second,
read-only declaration for workers:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client clio-coder \
  --output-dir /absolute/path/to/project --server-id zulipchat-read \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools \
  --tool-profile read-only
clio-coder mcp trust zulipchat-read --action-class read --network
```

It runs the server with `--tool-profile read-only --ephemeral-state`, which
registers and permits only the 22 read tools and keeps local state in a private
temporary database removed at exit. Agent sessions and approvals are
unavailable in that mode. A worker recipe names the exact
capabilities it may call, such as `mcp_zulipchat-read__search_messages`, and
uses `capabilityClass: read-only`.

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
  --expected-version 0.8.0
```

The check creates and removes its own temporary project and fake credentials.
It validates both export formats and their per-tool action classes,
negotiates MCP 2026-07-28 (or 2025-06-18 with older Clio builds), checks that
tool annotations agree with the read classes, reads server information,
exercises local profile/session binding, and sends a direct message by name
(and refuses an unknown name) against a mock Zulip it starts on a loopback port.
It does not connect to a real Zulip or change Clio's configuration or trust
records.
