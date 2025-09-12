#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Variation 2: Information-Rich Developer - FIXED
Philosophy: Show all technical details, use icons smartly, developer-focused, reactive
Example: ⚡Sonnet │ 🌿rework-v2.5.0*2 │ MCP[zulip✓,ctx7✓] │ 🟢25k/100k │ 📁zulipchat-mcp │ ⚡coding:mcp-fixes
"""

import json
import sys
import os
import subprocess
import socket
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

def get_model_icon_and_name(model_data: Optional[Dict[str, Any]]) -> str:
    """Model with smart icon - properly detect from data."""
    if not model_data:
        return "⚡Sonnet"
        
    model_id = model_data.get('id', '')
    model_name = model_data.get('display_name', '')
    
    # Check both id and display_name for model type
    full_text = f"{model_id} {model_name}".lower()
    
    if 'opus' in full_text:
        return "🧠Opus"
    elif 'haiku' in full_text:
        return "💨Haiku"
    elif 'sonnet' in full_text:
        return "⚡Sonnet"
    else:
        # Fallback - try to detect from model ID patterns
        if 'claude-3-opus' in model_id.lower():
            return "🧠Opus"
        elif 'claude-3-haiku' in model_id.lower():
            return "💨Haiku"
        elif 'sonnet' in model_id.lower():
            return "⚡Sonnet"
        else:
            return "🤖AI"

def get_git_status() -> str:
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

def is_port_open(host: str, port: int, timeout: float = 0.1) -> bool:
    """Check if a port is open (for MCP server detection)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except:
        return False

def get_mcp_detail() -> str:
    """Reactive MCP connection status - check actual connectivity."""
    servers = []
    
    # Check zulipchat-mcp (look for actual running process and connectivity)
    zulip_running = False
    try:
        # Check if process is running
        result = subprocess.run(
            ['pgrep', '-f', 'zulipchat.*mcp|mcp.*zulip'],
            capture_output=True, timeout=0.3
        )
        if result.returncode == 0:
            zulip_running = True
    except:
        pass
    
    servers.append('zulip✓' if zulip_running else 'zulip✗')
    
    # Check context7 - look for actual MCP config and running state
    ctx7_active = False
    try:
        # Check Claude Code MCP config
        claude_config = os.path.expanduser('~/.config/claude/mcp.json')
        if os.path.exists(claude_config):
            with open(claude_config, 'r') as f:
                config = json.load(f)
                if 'context7' in config.get('servers', {}):
                    ctx7_active = True
    except:
        pass
    
    servers.append('ctx7✓' if ctx7_active else 'ctx7✗')
    
    # Check for filesystem MCP (common)
    fs_mcp = os.path.exists(os.path.expanduser('~/.config/claude/mcp.json'))
    if fs_mcp:
        servers.append('fs✓')
    
    return f"MCP[{','.join(servers)}]"

def get_activity_summary() -> str:
    """Get current activity/task summary instead of useless MODE."""
    # Try to detect current activity from various sources
    
    # Check if we're in a git repo and what we might be working on
    try:
        # Get recent git activity
        result = subprocess.run(
            ['git', 'log', '--oneline', '-1'],
            capture_output=True, text=True, timeout=0.3
        )
        if result.returncode == 0:
            last_commit = result.stdout.strip()
            if last_commit:
                # Extract activity type from commit message
                if 'feat:' in last_commit.lower():
                    return "⚡coding:new-feature"
                elif 'fix:' in last_commit.lower():
                    return "🔧coding:bugfix"
                elif 'refactor:' in last_commit.lower():
                    return "♻️coding:refactor"
                elif 'test:' in last_commit.lower():
                    return "🧪coding:testing"
                elif 'docs:' in last_commit.lower():
                    return "📝coding:docs"
    except:
        pass
    
    # Check if there are modified files to infer activity
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True, text=True, timeout=0.3
        )
        if result.returncode == 0 and result.stdout.strip():
            files = result.stdout.strip().split('\n')
            if any('.py' in f for f in files):
                return "⚡coding:python"
            elif any('.js' in f or '.ts' in f for f in files):
                return "⚡coding:js/ts"
            elif any('.md' in f for f in files):
                return "📝coding:docs"
            elif any('test' in f.lower() for f in files):
                return "🧪coding:testing"
    except:
        pass
    
    # Default activity
    return "⚡coding:active"

def format_context_usage(data: Dict[str, Any]) -> str:
    """Dynamic context window analyzer with color coding."""
    # Claude 4 Sonnet has ~200k context window
    # Try to get actual token usage from multiple sources
    
    total_tokens = 0
    max_context = 200000  # Default for Sonnet
    
    # Try different data paths for token count
    if 'cost' in data:
        cost_data = data['cost']
        total_tokens = (
            cost_data.get('total_tokens_used', 0) or
            cost_data.get('input_tokens', 0) + cost_data.get('output_tokens', 0) or
            cost_data.get('prompt_tokens', 0) + cost_data.get('completion_tokens', 0)
        )
    
    # Alternative paths
    if total_tokens == 0:
        if 'usage' in data:
            usage = data['usage']
            total_tokens = (
                usage.get('total_tokens', 0) or
                usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            )
    
    # If still 0, try to parse transcript for better estimation
    if total_tokens == 0 and 'transcript_path' in data:
        try:
            transcript_path = data['transcript_path']
            if os.path.exists(transcript_path):
                with open(transcript_path, 'r') as f:
                    transcript = f.read()
                    # Better estimation: ~3.5 chars per token for Claude
                    total_tokens = len(transcript) // 4
        except:
            pass
    
    # If still 0, try to estimate from conversation length
    if total_tokens == 0 and 'messages' in data:
        # Rough estimation: ~4 chars per token
        try:
            messages = data['messages']
            total_chars = sum(len(str(msg)) for msg in messages)
            total_tokens = total_chars // 4
        except:
            pass
    
    # Adjust max_context based on model
    model_data = data.get('model', {})
    if model_data:
        model_id = model_data.get('id', '').lower()
        if 'opus' in model_id:
            max_context = 200000
        elif 'haiku' in model_id:
            max_context = 200000
        elif 'sonnet' in model_id:
            max_context = 200000
    
    # Calculate percentage
    if max_context > 0:
        percentage = (total_tokens / max_context) * 100
    else:
        percentage = 0
    
    # Format with color coding
    if total_tokens < 1000:
        token_str = f"{total_tokens}"
    elif total_tokens < 1000000:
        token_str = f"{total_tokens//1000}k"
    else:
        token_str = f"{total_tokens//1000000}M"
    
    max_str = f"{max_context//1000}k"
    
    # Color coding based on percentage
    if percentage < 40:
        return f"🟢{token_str}/{max_str}"
    elif percentage < 70:
        return f"🟠{token_str}/{max_str}"
    else:
        return f"🔴{token_str}/{max_str}"

def main() -> None:
    """Main entry point - reads JSON from stdin/argv and outputs status line."""
    try:
        # Read JSON input from stdin (Claude Code standard)
        data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
        
        # Extract all data with proper error handling
        model = get_model_icon_and_name(data.get('model'))
        git_status = get_git_status()
        
        workspace = data.get('workspace', {})
        folder = Path(workspace.get('current_dir', '.')).name
        
        context_usage = format_context_usage(data)
        activity = get_activity_summary()
        mcp_status = get_mcp_detail()
        
        # Build dynamic status line
        components = [
            model,
            git_status,
            mcp_status,
            context_usage,
            f"📁{folder}",
            activity
        ]
        
        # Rich separator
        status = " │ ".join(components)
        print(status)
        
    except Exception as e:
        # Graceful fallback with basic info
        try:
            model = "⚡Sonnet"  # Default assumption
            git_branch = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, timeout=0.3
            ).stdout.strip() or "main"
            folder = Path('.').name
            print(f"{model} │ 🌿{git_branch} │ MCP[unknown] │ 🟢0/200k │ 📁{folder} │ ⚡coding:active")
        except:
            print(f"⚡Sonnet │ 🌿main │ MCP[unknown] │ 🟢0/200k │ 📁project │ ⚡coding:active")

if __name__ == "__main__":
    main()