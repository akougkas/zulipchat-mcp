# Clio Coder

The v0.7.7 integration was checked against Clio Coder 0.7.0 (tag `v070`). Clio
negotiated MCP 2026-07-28, discovered all 60 extended tools with their
annotations, and applied the exported per-tool action classes. Checks used a
mock Zulip server and a local model through Clio's headless `run`, its
`mcp test` command, the plugin install path and a sandboxed read-only worker.
Reads ran, writes needed operator confirmation or were refused in read-only
runs, and the read-only worker never sent a write request to Zulip. No changes
to the Clio repository are required.

The two experiments below predate Clio 0.7.0 and used v0.7.4 of this server.

A later, authorized experiment also exercised the installed interactive Clio
TUI against live Zulip using a local v0.7.4 wheel in a temporary project. Both
the configured Codex target and a smaller local Qwopus target discovered
the server and called the reviewed account, channel, search, and message reads.
The local model also constructed narrows and summarized the retrieved discussion.
This establishes those read operations, not every discovered tool or the write
and approval workflows. See the [experiment notes](../testing/clio-live-readonly.md).

A subsequent Generic-bot experiment used **Luna** in a dedicated visible TUI.
A private experiment host adapter turned four normal owner mentions into Clio
turns, each producing one bot reply in the source topic, including a
five-message summary with correct UTC dates and IDs. That adapter and its native
approvals were scoped to one private project and are not shipped; see
[live bot mentions](../testing/clio-bot-mentions.md). The MCP exporter does not
install an unattended launcher or coding runner.

## Configure a project

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client clio-coder \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc \
  --zulip-bot-config-file /absolute/path/to/.zuliprc-bot --extended-tools
```

From a source checkout, `uv run zulipchat-mcp-integrate` performs the same
export. Clio 0.7.0 has no `mcp add` command; the project declaration is the
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
`~/.local/state/zulipchat-mcp/accounts/`, so all projects share one database and
one mention inbox per account.

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

Plugin mode exports an Agent Plugins 1.0.0 package. For `--client clio-coder`
its `mcp.json` also carries Clio's `timeoutMs` and `toolActionClasses`; other
clients receive the plain schema. Clio 0.7.0 executes plugin `mcp.json`
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
registers and permits only the 23 read tools and keeps local state in a private
temporary database removed at exit. Agent sessions, approvals and the mention
inbox are unavailable in that mode. A worker recipe names the exact
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
  --expected-version 0.7.7
```

The check creates and removes its own temporary project and fake credentials.
It validates both export formats and their 60 per-tool action classes,
negotiates MCP 2026-07-28 (or 2025-06-18 with older Clio builds), checks that
tool annotations agree with the read classes, reads server information, and
exercises local profile/session binding.
It does not connect to Zulip or change Clio's configuration or trust records.
