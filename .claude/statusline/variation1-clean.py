#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Variation 1: Clean & Minimal
Philosophy: Show only essential info, clean separators, no emoji overload
Example: [Sonnet] feat/v2* • orchestrator • MCP:zulip • 45k/∞ • code
"""

import json
import sys
import os
import subprocess
from pathlib import Path

def get_model_short(model_id, model_name):
    """Short model indicator."""
    if 'opus' in model_id.lower():
        return "Opus"
    elif 'haiku' in model_id.lower():
        return "Haiku"
    else:
        return "Sonnet"

def get_branch():
    """Get git branch, clean format."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=0.5
        )
        branch = result.stdout.strip() if result.returncode == 0 else 'main'
        
        # Check for changes
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, timeout=0.5
        )
        has_changes = '*' if result.stdout.strip() else ''
        
        # Shorten long branch names
        if len(branch) > 15:
            branch = branch[:12] + "…"
        
        return f"{branch}{has_changes}"
    except:
        return "main"

def get_active_agent():
    """Get current agent if any."""
    # Check for Task tool usage in recent activity
    # This would need integration with Claude's task tracking
    # For now, mock based on common patterns
    return None  # or "orchestrator", "code-writer", etc.

def get_mcp_connections():
    """Get connected MCP servers."""
    # Check for active MCP connections
    # In real implementation, check MCP config or process list
    servers = []
    
    # Check if zulipchat-mcp is configured
    if os.path.exists('.mcp.json'):
        servers.append('zulip')
    
    # Check for context7
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'context7'],
            capture_output=True, timeout=0.5
        )
        if result.returncode == 0:
            servers.append('ctx7')
    except:
        pass
    
    return servers

def get_mode():
    """Detect current mode: yolo, plan, or code."""
    # This would check Claude's current permission mode
    # For now, return default
    return "code"

def format_tokens(tokens):
    """Format token count for Max plan."""
    if tokens < 1000:
        return f"{tokens}"
    elif tokens < 100000:
        return f"{tokens//1000}k"
    else:
        return f"{tokens//1000}k"

def main():
    try:
        # Read JSON input
        data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
        
        # Extract data
        model = get_model_short(
            data.get('model', {}).get('id', ''),
            data.get('model', {}).get('display_name', '')
        )
        
        branch = get_branch()
        
        folder = Path(data.get('workspace', {}).get('current_dir', '.')).name
        if len(folder) > 15:
            folder = folder[:12] + "…"
        
        # Session tokens (for Max plan, show session usage)
        tokens = data.get('cost', {}).get('total_tokens_used', 0)
        token_display = f"{format_tokens(tokens)}/∞"
        
        # Build components
        components = [f"[{model}]", branch]
        
        # Add agent if active
        agent = get_active_agent()
        if agent:
            components.append(agent)
        
        # Add MCP connections
        mcps = get_mcp_connections()
        if mcps:
            components.append(f"MCP:{','.join(mcps)}")
        
        # Add tokens and mode
        components.append(token_display)
        components.append(get_mode())
        
        # Clean assembly with bullet separator
        status = " • ".join(components)
        
        print(status)
        
    except Exception as e:
        print(f"[Sonnet] main • MCP • ∞ • code")

if __name__ == "__main__":
    main()