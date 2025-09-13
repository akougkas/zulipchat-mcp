"""Integration registry and CLI for ZulipChat MCP agent installers.

This module provides a neutral CLI entrypoint that routes to specific agent installers
without leaking brand specifics into the core system.
"""

import argparse
import sys

from ..utils.logging import get_logger

logger = get_logger(__name__)

# Registry of supported agents and their installers
AGENT_REGISTRY = {
    "claude_code": {
        "installer_module": "zulipchat_mcp.integrations.claude_code.installer",
        "capabilities_module": "zulipchat_mcp.integrations.claude_code.capabilities",
        "description": "Claude Code integration with status line and commands",
    },
    "gemini_cli": {
        "installer_module": "zulipchat_mcp.integrations.gemini_cli.installer",
        "capabilities_module": "zulipchat_mcp.integrations.gemini_cli.capabilities",
        "description": "Gemini CLI integration (placeholder)",
    },
    "opencode": {
        "installer_module": "zulipchat_mcp.integrations.opencode.installer",
        "capabilities_module": "zulipchat_mcp.integrations.opencode.capabilities",
        "description": "OpenCode integration (placeholder)",
    },
}


def install_agent(agent: str, scope: str = "user", directory: str | None = None) -> int:
    """Install agent integration.

    Args:
        agent: Agent type to install
        scope: Installation scope (user or project)
        directory: Target directory for installation

    Returns:
        Exit code (0 for success, 1 for invalid args, 2 for installation error)
    """
    if agent not in AGENT_REGISTRY:
        logger.error(f"Unknown agent type: {agent}")
        logger.info(f"Supported agents: {', '.join(AGENT_REGISTRY.keys())}")
        return 1

    if scope not in ["user", "project"]:
        logger.error(f"Invalid scope: {scope}. Must be 'user' or 'project'")
        return 1

    try:
        # Dynamic import of installer module
        installer_module = AGENT_REGISTRY[agent]["installer_module"]
        module = __import__(installer_module, fromlist=["install"])

        if not hasattr(module, "install"):
            logger.error(
                f"Installer module {installer_module} missing install() function"
            )
            return 2

        # Call the installer
        result = module.install(scope=scope, directory=directory)

        if result.get("status") == "success":
            logger.info(f"Successfully installed {agent} integration")
            return 0
        else:
            logger.error(f"Installation failed: {result.get('error', 'Unknown error')}")
            return 2

    except ImportError as e:
        logger.error(f"Failed to import installer for {agent}: {e}")
        return 2
    except Exception as e:
        logger.error(f"Installation error: {e}")
        return 2


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Install ZulipChat MCP agent integrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  zulipchat-mcp-integrate claude_code --scope user
  zulipchat-mcp-integrate claude_code --scope project --dir /path/to/project
  zulipchat-mcp-integrate gemini_cli --scope user

Supported agents:
"""
        + "\n".join(
            f"  {agent}: {info['description']}"
            for agent, info in AGENT_REGISTRY.items()
        ),
    )

    parser.add_argument(
        "agent", choices=list(AGENT_REGISTRY.keys()), help="Agent type to install"
    )
    parser.add_argument(
        "--scope",
        choices=["user", "project"],
        default="user",
        help="Installation scope (default: user)",
    )
    parser.add_argument(
        "--dir",
        dest="directory",
        help="Target directory for project-scoped installation",
    )

    args = parser.parse_args()

    exit_code = install_agent(args.agent, args.scope, args.directory)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
