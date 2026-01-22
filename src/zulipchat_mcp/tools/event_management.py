"""Event system tools for ZulipChat MCP v0.4.0.

Core event handling: register, poll, listen, deregister.
Direct mapping to Zulip's event API endpoints.
"""

import asyncio
import time
from typing import Any

from fastmcp import FastMCP

from ..config import get_config_manager
from ..core.client import ZulipClientWrapper


async def register_events(
    event_types: list[str],
    narrow: list[dict[str, Any]] | None = None,
    queue_lifespan_secs: int = 300,
    all_public_streams: bool = False,
    include_subscribers: bool = False,
    client_gravatar: bool = False,
    slim_presence: bool = False,
    fetch_event_types: list[str] | None = None,
    client_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register for comprehensive real-time event streams from Zulip."""
    config = get_config_manager()
    client = ZulipClientWrapper(config)

    try:
        register_params = {
            "event_types": event_types,
            "queue_lifespan_secs": min(queue_lifespan_secs, 600),  # Max 600 seconds
            "all_public_streams": all_public_streams,
            "include_subscribers": include_subscribers,
            "client_gravatar": client_gravatar,
            "slim_presence": slim_presence,
        }

        if narrow:
            register_params["narrow"] = narrow
        if fetch_event_types:
            register_params["fetch_event_types"] = fetch_event_types
        if client_capabilities:
            register_params["client_capabilities"] = client_capabilities

        result = client.register(**register_params)

        if result.get("result") == "success":
            return {
                "status": "success",
                "queue_id": result.get("queue_id"),
                "last_event_id": result.get("last_event_id", -1),
                "zulip_feature_level": result.get("zulip_feature_level"),
                "realm_state": result.get("realm_state", {}),
                "queue_lifespan_secs": queue_lifespan_secs,
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to register events"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_events(
    queue_id: str,
    last_event_id: int,
    dont_block: bool = False,
    timeout: int = 10,
    apply_markdown: bool = True,
    client_gravatar: bool = False,
    user_client: str | None = None,
) -> dict[str, Any]:
    """Poll events from registered queue with long-polling support."""
    config = get_config_manager()
    client = ZulipClientWrapper(config)

    try:
        result = client.get_events(
            queue_id=queue_id,
            last_event_id=last_event_id,
            dont_block=dont_block,
            timeout=min(timeout, 60),  # Max 60 seconds
            apply_markdown=apply_markdown,
            client_gravatar=client_gravatar,
        )

        if result.get("result") == "success":
            events = result.get("events", [])
            return {
                "status": "success",
                "events": events,
                "found_newest": result.get("found_newest", False),
                "queue_id": queue_id,
                "event_count": len(events),
                "last_event_id": max(
                    [e.get("id", last_event_id) for e in events], default=last_event_id
                ),
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to get events"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def listen_events(
    event_types: list[str],
    duration: int = 300,  # Max 600 seconds
    narrow: list[dict[str, Any]] | None = None,
    filters: dict[str, Any] | None = None,
    poll_interval: int = 1,
    max_events_per_poll: int = 100,
    all_public_streams: bool = False,
    callback_url: str | None = None,
) -> dict[str, Any]:
    """Comprehensive stateless event listener with automatic queue management."""
    config = get_config_manager()
    ZulipClientWrapper(config)

    try:
        # Register queue
        register_result = await register_events(
            event_types=event_types,
            narrow=narrow,
            queue_lifespan_secs=min(duration + 60, 600),  # Buffer for processing
            all_public_streams=all_public_streams,
        )

        if register_result.get("status") != "success":
            return register_result

        queue_id = register_result["queue_id"]
        last_event_id = register_result["last_event_id"]
        collected_events = []
        start_time = time.time()

        try:
            # Event collection loop
            while time.time() - start_time < duration:
                # Get events
                events_result = await get_events(
                    queue_id=queue_id,
                    last_event_id=last_event_id,
                    timeout=min(poll_interval, 30),
                )

                if events_result.get("status") == "success":
                    events = events_result.get("events", [])

                    # Apply filters if specified
                    if filters and events:
                        filtered_events = []
                        for event in events:
                            include_event = True
                            for filter_key, filter_value in filters.items():
                                if (
                                    filter_key in event
                                    and event[filter_key] != filter_value
                                ):
                                    include_event = False
                                    break
                            if include_event:
                                filtered_events.append(event)
                        events = filtered_events

                    if events:
                        collected_events.extend(events[:max_events_per_poll])
                        last_event_id = max(
                            [e.get("id", last_event_id) for e in events],
                            default=last_event_id,
                        )

                        # Send to webhook if configured
                        if callback_url:
                            try:
                                import httpx

                                async with httpx.AsyncClient() as http_client:
                                    await http_client.post(
                                        callback_url, json={"events": events}
                                    )
                            except Exception:
                                pass  # Best effort

                # Sleep before next poll
                await asyncio.sleep(poll_interval)

        finally:
            # Cleanup: deregister queue
            try:
                await deregister_events(queue_id)
            except Exception:
                pass  # Best effort cleanup

        return {
            "status": "success",
            "collected_events": collected_events,
            "event_count": len(collected_events),
            "duration_seconds": time.time() - start_time,
            "session_summary": {
                "queue_id": queue_id,
                "event_types": event_types,
                "poll_interval": poll_interval,
                "max_events_per_poll": max_events_per_poll,
            },
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def deregister_events(queue_id: str) -> dict[str, Any]:
    """Deregister event queue."""
    config = get_config_manager()
    client = ZulipClientWrapper(config)

    try:
        result = client.deregister(queue_id)

        if result.get("result") == "success":
            return {"status": "success", "queue_id": queue_id}
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to deregister queue"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def register_event_management_tools(mcp: FastMCP) -> None:
    """Register event management tools with the MCP server."""
    mcp.tool(
        name="register_events",
        description="Register for comprehensive real-time event streams",
    )(register_events)
    mcp.tool(
        name="get_events",
        description="Poll events from registered queue with long-polling",
    )(get_events)
    mcp.tool(
        name="listen_events",
        description="Comprehensive stateless event listener with webhook integration",
    )(listen_events)
    mcp.tool(name="deregister_events", description="Deregister event queue")(
        deregister_events
    )
