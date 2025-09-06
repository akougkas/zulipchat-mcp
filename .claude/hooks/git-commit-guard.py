#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Git commit guardian - validates before committing."""

import json
import sys
import subprocess
import re

def check_git_status():
    """Analyze what's about to be committed."""
    try:
        # Get staged files
        staged = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True, text=True
        ).stdout.strip().split('\n')
        
        # Get diff stats
        stats = subprocess.run(
            ['git', 'diff', '--cached', '--stat'],
            capture_output=True, text=True
        ).stdout
        
        # Check for sensitive patterns
        diff = subprocess.run(
            ['git', 'diff', '--cached'],
            capture_output=True, text=True
        ).stdout
        
        issues = []
        
        # Check for secrets
        secret_patterns = [
            r'(?i)(api[_-]?key|secret|token|password)\s*=\s*["\']',
            r'ZULIP_API_KEY\s*=\s*["\'][^\'\"]+["\']',
            r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, diff):
                issues.append("⚠️  Potential secrets detected in diff")
                break
        
        # Check for debug code
        if 'console.log' in diff or 'print(' in diff or 'breakpoint()' in diff:
            issues.append("⚠️  Debug statements detected")
        
        # Check for large commits
        if len(staged) > 20:
            issues.append(f"⚠️  Large commit: {len(staged)} files")
        
        # Output for user verification
        print("\n🔍 Git Commit Verification")
        print("=" * 40)
        print(f"Files to commit: {len(staged)}")
        print(stats)
        
        if issues:
            print("\n⚠️  WARNINGS:")
            for issue in issues:
                print(f"  {issue}")
            print("\n❓ Proceed with commit? Review carefully!")
            # Exit 2 to block and ask for confirmation
            sys.exit(2)
        else:
            print("✅ Commit looks clean")
            
    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
    
    sys.exit(0)

# Main execution
try:
    data = json.load(sys.stdin)
    tool_name = data.get('tool_name', '')
    command = data.get('tool_input', {}).get('command', '')
    
    # Detect git commit commands
    if tool_name == 'Bash' and 'git commit' in command:
        check_git_status()
        
except Exception:
    pass

sys.exit(0)