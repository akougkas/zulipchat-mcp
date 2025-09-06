"""Stream management tools for ZulipChat MCP."""

from typing import Any

from ..core.client import ZulipClientWrapper
from ..config import ConfigManager
from ..utils.logging import LogContext, get_logger
from ..utils.metrics import Timer, track_tool_call, track_tool_error

logger = get_logger(__name__)


_client: ZulipClientWrapper | None = None


def _get_client() -> ZulipClientWrapper:
    global _client
    if _client is None:
        _client = ZulipClientWrapper(ConfigManager(), use_bot_identity=False)
    return _client


def get_streams() -> list[dict[str, Any]]:
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "get_streams"}):
        with LogContext(logger, tool="get_streams"):
            track_tool_call("get_streams")
            try:
                client = _get_client()
                streams = client.get_streams()
                return [
                    {
                        "stream_id": s.stream_id,
                        "name": s.name,
                        "description": s.description,
                        "is_private": s.is_private,
                    }
                    for s in streams
                ]
            except Exception as e:
                track_tool_error("get_streams", type(e).__name__)
                return [{"error": "An unexpected error occurred"}]


def rename_stream(stream_id: int, new_name: str) -> dict[str, Any]:
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "rename_stream"}):
        with LogContext(logger, tool="rename_stream", stream_id=stream_id):
            track_tool_call("rename_stream")
            try:
                client = _get_client()
                result = client.client.update_stream({"stream_id": stream_id, "name": new_name})
                if result.get("result") == "success":
                    return {"status": "success", "message": f"Stream renamed to '{new_name}'"}
                return {"status": "error", "error": result.get("msg", "Failed to rename stream")}
            except Exception as e:
                track_tool_error("rename_stream", type(e).__name__)
                return {"status": "error", "error": "An unexpected error occurred"}


def create_stream(
    name: str, 
    description: str = "", 
    subscribers: list[int] | None = None,
    invite_only: bool = False,
    is_web_public: bool = False
) -> dict[str, Any]:
    """Create a new stream/channel."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "create_stream"}):
        with LogContext(logger, tool="create_stream", stream_name=name):
            track_tool_call("create_stream")
            try:
                if not name or not name.strip():
                    return {"status": "error", "error": "Stream name cannot be empty"}
                
                client = _get_client()
                # Use direct Zulip client for stream creation
                request_data = {
                    "subscriptions": [{"name": name, "description": description}],
                    "invite_only": invite_only,
                    "is_web_public": is_web_public,
                }
                
                if subscribers:
                    request_data["principals"] = subscribers
                
                result = client.client.add_subscriptions(request_data["subscriptions"], 
                                                        principals=request_data.get("principals", []),
                                                        invite_only=invite_only)
                
                if result.get("result") == "success":
                    return {"status": "success", "message": f"Stream '{name}' created successfully"}
                return {"status": "error", "error": result.get("msg", "Failed to create stream")}
                
            except Exception as e:
                track_tool_error("create_stream", type(e).__name__)
                return {"status": "error", "error": "An unexpected error occurred"}


def archive_stream(stream_id: int) -> dict[str, Any]:
    """Archive a stream/channel."""
    with Timer("zulip_mcp_tool_duration_seconds", {"tool": "archive_stream"}):
        with LogContext(logger, tool="archive_stream", stream_id=stream_id):
            track_tool_call("archive_stream")
            try:
                if stream_id <= 0:
                    return {"status": "error", "error": "Invalid stream ID"}
                
                client = _get_client()
                # Use direct Zulip client for stream archiving
                result = client.client.delete_stream(stream_id)
                
                if result.get("result") == "success":
                    return {"status": "success", "message": "Stream archived successfully"}
                return {"status": "error", "error": result.get("msg", "Failed to archive stream")}
                
            except Exception as e:
                track_tool_error("archive_stream", type(e).__name__)
                return {"status": "error", "error": "An unexpected error occurred"}


def register_stream_tools(mcp: Any) -> None:
    mcp.tool(description="Get list of streams")(get_streams)
    mcp.tool(description="Rename a stream")(rename_stream)
    mcp.tool(description="Create a new stream")(create_stream)
    mcp.tool(description="Archive a stream")(archive_stream)
