"""Stream management tools for ZulipChat MCP.

Optimized for latency with direct dict manipulation.
"""

from typing import Any

from ..config import ConfigManager
from ..core.client import ZulipClientWrapper
from ..core.security import validate_stream_name
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)

_client: ZulipClientWrapper | None = None


def _get_client() -> ZulipClientWrapper:
    """Get or create client instance."""
    global _client
    if _client is None:
        _client = ZulipClientWrapper(ConfigManager(), use_bot_identity=False)
    return _client


def get_streams(include_subscribed: bool = True) -> list[dict[str, Any]]:
    """Get list of streams - optimized for latency."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_streams"}):
        with LogContext(logger, tool="get_streams"):
            track_tool_call("get_streams")
            try:
                client = _get_client()
                response = client.get_streams(include_subscribed=include_subscribed)

                # Quick validation
                if response.get("result") != "success":
                    logger.error(f"Failed to get streams: {response.get('msg')}")
                    return []

                # Return simplified stream info - direct from API
                return [
                    {
                        "stream_id": stream["stream_id"],
                        "name": stream["name"],
                        "description": stream.get("description", ""),
                        "is_private": stream.get("invite_only", False),
                    }
                    for stream in response.get("streams", [])
                ]

            except KeyError as e:
                track_tool_error("get_streams", "KeyError")
                logger.error(f"get_streams KeyError: {e}")
                return []
            except Exception as e:
                track_tool_error("get_streams", type(e).__name__)
                logger.error(f"get_streams error: {type(e).__name__}: {str(e)}")
                return []


def rename_stream(stream_id: int, new_name: str) -> dict[str, Any]:
    """Rename a stream."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "rename_stream"}):
        with LogContext(logger, tool="rename_stream", stream_id=stream_id):
            track_tool_call("rename_stream")
            try:
                # Input validation
                if stream_id <= 0:
                    return {"status": "error", "error": "Invalid stream ID"}
                if not validate_stream_name(new_name):
                    return {
                        "status": "error",
                        "error": f"Invalid stream name: {new_name}",
                    }

                client = _get_client()
                request = {"stream_id": stream_id, "new_name": new_name}
                result = client.client.update_stream(request)

                if result.get("result") == "success":
                    return {"status": "success", "message": "Stream renamed"}
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to rename stream"),
                }

            except KeyError as e:
                track_tool_error("rename_stream", "KeyError")
                return {"status": "error", "error": f"Missing field: {e}"}
            except Exception as e:
                track_tool_error("rename_stream", type(e).__name__)
                return {
                    "status": "error",
                    "error": f"Failed to rename stream: {str(e)}",
                }


def create_stream(
    name: str,
    description: str = "",
    is_private: bool = False,
) -> dict[str, Any]:
    """Create a new stream."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "create_stream"}):
        with LogContext(logger, tool="create_stream", stream_name=name):
            track_tool_call("create_stream")
            try:
                # Input validation
                if not validate_stream_name(name):
                    return {
                        "status": "error",
                        "error": f"Invalid stream name: {name}",
                    }

                client = _get_client()
                request = {
                    "subscriptions": [
                        {
                            "name": name,
                            "description": description,
                        }
                    ],
                    "invite_only": is_private,
                }

                result = client.client.add_subscriptions(
                    request["subscriptions"], invite_only=is_private
                )

                if result.get("result") == "success":
                    return {"status": "success", "message": f"Stream '{name}' created"}
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to create stream"),
                }

            except KeyError as e:
                track_tool_error("create_stream", "KeyError")
                return {"status": "error", "error": f"Missing field: {e}"}
            except Exception as e:
                track_tool_error("create_stream", type(e).__name__)
                return {
                    "status": "error",
                    "error": f"Failed to create stream: {str(e)}",
                }


def archive_stream(stream_id: int) -> dict[str, Any]:
    """Archive a stream."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "archive_stream"}):
        with LogContext(logger, tool="archive_stream", stream_id=stream_id):
            track_tool_call("archive_stream")
            try:
                # Input validation
                if stream_id <= 0:
                    return {"status": "error", "error": "Invalid stream ID"}

                client = _get_client()
                result = client.client.delete_stream(stream_id)

                if result.get("result") == "success":
                    return {"status": "success", "message": "Stream archived"}
                return {
                    "status": "error",
                    "error": result.get("msg", "Failed to archive stream"),
                }

            except KeyError as e:
                track_tool_error("archive_stream", "KeyError")
                return {"status": "error", "error": f"Missing field: {e}"}
            except Exception as e:
                track_tool_error("archive_stream", type(e).__name__)
                return {
                    "status": "error",
                    "error": f"Failed to archive stream: {str(e)}",
                }


def register_stream_tools(mcp: Any) -> None:
    mcp.tool(description="Get list of streams")(get_streams)
    mcp.tool(description="Rename a stream")(rename_stream)
    mcp.tool(description="Create a new stream")(create_stream)
    mcp.tool(description="Archive a stream")(archive_stream)
