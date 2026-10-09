# Agent Skills and plugin packages

v0.7.4 is prepared locally and unpublished. Run the examples below with
`uv run zulipchat-mcp-integrate` from this checkout while testing it. After
publication, use `uvx --from zulipchat-mcp zulipchat-mcp-integrate`.

Four bundled skills provide ordinary Zulip operations, topic-bound session
control, deliberate notifications, and a bounded work loop. They use the
[Agent Skills format](https://agentskills.io/specification), with `name` and
`description` frontmatter. The server exposes their content as immutable MCP
Resources. On MCP 2026-07-28 it also advertises
`io.modelcontextprotocol/skills` and implements `skills/list` and `skills/get`
under [SEP-2640](https://modelcontextprotocol.io/extensions/skills).
Each manifest includes a byte size and SHA-256 digest; those verify content,
while the host decides whether to trust and load it.

Hosts without this extension can read the Resources or load locally exported
skills. Skills are instructions; loading one does not register the MCP server,
start autonomous work, install lifecycle hooks, or authorize external writes.

## Native exports

```bash
uv run zulipchat-mcp-integrate export --client clio-coder \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

Use absolute credential paths because client process arguments do not expand
`~`. The exporter records file paths, without reading or copying API keys.

| Client target | MCP configuration | Skill directory | Activation |
| --- | --- | --- | --- |
| `claude-code` | `.mcp.json`, `.claude/settings.json` | `.claude/skills` | Claude MCP approval and native lifecycle hooks |
| `codex` | `.codex/config.toml` | `.agents/skills` | Trust the project and enable its MCP configuration in Codex |
| `opencode` | `opencode.json` | `.opencode/skills` | Enable the local server; existing JSONC requires manual snippet merge |
| `copilot` | `.mcp.json` | `.github/skills` | Copilot CLI repository trust and MCP policy |
| `vscode` | `.vscode/mcp.json` | `.github/skills` | VS Code workspace MCP trust |
| `antigravity-cli` | `mcp_config.json` staging fragment | `.agents/skills` | Merge the fragment into the CLI's user MCP file |
| `clio-coder` | `.clio-coder/mcp.yaml` | `.clio-coder/skills` | Separate project MCP trust; see the Clio guide |
| `generic` | `.mcp.json` fragment | `.agents/skills` | Adapt configuration to the host's documented paths |

Exports merge unrelated JSON/TOML/YAML settings and server entries, but refuse
to change an existing Zulip server declaration without `--force`. User-edited
skill files also require `--force`. Every conflict and symlink is checked before
writing. Configuration serialization can reformat JSON/TOML/YAML and removes
TOML/YAML comments; use `print` and merge manually when comments matter.
Claude credential replacement recognizes exact exporter-owned hook commands.
If a custom wrapper or edited command references the Zulip hook, export refuses
ambiguous ownership even with `--force`; review that command and merge it manually.
Individual replacements are atomic; an I/O failure may still interrupt a
multi-file export. The exporter does not alter host trust or install anything.

## Portable plugins

```bash
uv run zulipchat-mcp-integrate export --client codex --mode plugin \
  --output-dir ./zulipchat-plugin \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

For every target except Claude Code, plugin mode produces the same
[Agent Plugins 1.0.0](https://agent-plugins.org/) layout: root `plugin.json`,
root `mcp.json`, and four `skills/<name>/SKILL.md` files. The manifest and MCP
declarations are validated against the published schemas. Codex recognizes
this portable format. Clio validates the content but does not execute plugin
MCP declarations; configure its native YAML separately. OpenCode and
Antigravity use the native configuration/skill exports; a portable package
does not establish that they have a plugin installer for this specification.

Claude Code plugin mode retains its native `.claude-plugin/plugin.json`,
`.mcp.json`, hooks, skills, and session subagent. Those lifecycle hooks are
Claude-specific. Other hosts follow the skills explicitly and retain their
own scheduling and permission policies. None of these local packages is a
published marketplace listing.
