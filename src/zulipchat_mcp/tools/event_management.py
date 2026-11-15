"""Event system tools for ZulipChat MCP v0.4.0.

Core event handling: register, poll, listen, deregister.
Direct mapping to Zulip's event API endpoints.
"""

import asyncio
import time
from typing import Any

from ..config import bind_client, get_client
from ..core.api_errors import api_error


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
    client = get_client()

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

        result = await asyncio.to_thread(client.register, **register_params)

        if result.get("result") == "success":
            return {
                "status": "success",
                "queue_id": result.get("queue_id"),
                "last_event_id": result.get("last_event_id", -1),
                "zulip_feature_level": result.get("zulip_feature_level"),
                "realm_state": result.get("realm_state", {}),
                "queue_lifespan_secs": register_params["queue_lifespan_secs"],
            }
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to register events"),
                "code": result.get("code"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def _seconds(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


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
    client = get_client()

    try:
        result = await asyncio.to_thread(
            client.get_events,
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
                **api_error(result, "Failed to get events"),
                "code": result.get("code"),
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
) -> dict[str, Any]:
    """Collect events, retrying at most three consecutive failed polls.

    Unrecovered failures return error, or partial when events were collected.
    Recovered failures are reported in polling_errors even on success. Events
    go to the caller only: this server sends Zulip data to no other host.
    """
    if not 0 < duration <= 600 or poll_interval <= 0 or max_events_per_poll <= 0:
        return {
            "status": "error",
            "error": "Use duration in (0, 600], positive poll_interval and max_events_per_poll",
        }
    with bind_client(get_client()):
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
            start_time = time.monotonic()
            polling_errors = []
            consecutive_failures = 0
            last_failure = None
            cleanup_error = None

            try:
                # Event collection loop
                while (elapsed := time.monotonic() - start_time) < duration:
                    # Get events
                    try:
                        events_result = await get_events(
                            queue_id=queue_id,
                            last_event_id=last_event_id,
                            timeout=min(poll_interval, 30),
                            dont_block=True,
                        )
                    except Exception as exc:
                        events_result = {"status": "error", "error": str(exc)}

                    if events_result.get("status") == "success":
                        consecutive_failures = 0
                        last_failure = None
                        events = events_result.get("events", [])[:max_events_per_poll]
                        # Acknowledge processed events, including filtered ones;
                        # events beyond the page limit remain queued for the next poll.
                        last_event_id = max(
                            (e.get("id", last_event_id) for e in events),
                            default=last_event_id,
                        )

                        # Apply filters if specified
                        if filters and events:
                            filtered_events = []
                            for event in events:
                                include_event = True
                                for filter_key, filter_value in filters.items():
                                    if event.get(filter_key) != filter_value:
                                        include_event = False
                                        break
                                if include_event:
                                    filtered_events.append(event)
                            events = filtered_events

                        if events:
                            collected_events.extend(events[:max_events_per_poll])
                    else:
                        last_failure = {
                            "error": events_result.get("error", "Failed to get events"),
                            "code": events_result.get("code"),
                        }
                        retry_after = events_result.get("retry_after_seconds")
                        if retry_after is not None:
                            last_failure["retry_after_seconds"] = retry_after
                        polling_errors.append(last_failure)
                        consecutive_failures += 1
                        # A lost queue or invalid credentials cannot recover by polling
                        # the same queue. Unknown/backend/network errors get bounded
                        # retries, without acknowledging any unreceived events.
                        if (
                            last_failure["code"]
                            in {
                                "BAD_EVENT_QUEUE_ID",
                                "BAD_EVENT_QUEUE_OWNER",
                                "BAD_REQUEST",
                                "UNAUTHORIZED",
                                "FORBIDDEN",
                                "INVALID_API_KEY",
                            }
                            or consecutive_failures >= 3
                        ):
                            break

                    # Sleep before next poll, honoring a server retry-after.
                    delay = poll_interval * 2 ** min(consecutive_failures, 2)
                    if last_failure:
                        delay = max(
                            delay, _seconds(last_failure.get("retry_after_seconds"))
                        )
                    await asyncio.sleep(min(delay, duration - elapsed))

            finally:
                # Cleanup: deregister queue
                try:
                    cleanup_result = await deregister_events(queue_id)
                    if (
                        isinstance(cleanup_result, dict)
                        and cleanup_result.get("status") != "success"
                    ):
                        cleanup_error = cleanup_result
                except Exception as exc:
                    cleanup_error = {"status": "error", "error": str(exc)}

            response = {
                "status": (
                    ("partial" if collected_events else "error")
                    if last_failure
                    else "success"
                ),
                "collected_events": collected_events,
                "event_count": len(collected_events),
                "duration_seconds": time.monotonic() - start_time,
                "polling_errors": polling_errors,
                "poll_failure_count": len(polling_errors),
                "session_summary": {
                    "queue_id": queue_id,
                    "event_types": event_types,
                    "poll_interval": poll_interval,
                    "max_events_per_poll": max_events_per_poll,
                },
            }
            if last_failure:
                response.update(last_failure)
            if cleanup_error:
                response["cleanup_error"] = cleanup_error
            return response

        except Exception as e:
            return {"status": "error", "error": str(e)}


async def deregister_events(queue_id: str) -> dict[str, Any]:
    """Deregister event queue."""
    client = get_client()

    try:
        result = await asyncio.to_thread(client.deregister, queue_id)

        if result.get("result") == "success":
            return {"status": "success", "queue_id": queue_id}
        else:
            return {
                "status": "error",
                "error": result.get("msg", "Failed to deregister queue"),
                "code": result.get("code"),
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}
