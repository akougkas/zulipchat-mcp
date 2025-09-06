#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
WARP Framework Status Line - Max Plan Optimized
Shows workflow progress, token usage, and agent status
"""
import json
import sys
import os
from datetime import datetime

def format_tokens(tokens_used, tokens_limit):
    """Format token usage with color coding for Max plan users"""
    if tokens_limit == 0:
        return "🚀 Unlimited"
    
    percentage = (tokens_used / tokens_limit) * 100
    
    if percentage < 50:
        color = "32"  # Green
    elif percentage < 80:
        color = "33"  # Yellow  
    else:
        color = "31"  # Red
        
    return f"\033[{color}m{tokens_used:,}/{tokens_limit:,} ({percentage:.1f}%)\033[0m"

def get_workflow_status():
    """Check for active WARP workflow manifest"""
    manifest_dirs = [
        os.path.expanduser("~/.claude/outputs"),
        "."
    ]
    
    for manifest_dir in manifest_dirs:
        if os.path.exists(manifest_dir):
            # Look for recent manifest files
            manifest_files = []
            try:
                for root, dirs, files in os.walk(manifest_dir):
                    for file in files:
                        if file == "manifest.json":
                            manifest_files.append(os.path.join(root, file))
            except:
                continue
                
            # Get most recent manifest
            if manifest_files:
                latest_manifest = max(manifest_files, key=os.path.getmtime, default=None)
                if latest_manifest:
                    try:
                        with open(latest_manifest, 'r') as f:
                            manifest = json.load(f)
                            return manifest
                    except:
                        continue
    
    return None

def get_git_info():
    """Get git branch and status"""
    try:
        import subprocess
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                       stderr=subprocess.DEVNULL).decode().strip()
        
        # Check for uncommitted changes
        status = subprocess.check_output(['git', 'status', '--porcelain'], 
                                       stderr=subprocess.DEVNULL).decode().strip()
        
        if status:
            return f"🌱 {branch}*"
        else:
            return f"🌱 {branch}"
    except:
        return ""

def main():
    try:
        # Read the JSON input from Claude Code
        input_data = json.loads(sys.argv[1])
        
        model = input_data.get('model', 'unknown')
        cwd = input_data.get('cwd', '').replace(os.path.expanduser('~'), '~')
        tokens_used = input_data.get('tokens_used', 0)
        tokens_limit = input_data.get('tokens_limit', 0)
        
        # Status components
        components = []
        
        # WARP workflow status
        workflow = get_workflow_status()
        if workflow:
            workflow_name = workflow.get('workflow_name', 'Unknown')[:20]
            current_phase = "Unknown"
            completed_agents = 0
            total_agents = 0
            
            # Count agents and find current phase
            for phase in workflow.get('phases', []):
                phase_agents = phase.get('agents', [])
                total_agents += len(phase_agents)
                
                completed_in_phase = sum(1 for agent in phase_agents if agent.get('status') == 'completed')
                completed_agents += completed_in_phase
                
                if phase.get('status') == 'active':
                    current_phase = phase.get('phase_type', 'Unknown')
            
            # Workflow status with progress
            if completed_agents == total_agents and total_agents > 0:
                warp_status = f"🎯 {workflow_name}: ✅ Complete"
            elif total_agents > 0:
                progress_bar = "▰" * (completed_agents * 5 // total_agents) + "▱" * (5 - completed_agents * 5 // total_agents)
                warp_status = f"🎯 {workflow_name}: {current_phase} [{progress_bar}] {completed_agents}/{total_agents}"
            else:
                warp_status = f"🎯 {workflow_name}: {current_phase}"
                
            components.append(warp_status)
        
        # Model and tokens (optimized for Max plan)
        if tokens_limit > 0:
            token_info = f"🧠 {model.split('-')[-1]} • {format_tokens(tokens_used, tokens_limit)}"
        else:
            token_info = f"🧠 {model.split('-')[-1]} • 🚀 Max Plan"
        components.append(token_info)
        
        # Git info
        git_info = get_git_info()
        if git_info:
            components.append(git_info)
        
        # Working directory (shortened)
        if len(cwd) > 25:
            cwd_display = "..." + cwd[-22:]
        else:
            cwd_display = cwd
        components.append(f"📁 {cwd_display}")
        
        # Join all components
        status_line = " | ".join(components)
        
        # Add timestamp for active workflows
        if workflow:
            now = datetime.now().strftime("%H:%M")
            status_line += f" | ⏰ {now}"
        
        print(status_line)
        
    except Exception as e:
        # Fallback minimal status
        print(f"🎯 WARP Ready | 🧠 Max Plan | 📁 {os.getcwd().split('/')[-1]}")

if __name__ == "__main__":
    main()