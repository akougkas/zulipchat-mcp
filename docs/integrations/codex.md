# Codex (OpenAI)

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
