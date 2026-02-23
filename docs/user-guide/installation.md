# Installation

Install ZulipChat MCP from PyPI, GitHub, or TestPyPI.

## Recommended install (PyPI)

```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

Interactive onboarding:

```bash
uvx zulipchat-mcp-setup
```

## Install from GitHub

```bash
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Install from TestPyPI

```bash
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Local development install

```bash
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv sync
uv run zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Per-client setup

Use the dedicated integration pages:

- [Claude Code](../integrations/claude-code.md)
- [Gemini CLI](../integrations/gemini-cli.md)
- [Codex](../integrations/codex.md)
- [OpenCode](../integrations/opencode.md)
- [VS Code + GitHub Copilot](../integrations/vscode-copilot.md)
- [Cursor](../integrations/cursor.md)
- [Windsurf](../integrations/windsurf.md)
- [Antigravity](../integrations/antigravity.md)
- [Generic MCP](../integrations/generic.md)

## Verify installation

```bash
uvx zulipchat-mcp --help
```

If help renders, installation is working.

## Upgrade

PyPI:

```bash
uvx --refresh zulipchat-mcp --help
```

GitHub source:

```bash
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp --help
```
