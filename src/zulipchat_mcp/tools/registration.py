"""Shared MCP tool registration helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.tasks import TaskConfig
from mcp.types import ToolAnnotations

from ..core.tool_contract import READ_ONLY_TOOLS


def optional_background_task(poll_seconds: int = 5) -> TaskConfig:
    """Return explicit optional MCP background-task support metadata."""
    return TaskConfig(mode="optional", poll_interval=timedelta(seconds=poll_seconds))


def tool_annotations(
    name: str,
    title: str,
    *,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = True,
) -> ToolAnnotations:
    """Build MCP tool annotations for a tool.

    readOnlyHint comes from READ_ONLY_TOOLS, the same set that backs the
    read-only tool profile, so the hints and the enforced policy cannot differ.
    A read-only tool is never destructive and repeating it has no effect.
    """
    read_only = name in READ_ONLY_TOOLS
    if read_only and destructive:
        raise ValueError(
            f"{name} is in the read-only profile and cannot be destructive"
        )
    return ToolAnnotations(
        title=title,
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent or read_only,
        open_world_hint=open_world,
    )


def register_tool(
    mcp: FastMCP[Any],
    fn: Callable[..., Any],
    *,
    name: str,
    description: str,
    title: str,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = True,
    task: TaskConfig | None = None,
) -> None:
    """Register a tool with explicit annotations and task semantics.

    destructive is True only when the tool can delete or irreversibly overwrite
    user-visible data. idempotent is True only when repeating the same call has
    no further effect. open_world is False only for tools that never reach Zulip.

    FastMCP server-wide task defaults are intentionally disabled in server.py.
    Long-running tools opt in here so sync and fast tools are not accidentally
    advertised as background-task capable.
    """
    kwargs: dict[str, Any] = {
        "name": name,
        "description": description,
        "title": title,
        "annotations": tool_annotations(
            name,
            title,
            destructive=destructive,
            idempotent=idempotent,
            open_world=open_world,
        ),
    }
    if task is not None:
        kwargs["task"] = task
    mcp.tool(**kwargs)(fn)
