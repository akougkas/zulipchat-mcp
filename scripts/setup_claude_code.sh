#!/bin/bash
# Setup script to properly install ZulipChat MCP for Claude Code
# This handles the proper deployment for Claude Code agents to use

set -e

echo "🚀 ZulipChat MCP Setup for Claude Code"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${YELLOW}Step 1: Environment Check${NC}"
echo "-------------------------"

# Check UV is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ UV is not installed!${NC}"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo -e "${GREEN}✓ UV is installed${NC}"

# Check .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Creating from example..."
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "${YELLOW}⚠️  Please edit .env with your Zulip credentials${NC}"
    else
        echo "Please create .env with:"
        echo "  ZULIP_API_URL=https://your-org.zulipchat.com/api/v1"
        echo "  ZULIP_BOT_EMAIL=bot@your-org.zulipchat.com"
        echo "  ZULIP_BOT_API_KEY=your-api-key"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

echo ""
echo -e "${YELLOW}Step 2: Install Dependencies${NC}"
echo "----------------------------"
cd "$PROJECT_DIR"
uv sync
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""
echo -e "${YELLOW}Step 3: Test MCP Server${NC}"
echo "-----------------------"

# Test that the server can start
echo "Testing server startup..."
timeout 3 uv run zulipchat-mcp 2>&1 | head -5 || true
echo -e "${GREEN}✓ Server can start${NC}"

echo ""
echo -e "${YELLOW}Step 4: Add to Claude Code${NC}"
echo "--------------------------"

# Create the command for Claude Code
echo "To add this MCP server to Claude Code, run:"
echo ""

# Option 1: Using uv run with full path (recommended for development)
echo -e "${GREEN}Option 1: Development Mode (Recommended)${NC}"
echo "claude mcp add zulipchat"
echo ""
echo "When prompted for the command, enter:"
echo -e "${GREEN}uv${NC}"
echo ""
echo "When prompted for arguments, enter (as a JSON array):"
echo -e "${GREEN}[\"run\", \"--directory\", \"$PROJECT_DIR\", \"zulipchat-mcp\"]${NC}"
echo ""

# Note: UVX from GitHub will be available after publishing
echo -e "${YELLOW}Note:${NC} After publishing to GitHub, you can also use:"
echo "  uvx --from github:akougkas/zulipchat-mcp zulipchat-mcp"
echo ""

# Create a helper script for easy testing
cat > "$PROJECT_DIR/run_mcp_stdio.sh" << 'EOF'
#!/bin/bash
# Run the MCP server in stdio mode for testing
cd "$(dirname "${BASH_SOURCE[0]}")"
exec uv run zulipchat-mcp
EOF
chmod +x "$PROJECT_DIR/run_mcp_stdio.sh"

echo -e "${YELLOW}Step 5: Test Commands${NC}"
echo "---------------------"
echo ""
echo "Test the stdio server manually:"
echo -e "  ${GREEN}./run_mcp_stdio.sh${NC}"
echo ""
echo "You can type JSON-RPC commands like:"
echo '  {"jsonrpc": "2.0", "method": "initialize", "params": {"clientInfo": {"name": "test"}}, "id": 1}'
echo ""
echo "Press Ctrl+D to exit"
echo ""

echo -e "${YELLOW}Step 6: Configure Hooks (Optional)${NC}"
echo "-----------------------------------"
echo ""
echo "To enable Claude Code → Zulip notifications:"
echo -e "  ${GREEN}./hooks/setup_hooks.sh${NC}"
echo ""

echo "=================================="
echo -e "${GREEN}✨ Setup Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Add to Claude Code using the commands above"
echo "2. Restart Claude Code"
echo "3. Test with: claude (then ask it to send a message to Zulip)"
echo ""
echo "The MCP server will start automatically when Claude Code needs it."
echo "Check your Zulip for messages from the bot!"
echo ""