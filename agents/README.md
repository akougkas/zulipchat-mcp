# AI Agent Integrations

This directory contains integrations for various AI agents to use ZulipChat MCP slash commands.

## Available Agents

### Claude Code (`claude_code_commands.py`)
Generates slash command files for Claude Code in `~/.claude/commands/`

**Usage:**
```bash
uv run agents/claude_code_commands.py
```

**Created commands:**
- `/zulipchat:summarize` - Daily summary with message stats
- `/zulipchat:prepare` - Morning briefing with highlights
- `/zulipchat:catch_up` - Quick catch-up for missed messages

## Universal Implementation

All agents can use the universal `slash_commands.py` script:

```bash
# Examples
uv run slash_commands.py summarize
uv run slash_commands.py prepare general,development 5
uv run slash_commands.py catch_up general 4
```

## Adding New Agent Support

To add support for a new AI agent:

1. Create a new file: `agents/{agent_name}_commands.py`
2. Implement the agent's specific slash command format
3. Reference the universal `slash_commands.py` functions
4. Update this README with usage instructions

### Template Structure

```python
#!/usr/bin/env python3
"""
{Agent Name} Slash Commands for ZulipChat MCP
"""

def create_{agent_name}_commands():
    """Create slash command files for {Agent Name}"""
    # Agent-specific implementation
    pass

if __name__ == "__main__":
    create_{agent_name}_commands()
```

## Community Contributions

We welcome contributions for additional AI agent integrations! Popular agents to consider:

- **Cursor IDE**: Custom commands or terminal integration
- **Cascade**: Workflow script integration  
- **Aider**: External tool configuration
- **Continue**: VS Code extension integration
- **Other agents**: Any agent that can execute Python scripts

## Requirements

All agent integrations should:
- Use the universal `slash_commands.py` for core functionality
- Follow the agent's specific command format
- Include clear usage instructions
- Handle errors gracefully
- Provide examples in documentation