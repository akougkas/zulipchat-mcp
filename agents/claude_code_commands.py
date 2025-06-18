#!/usr/bin/env python3
"""
Claude Code Slash Commands for ZulipChat MCP

This script provides Claude Code slash command implementations.
Place the generated .md files in your ~/.claude/commands/ directory.
"""

import os


def create_claude_code_commands():
    """Create Claude Code slash command files in ~/.claude/commands/"""
    
    commands_dir = os.path.expanduser("~/.claude/commands")
    os.makedirs(commands_dir, exist_ok=True)
    
    # Summarize command
    summarize_content = """# ZulipChat Daily Summary

Generate an end-of-day summary with message statistics and key conversations from your Zulip workspace.

## Usage
- `/zulipchat:summarize` - Get today's activity summary (last 24 hours)
- `/zulipchat:summarize [streams] [hours]` - Custom streams and time range

## Examples
- `/zulipchat:summarize` - Summary of all streams from last 24 hours
- `/zulipchat:summarize general,development 48` - Summary of specific streams from last 48 hours

---

Please run the ZulipChat MCP slash command for summarize:

```bash
cd /path/to/zulipchat-mcp
uv run slash_commands.py summarize $ARGUMENTS
```

This will generate a comprehensive daily summary with:
- Total message count across streams
- Activity breakdown by stream
- Most active topics in each stream  
- Top contributors by message count
- Time range analysis

Format the output in a clear, readable summary that helps understand team activity patterns."""

    # Prepare command
    prepare_content = """# ZulipChat Morning Briefing

Generate a morning briefing with yesterday's highlights and weekly overview to start your day informed.

## Usage
- `/zulipchat:prepare` - Get morning briefing with yesterday's highlights and 7-day overview
- `/zulipchat:prepare [streams] [days]` - Custom streams and weekly lookback period

## Examples
- `/zulipchat:prepare` - Full morning briefing with 7-day overview
- `/zulipchat:prepare general,team-updates 5` - Briefing for specific streams with 5-day overview

---

Please run the ZulipChat MCP slash command for prepare:

```bash
cd /path/to/zulipchat-mcp
uv run slash_commands.py prepare $ARGUMENTS
```

This will generate a comprehensive morning briefing with:
- Yesterday's message statistics and activity
- Most active streams and topics from yesterday
- Weekly overview with trends and patterns
- Top contributors over the week
- Actionable insights for the day"""

    # Catch-up command
    catch_up_content = """# ZulipChat Catch-Up Summary

Generate a quick catch-up summary for messages you may have missed while away.

## Usage
- `/zulipchat:catch_up` - Get summary of missed messages (last 8 hours)
- `/zulipchat:catch_up [streams] [hours]` - Custom streams and time range

## Examples
- `/zulipchat:catch_up` - Summary of all active streams from last 8 hours
- `/zulipchat:catch_up general,development 4` - Summary of specific streams from last 4 hours

---

Please run the ZulipChat MCP slash command for catch_up:

```bash
cd /path/to/zulipchat-mcp
uv run slash_commands.py catch_up $ARGUMENTS
```

This will generate a focused catch-up summary with:
- Recent activity overview across streams
- Message counts per stream and topic
- Key conversation highlights organized by topic
- Important discussions you may have missed
- Scannable format for quick consumption"""

    # Write the files
    files = {
        "zulipchat:summarize.md": summarize_content,
        "zulipchat:prepare.md": prepare_content,
        "zulipchat:catch_up.md": catch_up_content
    }
    
    for filename, content in files.items():
        filepath = os.path.join(commands_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Created: {filepath}")
    
    print(f"\n🎉 Claude Code slash commands created in {commands_dir}")
    print("\nAvailable commands:")
    print("- /zulipchat:summarize")
    print("- /zulipchat:prepare") 
    print("- /zulipchat:catch_up")
    print("\nNote: Make sure to update the paths in the .md files to match your")
    print("actual zulipchat-mcp installation directory!")


if __name__ == "__main__":
    create_claude_code_commands()