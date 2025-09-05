#!/usr/bin/env python3
"""
Unified Agent Setup for ZulipChat MCP

Consolidates command generation for Claude Code, Gemini CLI, and OpenCode.
Creates command files for multiple AI agents from the existing MCP tools.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List


def get_command_definitions() -> Dict[str, Dict[str, Any]]:
    """Extract command definitions from the existing MCP tools."""
    return {
        'summarize': {
            'description': 'Generate daily summary with message stats',
            'argument_hint': '[streams] [hours]',
            'content': """Generate a daily summary of Zulip activity using these steps:

1. Parse streams from $1 (comma-separated) and hours from $2
2. Use mcp__zulipchat__get_daily_summary with the parsed streams and hours_back parameters
3. Format the results with statistics and highlight key conversations
4. Include message counts, active streams, and top contributors

Arguments:
- $1: Comma-separated list of stream names (optional)
- $2: Number of hours to look back (default: 24)

Example: /zulipchat:summarize general,development 48"""
        },
        'prepare': {
            'description': 'Morning briefing with yesterday\'s highlights',
            'argument_hint': '[streams] [days]',
            'content': """Create a morning briefing with yesterday's highlights and weekly overview:

1. Parse streams from $1 (comma-separated) and days from $2
2. Use mcp__zulipchat__get_daily_summary with parsed streams and hours_back (days * 24)
3. Use mcp__zulipchat__auto_summarize to generate detailed insights
4. Format as a morning briefing with:
   - Yesterday's most active streams and topics
   - Weekly message statistics
   - Top contributors
   - Key conversations and highlights

Arguments:
- $1: Comma-separated list of stream names (optional)
- $2: Number of days for weekly overview (default: 7)

Example: /zulipchat:prepare general,team-updates 5"""
        },
        'catch_up': {
            'description': 'Quick catch-up for missed messages',
            'argument_hint': '[streams] [hours]',
            'content': """Generate a catch-up summary for missed messages:

1. Parse streams from $1 (comma-separated) and hours from $2
2. Use mcp__zulipchat__get_messages with parsed stream_name and hours_back parameters
3. Use mcp__zulipchat__auto_summarize with summary_type="brief" for quick overview
4. Create a summary highlighting:
   - Total messages missed
   - Active streams and topics
   - Key contributors
   - Latest important discussions

Arguments:
- $1: Comma-separated list of stream names (optional, defaults to all public streams)
- $2: Number of hours to look back (default: 8)

Example: /zulipchat:catch_up general,development 4"""
        },
        'afk': {
            'description': 'Toggle Away From Keyboard mode for notifications',
            'argument_hint': '[on|off|toggle] [reason] [hours]',
            'content': """Toggle AFK (Away From Keyboard) mode for ZulipChat MCP notifications:

1. Parse command from $1 (on/off/toggle), reason from $2, and auto-return hours from $3
2. Import and use afk_state module to manage AFK state:
   - If "on": activate AFK with reason and auto-return
   - If "off": deactivate AFK
   - If "toggle" or empty: toggle current state
3. When AFK is ON: Claude Code sends notifications to Zulip
4. When AFK is OFF: Claude Code runs quietly without notifications
5. Auto-return: Automatically deactivates after specified hours

Arguments:
- $1: Command - "on", "off", or "toggle" (optional, defaults to toggle)
- $2: Reason for going AFK (optional, e.g., "Lunch break")
- $3: Auto-return after hours (optional, e.g., 1.5)

Examples:
- /zulipchat:afk - Toggle AFK mode
- /zulipchat:afk on "Lunch break" 1 - Go AFK for lunch, auto-return in 1 hour
- /zulipchat:afk off - Back at keyboard

Implementation:
```python
from zulipchat_mcp.afk_state import get_afk_state
afk = get_afk_state()

# Parse arguments
command = "$1" or "toggle"
reason = "$2" if "$2" else None  
hours = float("$3") if "$3" else None

# Execute command
if command == "on":
    result = afk.activate(reason, hours)
elif command == "off":
    result = afk.deactivate()
else:
    result = afk.toggle(reason, hours)

# Show status
status = afk.get_status()
print(f"AFK: {status['afk']}")
if status['afk']:
    print(f"Reason: {status['reason']}")
    if status.get('auto_return_in'):
        print(f"Auto-return in: {status['auto_return_in']} hours")
```"""
        }
    }


def generate_claude_command_file(command_name: str, command_def: Dict[str, Any]) -> str:
    """Generate Claude Code markdown command file content."""
    frontmatter = f"""---
allowed-tools: mcp__zulipchat__*
description: {command_def['description']}
argument-hint: {command_def['argument_hint']}
---

"""

    return frontmatter + command_def['content']


def generate_gemini_command_file(command_name: str, command_def: Dict[str, Any]) -> str:
    """Generate Gemini CLI TOML command file content."""
    description = command_def['description']
    prompt = command_def['content']

    # Simple TOML generation
    toml_content = f'''description = "{description}"
prompt = """
{prompt}
"""'''

    return toml_content


def generate_opencode_command_file(command_name: str, command_def: Dict[str, Any]) -> str:
    """Generate OpenCode markdown command file content."""
    tools_list = 'mcp__zulipchat__get_daily_summary, mcp__zulipchat__get_messages, mcp__zulipchat__auto_summarize'

    frontmatter = f"""---
description: {command_def['description']}
allowed-tools: [{tools_list}]
---

"""

    return frontmatter + command_def['content']


def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def install_claude_commands(target_dir: str | None = None) -> None:
    """Install Claude Code command files."""
    if target_dir is None:
        home = Path.home()
        target_path = home / '.claude' / 'commands' / 'zulipchat'
    else:
        target_path = Path(target_dir) / 'zulipchat'

    print(f"Installing Claude Code commands to: {target_path}")
    ensure_directory(target_path)

    commands = get_command_definitions()
    for command_name, command_def in commands.items():
        file_path = target_path / f"{command_name}.md"
        content = generate_claude_command_file(command_name, command_def)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Created: {file_path}")


def install_gemini_commands(target_dir: str | None = None, scope: str = 'user') -> None:
    """Install Gemini CLI command files."""
    if target_dir is None:
        home = Path.home()
        if scope == 'user':
            target_path = home / '.gemini' / 'commands' / 'zulipchat'
        else:  # project scope
            target_path = Path.cwd() / '.gemini' / 'commands' / 'zulipchat'
    else:
        target_path = Path(target_dir) / 'zulipchat'

    print(f"Installing Gemini CLI commands to: {target_path}")
    print(f"Scope: {scope}")
    ensure_directory(target_path)

    commands = get_command_definitions()
    for command_name, command_def in commands.items():
        file_path = target_path / f"{command_name}.toml"
        content = generate_gemini_command_file(command_name, command_def)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Created: {file_path}")


def install_opencode_commands(target_dir: str | None = None, scope: str = 'user') -> None:
    """Install OpenCode command files."""
    if target_dir is None:
        if scope == 'user':
            home = Path.home()
            target_path = home / '.local' / 'opencode' / 'commands' / 'zulipchat'
        else:  # project scope
            target_path = Path.cwd() / '.opencode' / 'commands' / 'zulipchat'
    else:
        target_path = Path(target_dir) / 'zulipchat'

    print(f"Installing OpenCode commands to: {target_path}")
    print(f"Scope: {scope}")
    ensure_directory(target_path)

    commands = get_command_definitions()
    for command_name, command_def in commands.items():
        file_path = target_path / f"{command_name}.md"
        content = generate_opencode_command_file(command_name, command_def)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Created: {file_path}")


def list_commands() -> None:
    """List available commands and their descriptions."""
    print("Available ZulipChat Commands:")
    print("=" * 50)

    commands = get_command_definitions()
    for name, definition in commands.items():
        print(f"\n🔧 {name}")
        print(f"   Description: {definition['description']}")
        print(f"   Arguments: {definition['argument_hint']}")


def main():
    """Main entry point for the unified agent setup."""
    if len(sys.argv) < 2:
        print("Unified Agent Setup for ZulipChat MCP")
        print("\nUsage:")
        print("  uv run agent_adapters/setup_agents.py <agent> [options]")
        print("\nAgents:")
        print("  claude     Install Claude Code commands")
        print("  gemini     Install Gemini CLI commands")
        print("  opencode   Install OpenCode commands")
        print("  all        Install all agent commands")
        print("  list       List available commands")
        print("\nOptions:")
        print("  --scope    Installation scope (user or project, default: user)")
        print("  --dir      Custom installation directory")
        sys.exit(1)

    agent = sys.argv[1].lower()
    scope = 'user'
    target_dir = None

    # Parse additional arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--scope' and i + 1 < len(sys.argv):
            scope = sys.argv[i + 1].lower()
            if scope not in ['user', 'project']:
                print("Error: Scope must be 'user' or 'project'")
                sys.exit(1)
            i += 2
        elif sys.argv[i] == '--dir' and i + 1 < len(sys.argv):
            target_dir = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    try:
        if agent == 'claude':
            install_claude_commands(target_dir)
        elif agent == 'gemini':
            install_gemini_commands(target_dir, scope)
        elif agent == 'opencode':
            install_opencode_commands(target_dir, scope)
        elif agent == 'all':
            print("Installing commands for all agents...")
            install_claude_commands(target_dir)
            print()
            install_gemini_commands(target_dir, scope)
            print()
            install_opencode_commands(target_dir, scope)
        elif agent == 'list':
            list_commands()
        else:
            print(f"Unknown agent: {agent}")
            sys.exit(1)

        if agent in ['claude', 'gemini', 'opencode', 'all']:
            print("\n🎉 Agent commands installed successfully!")
            print("\n📖 Usage:")
            if agent == 'claude' or agent == 'all':
                print("  Claude Code: /zulipchat:summarize [streams] [hours]")
            if agent == 'gemini' or agent == 'all':
                print("  Gemini CLI:  /zulipchat:summarize [streams] [hours]")
            if agent == 'opencode' or agent == 'all':
                if scope == 'user':
                    print("  OpenCode:    /user:zulipchat:summarize [streams] [hours]")
                else:
                    print("  OpenCode:    /project:zulipchat:summarize [streams] [hours]")

    except Exception as e:
        print(f"❌ Error installing commands: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()