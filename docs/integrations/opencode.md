# OpenCode

v0.7.4 can export `opencode.json` and `.opencode/skills`. Existing JSONC
configuration requires a manual snippet merge to preserve comments and avoid
competing files. See [skills and plugins](agent-skills.md). Configuration and
skill paths follow [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/)
and [Agent Skills](https://opencode.ai/docs/skills/).

OpenCode uses an `mcp` block in `opencode.json` (or your OpenCode config file).

## Config example

```jsonc
{
  "mcp": {
    "zulipchat": {
      "type": "local",
      "enabled": true,
      "command": [
        "uvx",
        "zulipchat-mcp",
        "--zulip-config-file",
        "/home/you/.zuliprc"
      ]
    }
  }
}
```

## Extended mode

Add `"--extended-tools"` to `command`.

## Notes

- OpenCode also supports CLI-based MCP server add/remove/list workflows.
- Template package: `integrations/opencode/`.
