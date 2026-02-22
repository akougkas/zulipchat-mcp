# Roadmap

## v0.5.1 (Current)

Released 2026-02-22 - [PyPI](https://pypi.org/project/zulipchat-mcp/)

**Highlights:**
- ConfigManager singleton pattern for consistent CLI arg handling
- All logging outputs to stderr (no stdout pollution for MCP STDIO)
- SECURITY.md with responsible disclosure policy
- CLI arguments now respected by all tools

## v0.6.0 (Next)

### Feature 1: Multi-Organization Support
**Problem**: Users with multiple Zulip orgs (work, personal, open-source) can't switch contexts.

**Solution**:
- Named profiles in config: `--profile work` / `--profile personal`
- Profile registry: `~/.config/zulipchat-mcp/profiles.json`
- Runtime switching: `switch_organization` tool
- Auto-discovery of multiple zuliprc files

**Example**:
```bash
uvx zulipchat-mcp --profile work
uvx zulipchat-mcp --profile personal
```

### Feature 2: Plugin Marketplace Packaging
**Problem**: Different AI platforms have different extension formats.

**Target platforms**:
- MCP Registry (modelcontextprotocol.io)
- Anthropic Tool Library
- Google Gemini Extensions
- OpenAI GPT Actions
- VS Code / Cursor extensions

**Approach**:
- Adapter layer per platform (same core, different packaging)
- `plugins/` directory with platform-specific manifests
- Single `uv build --target=<platform>` command

---

## Next Session Agenda
1. List zulipchat-mcp in public MCP catalogs
2. Submit to Anthropic/Google extension directories
3. Create promotional materials (demo GIFs, etc.)
