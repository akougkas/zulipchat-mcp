# Roadmap

## v0.7.4 (Current release)

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
credential precedence, cache/database isolation, configuration validation, and
acceptance tests. This feature is a design proposal; `--profile` and runtime
organization switching are not implemented in v0.7.4.

Runtime organization switching needs a separate design for listener shutdown,
pending approvals, tasks, and HTTP caller isolation before it can be offered.

## Distribution follow-up

- Validate the MCP Registry entry and submit supported plugin packages to host
  directories that accept this format. Local schema validation does not imply
  directory acceptance or listing.
- Use the [agent workflow example](docs/integrations/agent-workflow.md) as a small
  reproducible demo, including Clio discovery and owner replies.
- Collect real integration feedback before adding executable host plugins or
  another compatibility layer.
