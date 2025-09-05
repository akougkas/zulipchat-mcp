#!/usr/bin/env python3
"""
OpenCode Adapter for ZulipChat MCP

Generates OpenCode command files from the existing slash command logic.
Creates .opencode/commands/zulipchat/ directory with markdown command files.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any


def get_command_definitions() -> Dict[str, Dict[str, Any]]:
    """Extract command definitions from the existing slash command logic."""
    return {
        'summarize': {
            'description': 'Generate daily summary with message stats',
            'allowed_tools': ['mcp__zulipchat__get_daily_summary', 'mcp__zulipchat__get_messages', 'mcp__zulipchat__auto_summarize'],
            'content': """Generate a daily summary of Zulip activity using these steps:

1. Parse $ARGUMENTS to extract streams (comma-separated) and hours back
2. Use mcp__zulipchat__get_daily_summary with parsed streams and hours_back parameters
3. Format the results with statistics and highlight key conversations
4. Include message counts by stream and top contributors

Arguments: $ARGUMENTS
- Format: [streams] [hours] where streams is comma-separated list
- Example: general,development 48

The arguments will be used to:
- streams: Target specific streams (optional, defaults to all public streams)
- hours: Number of hours to look back (default: 24)"""
        },
        'prepare': {
            'description': 'Morning briefing with yesterday\'s highlights',
            'allowed_tools': ['mcp__zulipchat__get_daily_summary', 'mcp__zulipchat__get_messages', 'mcp__zulipchat__auto_summarize'],
            'content': """Create a morning briefing with yesterday's highlights and weekly overview:

1. Parse $ARGUMENTS to extract streams (comma-separated) and days back
2. Use mcp__zulipchat__get_daily_summary with parsed streams and hours_back (days * 24)
3. Use mcp__zulipchat__auto_summarize to generate detailed insights and weekly overview  
4. Format as a morning briefing with key insights and statistics
5. Include:
   - Yesterday's most active streams and topics
   - Weekly message statistics  
   - Top contributors
   - Key conversations and highlights

Arguments: $ARGUMENTS
- Format: [streams] [days] where streams is comma-separated list
- Example: general,team-updates 5

The arguments will be used to:
- streams: Target specific streams (optional, defaults to all public streams)
- days: Number of days for weekly overview (default: 7)"""
        },
        'catch_up': {
            'description': 'Quick catch-up for missed messages',
            'allowed_tools': ['mcp__zulipchat__get_messages', 'mcp__zulipchat__auto_summarize'],
            'content': """Generate a catch-up summary for missed messages:

1. Parse $ARGUMENTS to extract streams (comma-separated) and hours back
2. Use mcp__zulipchat__get_messages with parsed stream names and hours_back
3. Use mcp__zulipchat__auto_summarize with summary_type="brief" for quick overview
4. Group messages by stream and topic for easy scanning
5. Identify important conversations and key participants
6. Create a summary highlighting:
   - Total messages missed
   - Active streams and topics
   - Key contributors
   - Latest important discussions

Arguments: $ARGUMENTS
- Format: [streams] [hours] where streams is comma-separated list
- Example: general,development 4

The arguments will be used to:
- streams: Target specific streams (optional, defaults to all public streams)
- hours: Number of hours to look back (default: 8)"""
        }
    }


def generate_opencode_command_file(command_name: str, command_def: Dict[str, Any]) -> str:
    """Generate OpenCode markdown command file content."""
    tools_list = ', '.join([f'"{tool}"' for tool in command_def['allowed_tools']])
    
    frontmatter = f"""---
description: {command_def['description']}
allowed-tools: [{tools_list}]
---

"""

    return frontmatter + command_def['content']


def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def install_commands(target_dir: str | None = None, scope: str = 'user') -> None:
    """Install OpenCode command files to the specified directory."""
    if target_dir is None:
        if scope == 'user':
            # Default to user's local opencode commands directory
            home = Path.home()
            target_path = home / '.local' / 'opencode' / 'commands' / 'zulipchat'
        else:  # project scope
            target_path = Path.cwd() / '.opencode' / 'commands' / 'zulipchat'
    else:
        target_path = Path(target_dir) / 'zulipchat'

    print(f"Installing OpenCode commands to: {target_path}")
    print(f"Scope: {scope}")

    try:
        ensure_directory(target_path)
        commands = get_command_definitions()

        for command_name, command_def in commands.items():
            file_path = target_path / f"{command_name}.md"
            content = generate_opencode_command_file(command_name, command_def)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Created: {file_path}")

        print("\n🎉 OpenCode commands installed successfully!")
        print(f"📁 Commands available at: {target_path}")
        print("\n📖 Usage in OpenCode:")
        if scope == 'user':
            print("  /user:zulipchat:summarize [streams] [hours]")
            print("  /user:zulipchat:prepare [streams] [days]")
            print("  /user:zulipchat:catch_up [streams] [hours]")
        else:
            print("  /project:zulipchat:summarize [streams] [hours]")
            print("  /project:zulipchat:prepare [streams] [days]")
            print("  /project:zulipchat:catch_up [streams] [hours]")

    except Exception as e:
        print(f"❌ Error installing commands: {e}")
        sys.exit(1)


def list_commands() -> None:
    """List available commands and their descriptions."""
    print("Available ZulipChat Commands for OpenCode:")
    print("=" * 50)

    commands = get_command_definitions()
    for name, definition in commands.items():
        print(f"\n🔧 {name}")
        print(f"   Description: {definition['description']}")
        print(f"   Allowed Tools: {', '.join(definition['allowed_tools'])}")


def main():
    """Main entry point for the OpenCode adapter."""
    if len(sys.argv) < 2:
        print("OpenCode Adapter for ZulipChat MCP")
        print("\nUsage:")
        print("  uv run agent_adapters/opencode.py install [target_dir] [--scope user|project]")
        print("  uv run agent_adapters/opencode.py list")
        print("\nCommands:")
        print("  install    Install command files to OpenCode")
        print("  list       List available commands")
        print("\nOptions:")
        print("  --scope    Installation scope (user or project, default: user)")
        sys.exit(1)

    command = sys.argv[1].lower()
    scope = 'user'  # default scope

    # Parse scope option
    if '--scope' in sys.argv:
        scope_index = sys.argv.index('--scope')
        if scope_index + 1 < len(sys.argv):
            scope = sys.argv[scope_index + 1].lower()
            if scope not in ['user', 'project']:
                print("Error: Scope must be 'user' or 'project'")
                sys.exit(1)
            # Remove scope arguments from sys.argv for easier parsing
            sys.argv.pop(scope_index + 1)
            sys.argv.pop(scope_index)

    if command == 'install':
        target_dir = sys.argv[2] if len(sys.argv) > 2 else None
        install_commands(target_dir, scope)
    elif command == 'list':
        list_commands()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()