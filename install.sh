#!/bin/bash
set -euo pipefail

# ZulipChat MCP - Modern UV Installation
echo "🚀 ZulipChat MCP Server - UV Installer"
echo "======================================"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() { echo -e "${BLUE}▶️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${YELLOW}💡 $1${NC}"; }

# Check Python version
check_python() {
    print_step "Checking Python version..."
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is required but not found."
        echo "   Please install Python 3.10+ from https://python.org"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_success "Found Python $PYTHON_VERSION"
    
    # Check minimum version (3.10)
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
        echo "❌ Python 3.10+ required, found $PYTHON_VERSION"
        exit 1
    fi
}

# Install or update uv
install_uv() {
    print_step "Installing/updating uv package manager..."
    
    if command -v uv &> /dev/null; then
        print_info "uv is already installed, checking for updates..."
        uv self update || true
    else
        print_info "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    
    # Verify installation
    if command -v uv &> /dev/null; then
        UV_VERSION=$(uv --version)
        print_success "uv installed: $UV_VERSION"
    else
        echo "❌ Failed to install uv"
        echo "   Please try manual installation: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
}

# Install ZulipChat MCP
install_zulipchat_mcp() {
    print_step "Installing ZulipChat MCP from GitHub..."
    
    # Use uvx to install directly from GitHub
    if uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp --help &>/dev/null; then
        print_success "ZulipChat MCP installed successfully!"
    else
        echo "❌ Installation failed"
        echo "   This might be due to missing dependencies or network issues."
        echo "   Try running manually: uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp"
        exit 1
    fi
}

# Create configuration template
create_config() {
    print_step "Setting up configuration..."
    
    CONFIG_DIR="$HOME/.config/zulipchat-mcp"
    mkdir -p "$CONFIG_DIR"
    
    if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
        cat > "$CONFIG_DIR/config.json.example" << 'EOF'
{
  "email": "your-bot@zulip.com",
  "api_key": "your-api-key-here", 
  "site": "https://your-org.zulipchat.com"
}
EOF
        print_success "Created example config: $CONFIG_DIR/config.json.example"
    fi
}

# Install agent adapters if detected
install_agent_adapters() {
    print_step "Checking for AI agents..."
    
    AGENTS_FOUND=()
    
    # Check for various AI agents
    if [[ -d "$HOME/.claude" ]] || command -v claude &> /dev/null; then
        AGENTS_FOUND+=("Claude Code")
    fi
    
    if [[ -d "$HOME/.config/continue" ]] || command -v continue &> /dev/null; then
        AGENTS_FOUND+=("Continue")
    fi
    
    if command -v cursor &> /dev/null || [[ -d "/Applications/Cursor.app" ]]; then
        AGENTS_FOUND+=("Cursor")
    fi
    
    if [[ ${#AGENTS_FOUND[@]} -gt 0 ]]; then
        print_success "Detected AI agents: ${AGENTS_FOUND[*]}"
        print_info "Agent configurations can be found at: https://github.com/akougkas/zulipchat-mcp#setup"
    else
        print_info "No AI agents detected - you can configure them later"
    fi
}

# Print usage instructions
print_usage() {
    echo ""
    print_success "🎉 Installation Complete!"
    echo ""
    echo "📋 Quick Start:"
    echo "1️⃣  Get your Zulip API credentials:"
    echo "   • Visit: https://your-org.zulipchat.com"
    echo "   • Go to: Settings → Account & privacy → API key"
    echo ""
    echo "2️⃣  Set environment variables:"
    echo "   export ZULIP_EMAIL='your-bot@zulip.com'"
    echo "   export ZULIP_API_KEY='your-api-key'"
    echo "   export ZULIP_SITE='https://your-org.zulipchat.com'"
    echo ""
    echo "3️⃣  Run the server:"
    echo "   uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp"
    echo ""
    echo "📖 Full setup guide: https://github.com/akougkas/zulipchat-mcp#setup"
    echo "🐛 Issues? https://github.com/akougkas/zulipchat-mcp/issues"
}

# Main installation
main() {
    check_python
    install_uv
    install_zulipchat_mcp
    create_config
    install_agent_adapters
    print_usage
}

# Run installation
main "$@"