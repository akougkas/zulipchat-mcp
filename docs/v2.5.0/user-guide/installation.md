# Installation Guide

Complete installation guide for ZulipChat MCP v2.5.0 with multiple deployment options.

## Prerequisites

### System Requirements
- **Python**: 3.10, 3.11, or 3.12
- **Operating System**: Cross-platform (Linux, macOS, Windows)
- **Architecture**: x86_64, ARM64 supported

### Zulip Requirements
- Active Zulip organization
- Valid user account with API access
- Optional: Bot account for automated features

### Required Tools
- `uv` (recommended) or `pip` for dependency management
- `git` for source installation

## Installation Methods

### Method 1: Development Setup (Recommended)

For development or testing environments:

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp

# Create virtual environment
uv venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install with development dependencies
uv pip install -e .[dev]
```

### Method 2: Production Installation

For production environments:

```bash
# Direct installation from source
uv pip install git+https://github.com/akougkas/zulipchat-mcp.git

# Or install specific version/tag
uv pip install git+https://github.com/akougkas/zulipchat-mcp.git@v2.5.0
```

### Method 3: PyPI Installation

When available on PyPI:

```bash
uv pip install zulipchat-mcp
```

## Core Dependencies

The following packages are automatically installed:

| Package | Version | Purpose |
|---------|---------|---------|
| `fastmcp` | >=0.1.0 | MCP protocol implementation |
| `httpx` | >=0.24.0 | HTTP client for API calls |
| `pydantic` | >=2.0.0 | Data validation and parsing |
| `python-dotenv` | >=1.0.0 | Environment variable loading |
| `zulip` | >=0.9.0 | Official Zulip API client |
| `structlog` | >=24.1.0 | Structured logging |
| `prometheus-client` | >=0.19.0 | Metrics collection |
| `duckdb` | >=0.9.0 | Embedded database for caching |

## Verification

Verify your installation:

```bash
# Check Python version
python --version

# Verify installation
python -c "import zulipchat_mcp; print('✓ Installation successful')"

# Check available commands
python -m zulipchat_mcp.server --help
```

## Next Steps

After installation:

1. **[Configure credentials](configuration.md)** - Set up Zulip API access
2. **[Quick start guide](quick-start.md)** - Basic usage examples
3. **[Server startup](../api-reference/)** - Start using the MCP server

## Development Setup

For contributors and developers:

### Additional Development Dependencies

```bash
# Install with development extras
uv pip install -e .[dev]

# This includes:
# - pytest (testing framework)
# - black (code formatting)
# - ruff (linting)
# - mypy (type checking)
# - coverage (test coverage)
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/zulipchat_mcp

# Run specific test types
uv run pytest -m unit
uv run pytest -m integration
```

### Code Quality Tools

```bash
# Format code
uv run black src/zulipchat_mcp/

# Lint code
uv run ruff check src/zulipchat_mcp/

# Type checking
uv run mypy src/zulipchat_mcp/
```

## Container Deployment

### Docker Support (Future)

Container deployment will be supported in upcoming versions:

```dockerfile
# Dockerfile example (coming soon)
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv pip install .
CMD ["python", "-m", "zulipchat_mcp.server"]
```

## Troubleshooting Installation

### Common Issues

**Python Version Error**
```bash
# Check Python version
python --version
# Ensure it's 3.10, 3.11, or 3.12
```

**UV Not Found**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart terminal or source shell configuration
```

**Permission Errors**
```bash
# Use virtual environment (recommended)
uv venv
source .venv/bin/activate

# Or install to user directory
pip install --user git+https://github.com/akougkas/zulipchat-mcp.git
```

**Network/Proxy Issues**
```bash
# Configure pip/uv for proxy
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=https://proxy.example.com:8080

# Or use direct GitHub access
git clone https://github.com/akougkas/zulipchat-mcp.git
cd zulipchat-mcp
uv pip install -e .
```

### Verification Commands

```bash
# Test import
python -c "from zulipchat_mcp.server import main; print('✓ Server import OK')"

# Test core components
python -c "from zulipchat_mcp.core.client import ZulipClientWrapper; print('✓ Core OK')"

# Test tool loading
python -c "from zulipchat_mcp.tools import messaging_v25; print('✓ Tools OK')"
```

## Uninstallation

To completely remove ZulipChat MCP:

```bash
# Uninstall package
uv pip uninstall zulipchat-mcp

# Remove virtual environment (if used)
rm -rf .venv

# Remove configuration files (optional)
rm -rf ~/.config/zulipchat-mcp
```

## Version Management

### Checking Current Version

```bash
python -c "import zulipchat_mcp; print(zulipchat_mcp.__version__)"
```

### Upgrading

```bash
# Development installation
cd zulipchat-mcp
git pull origin main
uv pip install -e .

# Production installation  
uv pip install --upgrade git+https://github.com/akougkas/zulipchat-mcp.git
```

## Platform-Specific Notes

### Linux
- Standard installation works on all major distributions
- Some systems may require `python3-dev` for compilation

### macOS  
- Ensure Xcode command line tools are installed: `xcode-select --install`
- Apple Silicon (M1/M2) fully supported

### Windows
- Use PowerShell or Command Prompt
- Virtual environment activation: `.venv\Scripts\activate`
- Path separators use backslash (`\`)

## Support

If you encounter installation issues:

1. Check [Troubleshooting Guide](../troubleshooting.md)
2. Review [Configuration Guide](configuration.md)
3. Verify [System Requirements](#system-requirements)
4. Check GitHub Issues for known problems

---

**Next**: [Configuration Guide](configuration.md) - Set up your Zulip credentials