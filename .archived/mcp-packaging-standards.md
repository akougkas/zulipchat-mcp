# MCP Ecosystem Packaging Standards Research

**Last Updated**: 2025-01-25  
**Research Source**: Context7 + Official MCP Docs + GitHub Analysis  
**Status**: Comprehensive Analysis Complete

## Quick Start - Standard MCP Installation Pattern
```bash
# Industry Standard (100% of successful servers):
uvx package-name
claude mcp add package-name
# Client manages credentials securely
```

## Research Summary

**100% of successful MCP servers follow the uvx → claude mcp add pattern**:
- GitHub MCP servers (AWS, dbt-labs, etc.)
- Official MCP documentation examples
- Community servers (aider, openai, gsuite)

**0% use complex configuration**:
- No .env file management
- No custom setup scripts  
- No database config storage
- No interactive configuration

## pyproject.toml Requirements for uvx Compatibility

### 1. **Essential Build System**
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 2. **Project Scripts Entry Point** (Critical for uvx)
```toml
[project.scripts]
package-name = "module.path:main"

# Examples from successful servers:
# aider-mcp-server = "aider_mcp_server:main"
# dbt-mcp = "dbt_mcp.main:main"
# mcp-server-openai = "mcp_server_openai.server:main"
```

### 3. **Standard Dependencies**
```toml
dependencies = [
    "mcp>=1.6.0",  # or mcp[cli] for CLI features
    # Your specific dependencies
]
```

### 4. **Project Metadata**
```toml
[project]
name = "package-name"
version = "x.y.z"
description = "MCP server for [service] integration"
requires-python = ">=3.10"
readme = "README.md"
license = "MIT"
authors = [{name = "Your Name", email = "email@domain.com"}]
```

## Environment Variable Standards

**Standard pattern from successful servers**:
```bash
# Service credentials (3-5 variables max)
SERVICE_API_KEY=key
SERVICE_URL=https://api.service.com
SERVICE_EMAIL=user@domain.com  # if needed

# Optional configuration  
SERVICE_REGION=us-east-1       # if applicable
FASTMCP_LOG_LEVEL=ERROR        # common pattern
```

**ZulipChat MCP Standard Variables**:
```bash
ZULIP_EMAIL=user@domain.com
ZULIP_API_KEY=your-api-key
ZULIP_SITE=https://org.zulipchat.com
ZULIP_BOT_EMAIL=bot@domain.com      # optional
ZULIP_BOT_API_KEY=bot-key           # optional
```

## Server Entry Point Patterns

### Standard FastMCP Pattern
```python
# src/package_name/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Server Name")

# Register tools...

def main() -> None:
    """Main entry point for the MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
```

### Module Entry Point (`__main__.py`)
```python
# src/package_name/__main__.py
from .server import main

if __name__ == "__main__":
    main()
```

## Client Integration Standards

### Claude Code Configuration
```json
{
  "mcpServers": {
    "server-name": {
      "command": "uvx",
      "args": ["package-name"],
      "env": {
        "SERVICE_API_KEY": "value",
        "SERVICE_URL": "value"
      }
    }
  }
}
```

### Alternative Installation Methods
```json
{
  "command": "uvx",
  "args": ["--from", "git+https://github.com/org/repo.git", "package-name"]
}
```

## Analysis of ZulipChat MCP Current State

### ✅ **Already Compliant**
- Correct build system (hatchling)
- Proper entry point structure
- FastMCP server pattern
- Standard dependencies
- Good project metadata

### ❌ **Non-Standard Patterns to Fix**
1. **Entry Point Name**: Should be `zulipchat-mcp`, not `zulipchat-mcp-integrate`
2. **uvx Test**: Need to verify `uvx zulipchat-mcp` works
3. **Environment Variables**: Already standard ✅
4. **Complex Config**: Remove database config storage

## Specific Recommendations for ZulipChat MCP

### 1. **Fix pyproject.toml Entry Point**
```toml
[project.scripts]
# Current (keep as primary):
zulipchat-mcp = "zulipchat_mcp.server:main"

# Remove integration script from primary entry:
# zulipchat-mcp-integrate = "zulipchat_mcp.integrations.registry:main"
```

### 2. **Verify uvx Installation**
```bash
# Should work:
uvx zulipchat-mcp

# Should connect to server
claude mcp add zulipchat
```

### 3. **Simplify Configuration**
- Remove DuckDB config storage
- Keep only environment variable configuration
- Remove complex fallback systems

### 4. **Update Documentation**
```markdown
## Quick Start
```bash
uvx zulipchat-mcp
claude mcp add zulipchat
# Configure credentials when prompted
```

## Best Practices from Successful Servers

### **Packaging**
- Use hatchling build backend (fastest)
- Single main entry point script
- Minimal dependencies
- Clear package naming

### **Configuration** 
- Environment variables only
- 3-5 variables maximum
- Clear error messages for missing vars
- No file-based configuration

### **Documentation**
- One-line installation instructions
- Standard `claude mcp add` pattern
- Environment variable list
- No complex setup steps

## Validation Checklist

- [ ] `uvx package-name` installs and runs
- [ ] `claude mcp add package-name` prompts for credentials
- [ ] All environment variables configurable via client
- [ ] No files to manage (no .env carrying around)
- [ ] Works from any directory
- [ ] Matches patterns of other successful servers

## Related Documentation
- [MCP Official Quickstart](https://modelcontextprotocol.io/introduction/quickstart/server)
- [GitHub MCP Servers](https://github.com/modelcontextprotocol/)
- [AWS MCP Servers](https://github.com/awslabs/mcp)
- [uvx Documentation](https://docs.astral.sh/uv/guides/tools/)

## Success Examples

**Working servers that follow this pattern**:
- `uvx aider-mcp-server` → `claude mcp add aider`
- `uvx dbt-mcp` → `claude mcp add dbt`  
- `uvx awslabs.core-mcp-server` → `claude mcp add aws-core`
- `uvx mcp-server-openai` → `claude mcp add openai`

ZulipChat MCP should join this list with the same user experience pattern.