#!/bin/bash
# Setup script for Claude Code hooks integration with ZulipChat MCP

set -e

echo "🚀 Setting up Claude Code hooks for ZulipChat MCP integration"

# Check if Claude Code settings directory exists
CLAUDE_DIR="$HOME/.claude"
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "Creating Claude Code settings directory..."
    mkdir -p "$CLAUDE_DIR"
fi

# Check if project has .claude directory
PROJECT_CLAUDE_DIR=".claude/hooks"
if [ ! -d "$PROJECT_CLAUDE_DIR" ]; then
    echo "Creating project hooks directory..."
    mkdir -p "$PROJECT_CLAUDE_DIR"
fi

# Create a wrapper script that uses UV to run the bridge
BRIDGE_SCRIPT="hooks/claude_code_bridge.py"
if [ -f "$BRIDGE_SCRIPT" ]; then
    echo "Installing bridge script..."
    
    # Create a wrapper that uses UV
    cat > "$PROJECT_CLAUDE_DIR/zulip_bridge.sh" << 'WRAPPER'
#!/bin/bash
# Wrapper to run the bridge script with UV
cd "$(dirname "$0")/../.."  # Go to project root
uv run hooks/claude_code_bridge.py
WRAPPER
    
    chmod +x "$PROJECT_CLAUDE_DIR/zulip_bridge.sh"
    
    # Also copy the Python script for reference
    cp "$BRIDGE_SCRIPT" "$PROJECT_CLAUDE_DIR/zulip_bridge.py"
else
    echo "Error: Bridge script not found at $BRIDGE_SCRIPT"
    exit 1
fi

# Check for existing hooks configuration
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
    echo "⚠️  Existing Claude Code settings found"
    echo "Manual merge required. Example configuration saved to: hooks/example_settings.json"
    echo ""
    echo "To add ZulipChat hooks, merge the contents of hooks/example_settings.json"
    echo "with your existing $SETTINGS_FILE"
else
    echo "No existing settings found. Creating new settings with ZulipChat hooks..."
    cp "hooks/example_settings.json" "$SETTINGS_FILE"
    echo "✅ Hooks configuration installed to $SETTINGS_FILE"
fi

# Create environment configuration
ENV_FILE=".claude/hooks/zulip_env.sh"
cat > "$ENV_FILE" << 'EOF'
#!/bin/bash
# Environment configuration for ZulipChat MCP integration

# MCP Server URL (adjust if running on different port)
export ZULIPCHAT_MCP_URL="http://localhost:8000"

# Optional: Pre-configured agent ID (will auto-register if not set)
# export CLAUDE_CODE_AGENT_ID="your-agent-id-here"

# Optional: Custom stream prefix for agent channels
# export ZULIPCHAT_STREAM_PREFIX="ai-agents"
EOF

chmod +x "$ENV_FILE"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Add ZulipChat MCP to Claude Code:"
echo "   claude mcp add zulipchat"
echo "   Command: uv"
echo "   Arguments: [\"run\", \"--directory\", \"$(pwd)\", \"zulipchat-mcp\"]"
echo ""
echo "2. Configure your Zulip credentials in .env file"
echo ""
echo "3. Restart Claude Code to load the new hooks"
echo ""
echo "4. Optional: Edit $ENV_FILE to customize MCP server URL"
echo ""
echo "Your Claude Code will now send notifications to Zulip!"