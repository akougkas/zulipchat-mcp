"""Claude Code integration installer.

This module generates client-native command files that implement workflows
by calling ZulipChat MCP tools in pre-defined patterns.
"""

import json
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


def install(scope: str = "user", directory: str | None = None) -> dict[str, Any]:
    """Install Claude Code integration commands.

    Args:
        scope: Installation scope (user or project)
        directory: Target directory for project-scoped installation

    Returns:
        Installation result with status and details
    """
    try:
        if scope == "user":
            # User-scope installation (global commands)
            install_path = Path.home() / ".claude" / "commands"
        else:
            # Project-scope installation
            if directory:
                install_path = Path(directory) / ".claude" / "commands"
            else:
                install_path = Path.cwd() / ".claude" / "commands"

        install_path.mkdir(parents=True, exist_ok=True)

        # Generate command files for common workflows
        commands_created = []

        # Daily summary command
        daily_summary_cmd = {
            "name": "zulip-daily-summary",
            "description": "Get daily summary from Zulip streams",
            "type": "mcp_tool_chain",
            "tools": [
                {
                    "tool": "search_messages",
                    "server": "zulipchat-mcp",
                    "parameters": {
                        "query": "has:link OR has:image OR sender:me",
                        "limit": 20,
                    },
                },
                {
                    "tool": "get_daily_summary",
                    "server": "zulipchat-mcp",
                    "parameters": {"hours_back": 24},
                },
            ],
        }

        daily_summary_path = install_path / "zulip-daily-summary.json"
        with open(daily_summary_path, "w") as f:
            json.dump(daily_summary_cmd, f, indent=2)
        commands_created.append(str(daily_summary_path))

        # Morning briefing command
        morning_briefing_cmd = {
            "name": "zulip-morning-briefing",
            "description": "Get morning briefing from important Zulip streams",
            "type": "mcp_tool_chain",
            "tools": [
                {
                    "tool": "get_daily_summary",
                    "server": "zulipchat-mcp",
                    "parameters": {
                        "streams": ["general", "important", "announcements"],
                        "hours_back": 16,
                    },
                }
            ],
        }

        morning_briefing_path = install_path / "zulip-morning-briefing.json"
        with open(morning_briefing_path, "w") as f:
            json.dump(morning_briefing_cmd, f, indent=2)
        commands_created.append(str(morning_briefing_path))

        # Catch up command
        catch_up_cmd = {
            "name": "zulip-catch-up",
            "description": "Quick catch-up on recent Zulip activity",
            "type": "mcp_tool_chain",
            "tools": [
                {
                    "tool": "get_daily_summary",
                    "server": "zulipchat-mcp",
                    "parameters": {"hours_back": 4},
                }
            ],
        }

        catch_up_path = install_path / "zulip-catch-up.json"
        with open(catch_up_path, "w") as f:
            json.dump(catch_up_cmd, f, indent=2)
        commands_created.append(str(catch_up_path))

        return {
            "status": "success",
            "scope": scope,
            "install_path": str(install_path),
            "commands_created": commands_created,
            "message": f"Claude Code commands installed to {install_path}",
        }

    except Exception as e:
        logger.error(f"Installation failed: {e}")
        return {"status": "error", "error": str(e)}
