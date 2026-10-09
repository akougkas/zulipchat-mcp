# GitHub Copilot CLI

Copilot CLI supports a user MCP file at `~/.copilot/mcp-config.json` and
repository MCP files at `.mcp.json` or `.github/mcp.json`. The generated project
export uses `.mcp.json` and `.github/skills`:

```bash
uv run zulipchat-mcp-integrate export --client copilot \
  --output-dir /absolute/path/to/project \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

Without a source checkout, use `uvx --from zulipchat-mcp zulipchat-mcp-integrate`.
Copilot's repository trust and organization MCP policy still apply. To register
only a user-scoped server, Copilot also supports:

```bash
copilot mcp add zulipchat -- uvx zulipchat-mcp \
  --zulip-config-file /absolute/path/to/.zuliprc --extended-tools
```

Inspect the connection with `copilot mcp list`. The tools can write to Zulip;
loading the skills does not authorize messaging or grant approval to the host's
other tools. Follow the [agent workflow](agent-workflow.md).

This CLI format differs from VS Code's `servers` configuration; use the
[VS Code guide](vscode-copilot.md) for that host. Paths and the `type="local"`
declaration follow [GitHub's current MCP documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers).
