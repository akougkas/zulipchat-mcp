# Antigravity CLI

The `antigravity-cli` target produces a user-MCP staging fragment and project
Agent Skills. It is distinct from the [Antigravity IDE](antigravity.md) target.

```bash
uv run zulipchat-mcp-integrate export --client antigravity-cli \
  --output-dir ./antigravity-zulipchat \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

After v0.7.4 is published, use
`uvx --from zulipchat-mcp zulipchat-mcp-integrate` for the same operation.
Merge the resulting `mcp_config.json` into the CLI's user configuration
(`~/.gemini/config/mcp_config.json`, or the configuration directory selected by
`ANTIGRAVITY_HOME`). Copy the generated `.agents/skills` into the project.
Check the paths against the CLI version installed on your machine; this target
was verified against Clio's Antigravity CLI interoperability contract, without
running an installed Antigravity CLI.

The generated JSON uses `mcpServers.zulipchat` with `command="uvx"` and explicit
argument tokens. Credential paths should be absolute. Enable the server through
the host's MCP/trust settings and discover the tools before using the skills.
The skills cover messaging, session binding, owner steering, notifications,
and a bounded work loop. They do not install executable plugins or lifecycle
hooks. See [skills and plugin compatibility](agent-skills.md).
