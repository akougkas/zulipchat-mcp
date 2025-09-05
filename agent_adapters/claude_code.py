#!/usr/bin/env python3
"""
Claude Code Adapter for ZulipChat MCP

Generates Claude Code command files from the existing slash command logic.
Creates .claude/commands/zulipchat/ directory with markdown command files.
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


def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def install_commands(target_dir: str | None = None) -> None:
    """Install Claude Code command files to the specified directory."""
    if target_dir is None:
        # Default to user's home .claude/commands directory
        home = Path.home()
        target_path = home / '.claude' / 'commands' / 'zulipchat'
    else:
        target_path = Path(target_dir) / 'zulipchat'

    print(f"Installing Claude Code commands to: {target_path}")

    try:
        ensure_directory(target_path)
        commands = get_command_definitions()

        for command_name, command_def in commands.items():
            file_path = target_path / f"{command_name}.md"
            content = generate_claude_command_file(command_name, command_def)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Created: {file_path}")

        print("\n🎉 Claude Code commands installed successfully!")
        print(f"📁 Commands available at: {target_path}")
        print("\n📖 Usage in Claude Code:")
        print("  /zulipchat:summarize [streams] [hours]")
        print("  /zulipchat:prepare [streams] [days]")
        print("  /zulipchat:catch_up [streams] [hours]")

    except Exception as e:
        print(f"❌ Error installing commands: {e}")
        sys.exit(1)


def list_commands() -> None:
    """List available commands and their descriptions."""
    print("Available ZulipChat Commands for Claude Code:")
    print("=" * 50)

    commands = get_command_definitions()
    for name, definition in commands.items():
        print(f"\n🔧 {name}")
        print(f"   Description: {definition['description']}")
        print(f"   Arguments: {definition['argument_hint']}")


def main():
    """Main entry point for the Claude Code adapter."""
    if len(sys.argv) < 2:
        print("Claude Code Adapter for ZulipChat MCP")
        print("\nUsage:")
        print("  uv run agent_adapters/claude_code.py install [target_dir]")
        print("  uv run agent_adapters/claude_code.py list")
        print("\nCommands:")
        print("  install    Install command files to Claude Code")
        print("  list       List available commands")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'install':
        target_dir = sys.argv[2] if len(sys.argv) > 2 else None
        install_commands(target_dir)
    elif command == 'list':
        list_commands()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()