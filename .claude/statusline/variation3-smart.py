#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Variation 3: Context-Aware Smart
Philosophy: Adapt display to current activity, highlight what matters now
Example (idle): Sonnet • feat/v2 • zulipchat • 45k
Example (agent): 🔄 orchestrator → api-researcher • feat/v2 • 52k
Example (commit): ⚠️ GIT COMMIT • 5 files • feat/v2* • CHECK DIFF
"""

import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

class SmartStatus:
    def __init__(self, data):
        self.data = data
        self.model = self._get_model()
        self.tokens = data.get('cost', {}).get('total_tokens_used', 0)
        self.workspace = data.get('workspace', {})
        self.detect_context()
    
    def _get_model(self):
        """Get model short name."""
        model_id = self.data.get('model', {}).get('id', '').lower()
        if 'opus' in model_id:
            return "Opus"
        elif 'haiku' in model_id:
            return "Haiku"
        else:
            return "Sonnet"
    
    def detect_context(self):
        """Detect what's happening right now."""
        self.context = "normal"
        self.context_data = {}
        
        # Check for git operations
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'git commit'],
                capture_output=True, timeout=0.5
            )
            if result.returncode == 0:
                self.context = "git_commit"
                # Count staged files
                result = subprocess.run(
                    ['git', 'diff', '--cached', '--name-only'],
                    capture_output=True, text=True, timeout=0.5
                )
                self.context_data['files'] = len(result.stdout.strip().split('\n'))
                return
        except:
            pass
        
        # Check for active agents
        if self._check_agent_activity():
            self.context = "agent_active"
            return
        
        # Check for test running
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'pytest'],
                capture_output=True, timeout=0.5
            )
            if result.returncode == 0:
                self.context = "testing"
                return
        except:
            pass
        
        # Check for MCP server starting
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'zulipchat-mcp'],
                capture_output=True, timeout=0.5
            )
            if result.returncode == 0:
                self.context = "mcp_running"
                return
        except:
            pass
    
    def _check_agent_activity(self):
        """Check if agents are active."""
        # Would check Claude's Task tool usage
        # For now, mock based on token increase rate
        return False
    
    def _get_branch(self):
        """Get git branch."""
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
            
            return f"{branch}{has_changes}"
        except:
            return "main"
    
    def _format_tokens(self):
        """Smart token formatting."""
        if self.tokens < 10000:
            return f"{self.tokens//1000}k"
        elif self.tokens < 100000:
            return f"{self.tokens//1000}k"
        else:
            return f"{self.tokens//1000}k⚡"  # High usage indicator
    
    def build_status(self):
        """Build context-aware status line."""
        branch = self._get_branch()
        folder = Path(self.workspace.get('current_dir', '.')).name
        
        if self.context == "git_commit":
            # Highlight git commit activity
            files = self.context_data.get('files', 0)
            return f"⚠️ GIT COMMIT • {files} files • {branch} • CHECK DIFF"
        
        elif self.context == "agent_active":
            # Show agent workflow
            # Would show actual agent names from Task tracking
            return f"🔄 orchestrator → api-researcher • {branch} • {self._format_tokens()}"
        
        elif self.context == "testing":
            # Testing focus
            return f"🧪 TESTING • {self.model} • {branch} • {folder}"
        
        elif self.context == "mcp_running":
            # MCP server active
            return f"🟢 MCP ACTIVE • {self.model} • {branch} • {self._format_tokens()}"
        
        else:
            # Normal state - clean and simple
            tokens = self._format_tokens()
            
            # Check permission mode
            mode = ""
            if os.environ.get('CLAUDE_MODE') == 'yolo':
                mode = " • 🚀yolo"
            elif os.environ.get('CLAUDE_MODE') == 'plan':
                mode = " • 📋plan"
            
            return f"{self.model} • {branch} • {folder} • {tokens}{mode}"

def main():
    try:
        # Read JSON input
        data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
        
        # Create smart status
        status = SmartStatus(data)
        print(status.build_status())
        
    except Exception as e:
        # Fallback
        print(f"Sonnet • main • zulipchat • 0k")

if __name__ == "__main__":
    main()