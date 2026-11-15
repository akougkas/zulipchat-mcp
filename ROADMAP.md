# Roadmap

## v0.8.0 (unreleased)

- Talk to local ACP coding agents (Clio, Claude and others) from Zulip through
  the agent bridge `zulipchat-mcp-agents`, one Zulip bot per agent, with
  `service install` to run it at login.
- Remove the MCP-side agent control plane: the session tools, their listener,
  the Claude hook bridge, three skills and the DuckDB database. Core tools go
  from 19 to 13 and extended from 53 to 45.
- Export per-tool Clio action classes so trusted servers work in Clio 0.7 read-only runs.
- Export a read-only Clio declaration for sandboxed read-only workers.
- Keep read caches in memory with `--ephemeral-state` where state is not writable.
- Keep message reads within client result budgets: compact stream and user listings, Markdown message content and cursor paging for search.
- Complete task-augmented calls such as `ask_owner` for clients that declare the MCP Tasks extension.

## v0.7.6

- Enforce owner-only bot mention and direct-message polling, with `--mention-allow`.
- Read direct messages to the bot; send as the bot per message.
- Suppress repeated identical sends; report the sending identity and UTC times.
- Advertise MCP tool annotations derived from the read-only profile.

## v0.7.5

- Share one account database per Zulip account across projects and hosts under
  `$XDG_STATE_HOME/zulipchat-mcp`, rather than the server's working directory.
- Export several organizations into one host configuration with `--server-id`.
- Keep checked-in integration skill templates identical to the packaged skills.

## v0.7.4

- Correct auxiliary `uvx` commands and gate explicit package sources in CI.
- Merge Olivier Durif's community PR #22, allow compatible FastMCP 4 updates,
  refresh the full lockfile, and test the minimum and latest allowed versions.
- Package four Agent Skills, serve them through MCP Resources and SEP-2640,
  and export native configuration for Claude Code, Codex, OpenCode, Copilot CLI,
  VS Code, Antigravity CLI, and Clio Coder.
- Provide an Agent Plugins 1.0.0 package alongside Claude's native plugin format.
  Keep host-specific execution and permission checks explicit.
- Address confirmed findings from the independent Astra architecture review.
- Keep Python 3.10 compatibility and validate current Python versions, local
  source, and built wheels with fake credentials.

Evidence and limitations: [v0.7.4 audit](docs/releases/v0.7.4-audit.md).
The FastMCP migration (#17) and modern ping behavior (#18) were resolved in
v0.7.3; see its [completed audit](docs/releases/v0.7.3-audit.md).

## Next: named organization profiles

Start with **startup selection**, with one organization per server process.
The [profile design](docs/developer-guide/organization-profiles.md) specifies
credential precedence, cache isolation, configuration validation, and
acceptance tests. This feature is a design proposal; `--profile` and runtime
organization switching are not implemented. v0.7.5's `--server-id` exports
and shared per-account state cover one process per organization today.

Runtime organization switching needs a separate design for in-flight calls,
cached reads, tasks, and HTTP caller isolation before it can be offered.

## Distribution follow-up

- Validate the MCP Registry entry and submit supported plugin packages to host
  directories that accept this format. Local schema validation does not imply
  directory acceptance or listing.
- Use [Agent bots](docs/integrations/agent-bots.md) as a small reproducible
  demo: a Clio bot answering its owner from Zulip.
- Collect real integration feedback before adding executable host plugins or
  another compatibility layer.
