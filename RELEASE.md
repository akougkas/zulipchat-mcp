# ZulipChat MCP v0.7.1

Patch release for the FastMCP task startup regression in v0.7.0.

## Fixed

- Added the FastMCP task extra through `fastmcp[anthropic,tasks]`, so task
  support installs its required runtime dependencies.
- Disabled server-wide FastMCP task advertisement with `tasks=False`.
- Made task support explicit and optional only for the intended long-running
  tools: `teleport_chat`, `wait_for_response`, and `listen_events`.
- Converted `teleport_chat(wait_for_reply=True)` and `wait_for_response` to
  async-safe implementations so they can run honestly as background-capable MCP
  tools.
- Moved background service startup and shutdown into the FastMCP lifespan so
  listener ownership is tied to server lifetime.

## Validation

The release was checked with:

```bash
uv sync
uv run pytest -q
uv run mypy src
uv run ruff check .
changed_py=$(git diff --name-only -- '*.py')
[ -z "$changed_py" ] || uv run black --check $changed_py
uv build
scripts/pre_release_smoke.sh --version 0.7.1 --allow-dirty
uvx --from dist/zulipchat_mcp-0.7.1-py3-none-any.whl zulipchat-mcp --version
uv run python scripts/mcp_stdio_smoke.py --expected-version 0.7.1 -- uv run zulipchat-mcp
```

The MCP stdio smoke uses fake credentials, starts the server, lists tools, and
calls `server_info`. It does not send Zulip messages or contact a real Zulip
server.

## Upgrade

```bash
uvx --refresh-package zulipchat-mcp zulipchat-mcp --version
```

If your MCP client caches packages, refresh or remove that client cache before
restarting the server.

## Credits

Thanks to @jessealama for the original report and PR #11, @peteWT for the
detailed dependency and async-task repro in #12, and @jpuritz for confirming the
failure.
