# PanCode

The [mock-backed integration check](#repeat-the-mock-backed-integration-check)
drives a built PanCode CLI against this server and a mock Zulip: the project
export, launch trust, surface approval, and real tool calls through
`uvx zulipchat-mcp@X.Y.Z`. An earlier live experiment against a real
organization, with tools since removed, is described in
[live read-only use](../testing/pancode-live-readonly.md).

PanCode loads MCP tools lazily through its `gateway` tool, so the number of
tools costs little; what costs tokens is calls per task and result size. This
server keeps both small: one call sends a direct message by name, reads are
compact Markdown, and every tool description leads with a sentence that stands
alone in `gateway(op="find")` results.

## Configure a project

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client pancode \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc \
  --zulip-bot-config-file /absolute/path/to/.zuliprc-bot --extended-tools
```

From a source checkout, `uv run zulipchat-mcp-integrate` performs the same
export. The project declaration is the generated `.pancode/mcp.yaml`, in
PanCode's version 1 schema:

```yaml
version: 1
servers:
  - id: zulipchat
    command: uvx
    args:
      - zulipchat-mcp@0.8.0
      - --zulip-config-file
      - /absolute/path/to/.zuliprc
      - --extended-tools
    timeoutMs: 900000
    toolActionClasses:
      add_reaction: execute
      delete_draft: destructive
      get_message: read
      # ... one entry for every exported tool
```

Exports pin the command to the version of the exporter that wrote them
(`zulipchat-mcp@X.Y.Z`): the command holds your Zulip key, and an unpinned `uvx` runs whatever
the index serves at each start. To upgrade, run the export again from the new
version with `--force`; PanCode then asks you to trust the changed declaration.

The 15-minute timeout covers long-running tools such as `listen_events`.
`toolActionClasses` classifies every tool from the server's own annotations:
tools in the server's read-only set are `read`, tools that edit or delete
existing content are `destructive`, and all others are `execute`. The export
also installs the `zulipchat` skill into `.pancode/skills`.

The export does not approve execution. Inside that project inspect the
declaration and trust it using PanCode's operator commands:

```bash
pancode mcp list --json
pancode mcp trust zulipchat --action-class execute --network
pancode mcp trust zulipchat --surface
```

Project YAML cannot grant itself a server action class or network access, so
the export writes no `network` field there. Its per-tool classes take effect
once the operator trusts the declaration; the trust digest covers them, so
editing a class requires a new trust decision. `--network` lets the server
reach Zulip when PanCode runs it inside a worker sandbox. The second command
approves the tool surface the server serves (each tool's name, schema and
annotations); at a terminal it shows the surface and records it, and in a
script `--surface --hash <sha256>` records only a surface you reviewed. Until
it is approved, sessions list the tools but refuse every call. Use a
user-owned bot or user credential file with appropriate organization
permissions.

Check single calls without a model:

```bash
pancode mcp test zulipchat --call server_info --call get_streams --json
pancode mcp test zulipchat --call send_message --args '{"type":"stream","to":"general","topic":"t","content":"hi"}' --json
```

The reads run. The write is refused because it needs operator confirmation, as
in a headless run without approval.

### Every project at once

For every project, declare the server in PanCode's user-level
`~/.config/pancode/mcp.yaml` instead. `print` writes that form, which carries
`network: true` because PanCode honors `network` only in the user's own
declaration:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate print --client pancode \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

Copy its `servers` entry into the user file and the skills into
`~/.config/pancode/skills`. PanCode records a user server's tool surface on its
first listing in an attended session.

### Several organizations

One server process serves one Zulip organization. Export once per organization
with a distinct `--server-id`; repeated exports merge into the same
`.pancode/mcp.yaml` and leave other servers unchanged:

```bash
for org in grc chronolog; do
  uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client pancode \
    --output-dir /absolute/path/to/project --server-id "zulipchat-$org" \
    --zulip-config-file "$HOME/.zuliprc-$org" --extended-tools
  pancode mcp trust "zulipchat-$org" --action-class execute --network
  pancode mcp trust "zulipchat-$org" --surface
done
```

Each account's read caches live under `~/.local/state/zulipchat-mcp/accounts/`,
so all projects share them.

## Drive the server

Discover through PanCode's gateway:

```text
gateway(op="find", server="zulipchat")
gateway(op="describe", capability="mcp_zulipchat__server_info")
gateway(op="call", capability="mcp_zulipchat__server_info", args={})
```

Inspect each tool's actual schema before calling it. The bundled `zulipchat`
skill describes the common reads and writes. To reach the owner from Zulip,
use the agent bridge below rather than polling from inside a session.

## Invoke PanCode from Zulip

PanCode speaks ACP (`pancode acp`), so the [agent bridge](agent-bots.md) can
serve it behind its own Zulip bot:

```bash
uv tool install zulipchat-mcp
zulipchat-mcp-agents add pancode --cwd ~/projects
zulipchat-mcp-agents service install
```

`add` creates the bot with `~/.zuliprc` unless `--owner-zuliprc` names another
file. `service install` runs the bridge at login; `zulipchat-mcp-agents run`
runs it in the foreground instead, while the service is stopped.

DM the bot, or mention it in a channel topic, and the bridge starts a PanCode
session for that conversation. The bridge starts PanCode with
`--autonomy default` unless the agent command names a level, so PanCode asks
before acting; an ACP permission request appears in the conversation as a
yes/no question, and a question PanCode asks the operator arrives as a numbered
list to answer in the conversation. Only the bot's owner and listed user IDs
are heard.

From a running PanCode session, `teleport_chat(agent="pancode", message=...,
session_id=...)` hands the conversation to that bot; the owner continues it in
a DM with the bot.

## PanHub pack

The repository's `pancode/` directory is the PanHub pack: an Agent Plugins
1.0.0 package whose `plugin.json` declares `extensions["dev.pancode"]` and
whose `mcp.json` carries PanCode's `timeoutMs` and `toolActionClasses`. It
names `~/.zuliprc`, which the server expands itself, so it holds no user path.
`scripts/sync_integration_templates.py` regenerates it from the exporter, and
its `--check` fails on any stale, missing or extra file. To install the pack
from a checkout:

```bash
pancode hub validate ./pancode
pancode hub install ./pancode --user
pancode mcp trust zulipchat --action-class execute --network
pancode mcp trust zulipchat --surface
```

Plugin mode writes the same package for another directory or credential file:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client pancode \
  --mode plugin --output-dir ./zulipchat-plugin \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

Other clients receive the plain Agent Plugins schema. A content plugin does
not install hooks or bypass host permissions.

## Read-only turns and workers

In a read-only turn, and in read-only workers, PanCode starts and runs only
tools the operator classes `read`. The per-tool classes above make the full
server usable there: reads work and every write is refused before it reaches
Zulip.

A read-only worker runs its MCP servers in a sandbox where nothing persistent
is writable, so the server cannot write its account cache. Export a second,
read-only declaration for workers:

```bash
uvx --from zulipchat-mcp zulipchat-mcp-integrate export --client pancode \
  --output-dir /absolute/path/to/project --server-id zulipchat-read \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools \
  --tool-profile read-only
pancode mcp trust zulipchat-read --action-class read --network
pancode mcp trust zulipchat-read --surface
```

It runs the server with `--tool-profile read-only --ephemeral-state`, which
registers and permits only the 21 read tools and keeps read caches in memory.
A worker recipe names the exact capabilities it may call, such as
`mcp_zulipchat-read__search_messages`, and uses `capabilityClass: read-only`.

## Repeat the mock-backed integration check

Build or install PanCode, then run this from the ZulipChat checkout:

```bash
node scripts/pancode_mcp_smoke.mjs --pancode "$(command -v pancode)" \
  --workdir /absolute/path/to/scratch
```

The script imports nothing from PanCode; it drives the CLI. In a scratch
project with `PANCODE_HOME` under `--workdir` it runs the standalone export,
`pancode mcp trust zulipchat --json`, `pancode mcp test zulipchat --json` to
read the surface digest, `pancode mcp trust zulipchat --surface --hash <digest>`,
and `pancode mcp test zulipchat --call server_info --call get_streams --json`,
and checks that both calls answer from a mock Zulip it starts on a loopback
port. The server runs through the exported `uvx zulipchat-mcp@X.Y.Z`, so the
pinned release must be published.

`--bridge` adds one bridged message. With `XDG_CONFIG_HOME` and
`XDG_STATE_HOME` under `--workdir`, it declares a `pancode` agent bot whose
command is `pancode acp`, starts `zulipchat-mcp-agents run --agent pancode`,
sends the bot one DM from the mock owner, and waits for the bot's reply in that
DM. That leg runs a real model: the scratch PanCode home's only target is
`openai-codex`, with its credential copied from `--credentials` (default
`~/.config/pancode/credentials.yaml`) without printing it.

The check never connects to a real Zulip and never reads or changes your own
PanCode home, trust records or `~/.config/zulipchat-mcp`.
