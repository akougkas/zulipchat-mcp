# Codex (OpenAI)

v0.7.4 adds project exports containing `.codex/config.toml` and
`.agents/skills`, and portable Agent Plugins 1.0.0 packages. See
[skills and plugins](agent-skills.md) for export, trust, and compatibility details.
The format follows [Codex MCP configuration](https://developers.openai.com/codex/mcp/)
and [OpenAI plugin packaging](https://developers.openai.com/plugins/deploy/submission).

## Add server from CLI

```bash
codex mcp add zulipchat uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Manual config (`~/.codex/config.toml`)

```toml
[mcp_servers.zulipchat]
command = "uvx"
args = ["zulipchat-mcp", "--zulip-config-file", "/home/you/.zuliprc"]
```

## Extended mode

```toml
[mcp_servers.zulipchat]
command = "uvx"
args = ["zulipchat-mcp", "--zulip-config-file", "/home/you/.zuliprc", "--extended-tools"]
```

## Notes

- Codex supports `codex mcp add`, `codex mcp list`, and `codex mcp remove`.
- Template package: `integrations/codex/`.
