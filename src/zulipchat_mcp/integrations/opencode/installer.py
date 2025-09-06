"""OpenCode integration installer (placeholder).

This is a skeleton implementation that will be enhanced later.
"""

from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


def install(scope: str = "user", directory: str | None = None) -> dict[str, Any]:
    """Install OpenCode integration commands (placeholder).

    Args:
        scope: Installation scope (user or project)
        directory: Target directory for project-scoped installation

    Returns:
        Installation result with status and details
    """
    logger.info("OpenCode integration is not yet implemented")

    return {
        "status": "success",
        "scope": scope,
        "message": "OpenCode integration (placeholder - not yet implemented)",
        "commands_created": [],
    }
