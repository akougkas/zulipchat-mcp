"""Topic naming helpers for consistent Agent-Channel threading.

Provides a stable, readable scheme for all agent communications.
"""

from __future__ import annotations

from pathlib import Path


def project_from_path(path: str | None) -> str:
    if not path:
        return "Project"
    try:
        return Path(path).name or "Project"
    except Exception:
        return "Project"


def topic_input(project: str, request_id: str) -> str:
    """Topic for input requests: Agents/Input/<project>/<id>"""
    return f"Agents/Input/{project}/{request_id}"


def topic_chat(project: str, agent_type: str, session_id: str) -> str:
    """Topic for ongoing chat: Agents/Chat/<project>/<agent>/<session>"""
    return f"Agents/Chat/{project}/{agent_type}/{session_id}"


def topic_status(agent_type: str) -> str:
    """Topic for status updates: Agents/Status/<agent>"""
    return f"Agents/Status/{agent_type}"

