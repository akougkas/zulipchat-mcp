# Release v0.4.2

## Overview

ZulipChat MCP v0.4.2 adds privacy policy documentation and MCP registry metadata for official directory listings.

## What's New

### Privacy Policy & Compliance
- Added comprehensive `PRIVACY.md` documenting data handling practices
- Added Privacy Policy section to README (required for Anthropic MCP Directory)
- No data collection, no telemetry, local execution only

### MCP Registry Support
- Added `server.json` for Official MCP Registry (registry.modelcontextprotocol.io)
- Added `mcp-name` metadata for PyPI package ownership verification
- Ready for submission to Smithery.ai, Glama.ai, and cursor.directory

## Installation

### From PyPI (Recommended)
```bash
uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

### Setup Wizard
```bash
uvx --from zulipchat-mcp zulipchat-mcp-setup
```

### Claude Code
```bash
claude mcp add zulipchat -- uvx zulipchat-mcp --zulip-config-file ~/.zuliprc
```

## Directory Listings

This release prepares zulipchat-mcp for listing in:
- [Official MCP Registry](https://registry.modelcontextprotocol.io)
- [Smithery.ai](https://smithery.ai)
- [Glama.ai](https://glama.ai/mcp/servers)
- [cursor.directory](https://cursor.directory/mcp)
- [mcpservers.org](https://mcpservers.org) (submitted)
- [mcp.so](https://mcp.so) (submitted)

## Links

- [PyPI Package](https://pypi.org/project/zulipchat-mcp/0.4.2/)
- [Documentation](https://github.com/akougkas/zulipchat-mcp#readme)
- [Privacy Policy](https://github.com/akougkas/zulipchat-mcp/blob/main/PRIVACY.md)
- [Issues](https://github.com/akougkas/zulipchat-mcp/issues)
