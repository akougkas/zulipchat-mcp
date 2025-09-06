#!/bin/bash
# Setup script for Claude Code hooks integration with ZulipChat MCP (examples)

set -e

echo "🚀 Setting up Claude Code hooks for ZulipChat MCP integration (examples)"

CLAUDE_DIR="$HOME/.claude"
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "Creating Claude Code settings directory..."
    mkdir -p "$CLAUDE_DIR"
fi

PROJECT_CLAUDE_DIR=".claude/hooks"
if [ ! -d "$PROJECT_CLAUDE_DIR" ]; then
    echo "Creating project hooks directory..."
    mkdir -p "$PROJECT_CLAUDE_DIR"
fi

# Create wrapper pointing to examples/hooks bridge
cat > "$PROJECT_CLAUDE_DIR/zulip_bridge.sh" << 'WRAPPER'
#!/bin/bash
# Wrapper to run the bridge script with UV from examples
cd "$(dirname "$0")/../.."  # Go to project root
uv run examples/hooks/claude_code_bridge.py
WRAPPER

chmod +x "$PROJECT_CLAUDE_DIR/zulip_bridge.sh"

# Copy reference Python script for manual runs
cp "examples/hooks/claude_code_bridge.py" "$PROJECT_CLAUDE_DIR/zulip_bridge.py"

SETTINGS_FILE="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
    echo "⚠️  Existing Claude Code settings found"
    echo "Manual merge required. Example configuration is at: examples/hooks/example_settings.json"
else
    echo "No existing settings found. Creating new settings with ZulipChat hooks..."
    cp "examples/hooks/example_settings.json" "$SETTINGS_FILE"
    echo "✅ Hooks configuration installed to $SETTINGS_FILE"
fi

ENV_FILE=".claude/hooks/zulip_env.sh"
cat > "$ENV_FILE" << 'EOF'
#!/bin/bash
# Environment configuration for ZulipChat MCP integration
export ZULIPCHAT_MCP_URL="http://localhost:8000"
# export CLAUDE_CODE_AGENT_ID="your-agent-id-here"
EOF

chmod +x "$ENV_FILE"

echo "✅ Example hooks setup complete."
