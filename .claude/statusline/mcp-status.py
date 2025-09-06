#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Enhanced MCP status line with agent tracking and token usage."""

import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

def get_git_info():
    """Get current git branch and status."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=1
        )
        branch = result.stdout.strip() if result.returncode == 0 else 'main'
        
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, timeout=1
        )
        has_changes = '*' if result.stdout.strip() else ''
        
        return f"{branch}{has_changes}"
    except:
        return "no-git"

def get_active_agent():
    """Check for active subagent from recent Task calls."""
    # Look for agent activity markers
    marker_file = Path.home() / '.claude' / 'active-agent'
    if marker_file.exists():
        try:
            with open(marker_file, 'r') as f:
                agent_info = f.read().strip()
                # Check if file is recent (within last 60 seconds)
                if (datetime.now().timestamp() - marker_file.stat().st_mtime) < 60:
                    return agent_info
        except:
            pass
    
    # Check running processes for subagent indicators
    try:
        result = subprocess.run(
            ['pgrep', '-af', 'Task.*agent'],
            capture_output=True, text=True, timeout=1
        )
        if result.stdout:
            # Extract agent name from process
            for line in result.stdout.split('\n'):
                if 'orchestrator' in line:
                    return "🎯ORCH"
                elif 'architect' in line:
                    return "🏗️ARCH"
                elif 'writer' in line:
                    return "✍️WRITE"
                elif 'debugger' in line:
                    return "🐛DEBUG"
                elif 'researcher' in line:
                    return "🔍RSRCH"
    except:
        pass
    
    return None

def format_tokens(tokens_used, tokens_limit):
    """Format token usage with visual indicator."""
    if tokens_limit == 0:
        # Unlimited/Max plan
        if tokens_used < 1000:
            return f"{tokens_used}"
        elif tokens_used < 10000:
            return f"{tokens_used/1000:.1f}k"
        else:
            return f"{tokens_used/1000:.0f}k"
    else:
        # Limited plan - show percentage
        pct = (tokens_used / tokens_limit) * 100
        if pct < 50:
            symbol = "🟢"
        elif pct < 80:
            symbol = "🟡"
        else:
            symbol = "🔴"
        return f"{symbol}{pct:.0f}%"

def get_workflow_progress():
    """Check for workflow progress from todo lists or manifests."""
    # Check for active todos
    todo_file = Path.home() / '.claude' / 'todos' / 'current.json'
    if todo_file.exists():
        try:
            with open(todo_file, 'r') as f:
                todos = json.load(f)
                total = len(todos)
                completed = sum(1 for t in todos if t.get('status') == 'completed')
                in_progress = sum(1 for t in todos if t.get('status') == 'in_progress')
                
                if total > 0:
                    if in_progress > 0:
                        # Show progress bar
                        filled = int((completed / total) * 5)
                        bar = "▰" * filled + "▱" * (5 - filled)
                        return f"[{bar}] {completed}/{total}"
                    elif completed == total:
                        return "✅ALL"
        except:
            pass
    
    return None

def get_mcp_status():
    """Check MCP server status."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'zulipchat-mcp'],
            capture_output=True, timeout=1
        )
        return "🟢" if result.returncode == 0 else "⭕"
    except:
        return "?"

def main():
    try:
        # Read JSON input
        input_data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
        
        # Extract information
        model = input_data.get('model', {})
        model_name = model.get('display_name', 'Unknown')
        model_id = model.get('id', '')
        
        workspace = input_data.get('workspace', {})
        current_dir = workspace.get('current_dir', os.getcwd())
        
        cost_info = input_data.get('cost', {})
        total_cost = cost_info.get('total_cost_usd', 0)
        total_tokens = cost_info.get('total_tokens_used', 0)
        token_limit = cost_info.get('tokens_limit', 0)
        lines_changed = cost_info.get('total_lines_added', 0) + cost_info.get('total_lines_removed', 0)
        
        # Build status components
        components = []
        
        # Active agent (if any)
        agent = get_active_agent()
        if agent:
            components.append(f"\033[35m{agent}\033[0m")  # Magenta for agent
        
        # Workflow progress
        progress = get_workflow_progress()
        if progress:
            components.append(progress)
        
        # Model indicator (smart: Opus=🧠, Sonnet=⚡, Haiku=💨)
        if 'opus' in model_id.lower():
            model_icon = "🧠"
        elif 'haiku' in model_id.lower():
            model_icon = "💨"
        else:
            model_icon = "⚡"
        components.append(f"{model_icon}{model_name[:3]}")
        
        # Token usage
        if total_tokens > 0 or token_limit > 0:
            token_display = format_tokens(total_tokens, token_limit)
            components.append(f"🪙{token_display}")
        
        # Git status
        git_info = get_git_info()
        if git_info != "no-git":
            if '*' in git_info:
                components.append(f"\033[33m🌿{git_info}\033[0m")  # Yellow for changes
            else:
                components.append(f"🌿{git_info}")
        
        # Code changes indicator
        if lines_changed > 0:
            if lines_changed < 10:
                change_icon = "•"
            elif lines_changed < 50:
                change_icon = "••"
            else:
                change_icon = "•••"
            components.append(f"Δ{change_icon}")
        
        # MCP server
        mcp = get_mcp_status()
        components.append(f"MCP{mcp}")
        
        # Directory (compact)
        dir_name = Path(current_dir).name
        if len(dir_name) > 15:
            dir_name = f"…{dir_name[-12:]}"
        components.append(f"📁{dir_name}")
        
        # Cost if significant
        if total_cost > 0.01:
            if total_cost < 1:
                cost_str = f"{int(total_cost * 100)}¢"
            else:
                cost_str = f"${total_cost:.2f}"
            components.append(f"\033[36m{cost_str}\033[0m")  # Cyan for cost
        
        # Join with smart separators
        status_line = " │ ".join(components)
        
        # Add activity indicator
        if agent:
            status_line = "● " + status_line  # Active dot
        else:
            status_line = "  " + status_line
        
        print(status_line)
        
    except Exception as e:
        # Minimal fallback
        print(f"MCP │ zulipchat │ err:{str(e)[:10]}")

if __name__ == "__main__":
    main()