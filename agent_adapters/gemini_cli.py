#!/usr/bin/env python3
"""
Gemini CLI Adapter for ZulipChat MCP

Generates Gemini CLI command files from the existing slash command logic.
Creates .gemini/commands/zulipchat/ directory with TOML command files.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

# TOML generation without external dependencies


def get_command_definitions() -> Dict[str, Dict[str, Any]]:
    """Extract command definitions from the existing slash command logic."""
    return {
        'summarize': {
            'description': 'Generate daily summary with message stats',
            'prompt': """You have access to a ZulipChat MCP server. Generate a daily summary by:

1. Parse arguments {{args}} to get streams (comma-separated) and hours_back
2. Use mcp__zulipchat__get_daily_summary with the parsed streams and hours_back parameters
3. Format the results with statistics and highlighting key conversations
4. Include message counts by stream and top contributors

Arguments: streams (comma-separated) and hours back (default 24)
Example: general,development 48"""
        },
        'prepare': {
            'description': 'Morning briefing with yesterday\'s highlights',
            'prompt': """Create a morning briefing report using the ZulipChat MCP server:

1. Parse arguments {{args}} to get streams (comma-separated) and days back
2. Use mcp__zulipchat__get_daily_summary with parsed streams and hours_back (days * 24)
3. Use mcp__zulipchat__auto_summarize to generate detailed insights and weekly overview
4. Format as a morning briefing with key insights and statistics
5. Include top contributors and active topics from the specified time period

Arguments: streams (comma-separated) and days back (default 7)
Example: general,team-updates 5"""
        },
        'catch_up': {
            'description': 'Quick catch-up for missed messages',
            'prompt': """Generate a catch-up summary using the ZulipChat MCP server:

1. Parse arguments {{args}} to get streams (comma-separated) and hours back
2. Use mcp__zulipchat__get_messages with parsed stream names and hours_back
3. Use mcp__zulipchat__auto_summarize with summary_type="brief" for quick overview
4. Group by stream and topic for easy scanning
5. Highlight important conversations and key participants
6. Show message counts and activity levels

Arguments: streams (comma-separated) and hours back (default 8)
Example: general,development 4"""
        }
    }


def generate_gemini_command_file(command_name: str, command_def: Dict[str, Any]) -> str:
    """Generate Gemini CLI TOML command file content."""
    description = command_def['description']
    prompt = command_def['prompt']

    # Simple TOML generation
    toml_content = f'''description = "{description}"
prompt = """
{prompt}
"""'''

    return toml_content


def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def install_commands(target_dir: str | None = None, scope: str = 'user') -> None:
    """Install Gemini CLI command files to the specified directory."""
    if target_dir is None:
        # Default to user's home .gemini/commands directory
        home = Path.home()
        if scope == 'user':
            target_path = home / '.gemini' / 'commands' / 'zulipchat'
        else:  # project scope
            target_path = Path.cwd() / '.gemini' / 'commands' / 'zulipchat'
    else:
        target_path = Path(target_dir) / 'zulipchat'

    print(f"Installing Gemini CLI commands to: {target_path}")
    print(f"Scope: {scope}")

    try:
        ensure_directory(target_path)
        commands = get_command_definitions()

        for command_name, command_def in commands.items():
            file_path = target_path / f"{command_name}.toml"
            content = generate_gemini_command_file(command_name, command_def)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Created: {file_path}")

        print("\n🎉 Gemini CLI commands installed successfully!")
        print(f"📁 Commands available at: {target_path}")
        print("\n📖 Usage in Gemini CLI:")
        print("  /zulipchat:summarize [streams] [hours]")
        print("  /zulipchat:prepare [streams] [days]")
        print("  /zulipchat:catch_up [streams] [hours]")

    except Exception as e:
        print(f"❌ Error installing commands: {e}")
        sys.exit(1)


def list_commands() -> None:
    """List available commands and their descriptions."""
    print("Available ZulipChat Commands for Gemini CLI:")
    print("=" * 50)

    commands = get_command_definitions()
    for name, definition in commands.items():
        print(f"\n🔧 {name}")
        print(f"   Description: {definition['description']}")
        print(f"   Prompt: {definition['prompt'][:100]}...")


def main():
    """Main entry point for the Gemini CLI adapter."""
    if len(sys.argv) < 2:
        print("Gemini CLI Adapter for ZulipChat MCP")
        print("\nUsage:")
        print("  uv run agent_adapters/gemini_cli.py install [target_dir] [--scope user|project]")
        print("  uv run agent_adapters/gemini_cli.py list")
        print("\nCommands:")
        print("  install    Install command files to Gemini CLI")
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