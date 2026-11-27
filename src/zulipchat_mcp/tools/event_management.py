"""Event system tools for ZulipChat MCP v0.4.0.

Core event handling: register, poll, listen, deregister.
Direct mapping to Zulip's event API endpoints.
"""

import asyncio
import json
import time
from typing import Annotated, Any

from pydantic import Field

from ..config import bind_client, get_client
from ..core.errors import api_error, error_object, internal_error, tool_error

EventTypes = Annotated[
    list[str],
    Field(
        min_length=1,
        max_length=50,
        description='Zulip event types, e.g. ["message", "reaction"].',
    ),
]
EventNarrow = Annotated[
    list[dict[str, Any]] | None,
    Field(
        max_length=20,
        description='Narrow terms limiting message events, e.g. [{"operator": '
        '"channel", "operand": "general"}].',
    ),
]
QueueId = Annotated[
    str,
    Field(min_length=1, max_length=100, description="queue_id from register_events."),
]
REALM_STATE_MAX_CHARS = 100_000
# Fields of a register response that describe the queue, not the realm.
QUEUE_FIELDS = {
    "result",
    "msg",
    "queue_id",
    "last_event_id",
    "zulip_feature_level",
    "zulip_version",
    "zulip_merge_base",
    "ignored_parameters_unsupported",
}


async def register_events(
    event_types: EventTypes,
    narrow: EventNarrow = None,
    queue_lifespan_secs: Annotated[
        int,
        Field(
            ge=1,
            le=600,
            description="Seconds the queue survives without a poll (1-600).",
        ),
    ] = 300,
    all_public_streams: Annotated[
        bool, Field(description="Receive message events from every public channel.")
    ] = False,
    include_subscribers: Annotated[
        bool, Field(description="Include subscriber lists in channel state.")
    ] = False,
    client_gravatar: Annotated[
        bool, Field(description="Omit Gravatar avatar URLs.")
    ] = False,
    slim_presence: Annotated[
        bool, Field(description="Key presence by user ID instead of email.")
    ] = False,
    fetch_event_types: Annotated[
        list[str] | None,
        Field(
            max_length=50,
            description="Which initial state to fetch; defaults to event_types "
            "when include_realm_state is true.",
        ),
    ] = None,
    client_capabilities: Annotated[
        dict[str, Any] | None,
        Field(description="Zulip client_capabilities flags."),
    ] = None,
    include_realm_state: Annotated[
        bool,
        Field(
            description="Return the initial realm state (up to 100,000 characters "
            "of JSON); otherwise only its key names."
        ),
    ] = False,
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
        if fetch_event_types is not None:
            register_params["fetch_event_types"] = fetch_event_types
        elif not include_realm_state:
            # The queue needs no initial state; do not make Zulip compute it.
            register_params["fetch_event_types"] = []
        if client_capabilities:
            register_params["client_capabilities"] = client_capabilities

        result = await asyncio.to_thread(client.register, **register_params)

        if result.get("result") == "success":
            state = {k: v for k, v in result.items() if k not in QUEUE_FIELDS}
            response = {
                "status": "success",
                "queue_id": result.get("queue_id"),
                "last_event_id": result.get("last_event_id", -1),
                "zulip_feature_level": result.get("zulip_feature_level"),
                "queue_lifespan_secs": register_params["queue_lifespan_secs"],
                "realm_state_keys": sorted(state),
            }
            if include_realm_state:
                if len(json.dumps(state, default=str)) <= REALM_STATE_MAX_CHARS:
                    response["realm_state"] = state
                else:
                    response["realm_state_truncated"] = True
                    response["note"] = (
                        "Realm state exceeds 100,000 characters; pass fewer "
                        "fetch_event_types to receive it."
                    )
            return response
        else:
            return api_error(result, "Failed to register events")

    except Exception as e:
        return internal_error(e)


def _seconds(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


async def get_events(
    queue_id: QueueId,
    last_event_id: Annotated[
        int,
        Field(
            ge=-1,
            description="last_event_id from register_events or the previous "
            "get_events; acknowledges every event up to it.",
        ),
    ],
    dont_block: Annotated[
        bool, Field(description="Return at once even when no event is waiting.")
    ] = False,
    timeout: Annotated[
        int,
        Field(ge=1, le=60, description="Longest wait for an event, in seconds."),
    ] = 10,
    apply_markdown: Annotated[
        bool, Field(description="Message content as rendered HTML, not Markdown.")
    ] = True,
    client_gravatar: Annotated[
        bool, Field(description="Omit Gravatar avatar URLs.")
    ] = False,
    user_client: Annotated[
        str | None,
        Field(max_length=100, description="Unused; accepted for compatibility."),
    ] = None,
    max_events: Annotated[
        int,
        Field(
            ge=1,
            le=1000,
            description="Most events returned; the rest stay queued and "
            "more_events is true.",
        ),
    ] = 100,
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
            received = sorted(
                result.get("events", []), key=lambda e: e.get("id", last_event_id)
            )
            events = received[:max_events]
            return {
                "status": "success",
                "found_newest": result.get("found_newest", False),
                "queue_id": queue_id,
                "event_count": len(events),
                "more_events": len(received) > len(events),
                "last_event_id": max(
                    [e.get("id", last_event_id) for e in events], default=last_event_id
                ),
                "events": events,
            }
        else:
            return api_error(
                result,
                "Failed to get events",
                recovery_tool="register_events",
                hint="A BAD_EVENT_QUEUE_ID queue is gone; register a new one.",
            )

    except Exception as e:
        return internal_error(e)


async def listen_events(
    event_types: EventTypes,
    duration: Annotated[
        int, Field(gt=0, le=600, description="Seconds to listen (1-600).")
    ] = 300,
    narrow: EventNarrow = None,
    filters: Annotated[
        dict[str, Any] | None,
        Field(
            description="Keep only events whose top-level fields equal these, "
            'e.g. {"type": "message"}.'
        ),
    ] = None,
    poll_interval: Annotated[
        int, Field(gt=0, le=60, description="Seconds between polls.")
    ] = 1,
    max_events_per_poll: Annotated[
        int, Field(gt=0, le=1000, description="Most events kept from one poll.")
    ] = 100,
    all_public_streams: Annotated[
        bool, Field(description="Receive message events from every public channel.")
    ] = False,
    max_events: Annotated[
        int,
        Field(
            ge=1,
            le=1000,
            description="Stop listening once this many events are collected.",
        ),
    ] = 500,
) -> dict[str, Any]:
    """Collect events, retrying at most three consecutive failed polls.

    Unrecovered failures return error, or partial when events were collected.
    Recovered failures are reported in polling_errors even on success. Events
    go to the caller only: this server sends Zulip data to no other host.
    """
    if (
        not 0 < duration <= 600
        or poll_interval <= 0
        or max_events_per_poll <= 0
        or not 1 <= max_events <= 1000
    ):
        return tool_error(
            "Use duration in (0, 600], positive poll_interval and "
            "max_events_per_poll, and max_events in 1..1000"
        )
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
            collected_events: list[dict[str, Any]] = []
            start_time = time.monotonic()
            polling_errors = []
            consecutive_failures = 0
            last_failure: dict[str, Any] | None = None
            cleanup_error = None
            reached_cap = False

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
                            max_events=max_events_per_poll,
                        )
                    except Exception as exc:
                        events_result = internal_error(exc)

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
                            room = max_events - len(collected_events)
                            collected_events.extend(events[:room])
                        if len(collected_events) >= max_events:
                            reached_cap = True
                            break
                    else:
                        failure = events_result.get("error")
                        last_failure = (
                            failure
                            if isinstance(failure, dict)
                            else error_object(
                                str(failure or "Failed to get events"), "ZULIP_ERROR"
                            )
                        )
                        polling_errors.append(last_failure)
                        consecutive_failures += 1
                        # A lost queue or invalid credentials cannot recover by polling
                        # the same queue. Unknown/backend/network errors get bounded
                        # retries, without acknowledging any unreceived events.
                        if (
                            last_failure.get("code")
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
                    cleanup_error = internal_error(exc)

            response = {
                "status": (
                    ("partial" if collected_events else "error")
                    if last_failure
                    else "success"
                ),
                "event_count": len(collected_events),
                "reached_max_events": reached_cap,
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
                response["error"] = last_failure
            if cleanup_error:
                response["cleanup_error"] = cleanup_error
            response["collected_events"] = collected_events
            return response

        except Exception as e:
            return internal_error(e)


async def deregister_events(queue_id: QueueId) -> dict[str, Any]:
    """Deregister event queue."""
    client = get_client()

    try:
        result = await asyncio.to_thread(client.deregister, queue_id)

        if result.get("result") == "success":
            return {"status": "success", "queue_id": queue_id}
        else:
            return api_error(result, "Failed to deregister queue")

    except Exception as e:
        return internal_error(e)
