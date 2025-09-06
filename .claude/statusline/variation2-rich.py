#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Variation 2: Information-Rich Developer
Philosophy: Show all technical details, use icons smartly, developer-focused
Example: 🧠Opus │ 🎯orchestrator:active │ 🌿feat/v2* │ MCP[zulip✓,ctx7✓] │ 📊45k tok │ 📁zulipchat-mcp │ MODE:code
"""

import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

def get_model_icon_and_name(model_id, model_name):
    """Model with smart icon."""
    if 'opus' in model_id.lower():
        return "🧠Opus"
    elif 'haiku' in model_id.lower():
        return "💨Haiku"
    else:
        return "⚡Sonnet"

def get_git_status():
    """Detailed git status."""
    try:
        # Branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=0.5
        )
        branch = result.stdout.strip() if result.returncode == 0 else 'main'
        
        # Changes count
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, timeout=0.5
        )
        changes = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        
        if changes > 0:
            return f"🌿{branch}*{changes}"
        else:
            return f"🌿{branch}"
    except:
        return "🌿main"

def get_agent_status():
    """Detailed agent activity."""
    # Check for active Task subagents
    # Would integrate with Claude's task tracking
    # Mock for demonstration
    agents = {
        'orchestrator': '🎯',
        'code-architect': '🏗️',
        'code-writer': '✍️',
        'debugger': '🐛',
        'api-researcher': '🔍',
        'pattern-analyzer': '📊'
    }
    
    # In reality, check for active Task processes or state files
    # For now, return None or mock active agent
    return None  # or "🎯orchestrator:active"

def get_mcp_detail():
    """Detailed MCP connection status."""
    servers = []
    
    # Check zulipchat-mcp
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'zulipchat-mcp'],
            capture_output=True, timeout=0.5
        )
        if result.returncode == 0:
            servers.append('zulip✓')
        else:
            servers.append('zulip✗')
    except:
        pass
    
    # Check context7
    if os.path.exists(os.path.expanduser('~/.config/claude/mcp.json')):
        servers.append('ctx7✓')
    
    # Check for other common MCPs
    if os.path.exists('.mcp.json'):
        with open('.mcp.json', 'r') as f:
            config = json.load(f)
            for server in config.get('servers', {}).keys():
                if server not in ['zulipchat-mcp', 'context7']:
                    servers.append(server[:4])
    
    return f"MCP[{','.join(servers)}]" if servers else "MCP[none]"

def get_permission_mode():
    """Get current permission mode."""
    # Would check Claude's actual mode
    # For now, use environment or default
    mode = os.environ.get('CLAUDE_MODE', 'code')
    return f"MODE:{mode}"

def format_session_tokens(tokens):
    """Format token usage for session."""
    if tokens < 1000:
        return f"📊{tokens} tok"
    elif tokens < 1000000:
        return f"📊{tokens//1000}k tok"
    else:
        return f"📊{tokens//1000000}M tok"

def main():
    try:
        # Read JSON input
        data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
        
        # Extract all data
        model = get_model_icon_and_name(
            data.get('model', {}).get('id', ''),
            data.get('model', {}).get('display_name', '')
        )
        
        git_status = get_git_status()
        
        workspace = data.get('workspace', {})
        folder = Path(workspace.get('current_dir', '.')).name
        
        tokens = data.get('cost', {}).get('total_tokens_used', 0)
        token_display = format_session_tokens(tokens)
        
        # Build status line with all details
        components = [model]
        
        # Add agent if active
        agent = get_agent_status()
        if agent:
            components.append(agent)
        
        components.extend([
            git_status,
            get_mcp_detail(),
            token_display,
            f"📁{folder}",
            get_permission_mode()
        ])
        
        # Rich separator
        status = " │ ".join(components)
        
        print(status)
        
    except Exception as e:
        print(f"⚡Sonnet │ 🌿main │ MCP[none] │ 📊0 tok │ MODE:code")

if __name__ == "__main__":
    main()