#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Validate Python code changes for production readiness."""

import json
import sys
import subprocess
from pathlib import Path

def validate_python_file(file_path):
    """Run validation checks on Python file."""
    if not file_path.endswith('.py') or not Path(file_path).exists():
        return
    
    issues = []
    
    # Check file size (might indicate over-engineering)
    size = Path(file_path).stat().st_size
    if size > 50000:  # 50KB
        issues.append(f"Large file: {size/1000:.1f}KB - consider splitting")
    
    # Quick syntax check
    result = subprocess.run(
        ['python', '-m', 'py_compile', file_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        issues.append("Syntax error detected!")
        
    # Check for common issues
    with open(file_path, 'r') as f:
        content = f.read()
        
        # Missing type hints in function definitions
        if 'def ' in content and '->' not in content:
            issues.append("Missing return type hints")
            
        # TODO comments (shouldn't commit incomplete work)
        if 'TODO' in content or 'FIXME' in content:
            issues.append("Unresolved TODO/FIXME comments")
            
        # Hardcoded values that should be config
        if 'localhost' in content or '127.0.0.1' in content:
            issues.append("Hardcoded localhost - use config")
    
    if issues:
        # Launch background validation agent
        print(json.dumps({
            "decision": "block",
            "reason": f"Code issues in {Path(file_path).name}:\n" + "\n".join(f"• {i}" for i in issues),
            "suppressOutput": False
        }))
        sys.exit(2)

# Main
try:
    data = json.load(sys.stdin)
    tool_name = data.get('tool_name', '')
    
    if tool_name in ['Write', 'Edit', 'MultiEdit']:
        file_path = data.get('tool_input', {}).get('file_path', '')
        
        # Only validate on significant edits (not minor changes)
        if tool_name == 'Write' or 'MultiEdit' in tool_name:
            validate_python_file(file_path)
            
except Exception:
    pass

sys.exit(0)