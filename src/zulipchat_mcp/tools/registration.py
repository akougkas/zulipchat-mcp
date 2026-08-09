"""Shared MCP tool registration helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.tasks import TaskConfig


def optional_background_task(poll_seconds: int = 5) -> TaskConfig:
    """Return explicit optional MCP background-task support metadata."""
    return TaskConfig(mode="optional", poll_interval=timedelta(seconds=poll_seconds))


def register_tool(
    mcp: FastMCP[Any],
    fn: Callable[..., Any],
    *,
    name: str,
    description: str,
    task: TaskConfig | None = None,
) -> None:
    """Register a tool with explicit task semantics.

    FastMCP server-wide task defaults are intentionally disabled in server.py.
    Long-running tools opt in here so sync and fast tools are not accidentally
    advertised as background-task capable.
    """
    kwargs: dict[str, Any] = {"name": name, "description": description}
    if task is not None:
        kwargs["task"] = task
    mcp.tool(**kwargs)(fn)
