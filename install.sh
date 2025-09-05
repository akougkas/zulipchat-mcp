#!/bin/bash
set -euo pipefail

# ZulipChat MCP - Simple UV Installation
echo "🚀 ZulipChat MCP Server - UV Installer"
echo "======================================"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}▶️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }

# Check Python version
print_step "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found."
    echo "   Please install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
print_success "Found Python $PYTHON_VERSION"

# Check minimum version
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    echo "❌ Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi

# Install uv if not present
print_step "Installing uv package manager..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

UV_VERSION=$(uv --version)
print_success "uv ready: $UV_VERSION"

# Test installation
print_step "Testing ZulipChat MCP installation..."
if uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp --help &>/dev/null; then
    print_success "ZulipChat MCP installed successfully!"
else
    echo "❌ Installation failed"
    exit 1
fi

# Print usage instructions
echo ""
print_success "🎉 Installation Complete!"
echo ""
echo "📋 Quick Start:"
echo "1️⃣  Set environment variables:"
echo "   export ZULIP_EMAIL='your-bot@zulip.com'"
echo "   export ZULIP_API_KEY='your-api-key'"
echo "   export ZULIP_SITE='https://your-org.zulipchat.com'"
echo ""
echo "2️⃣  Run the server:"
echo "   uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp"
echo ""
echo "📖 Full setup guide: https://github.com/akougkas/zulipchat-mcp#setup"