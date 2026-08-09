"""Temporary workaround for an mcp-types 2.0.0 omission.

Upstream issue: https://github.com/modelcontextprotocol/python-sdk/issues/3273

mcp-types 2.0.0 vendors the 2026-07-28 schema without PingRequest/EmptyResult
entries, so ping has no ("ping", "2026-07-28") row in any surface map:
CLIENT_REQUESTS (server-side request validation/parsing), SERVER_REQUESTS
(client-side ping initiation), SERVER_RESULTS and CLIENT_RESULTS (result
serialization). The SDK's ServerRunner surface-validates against these maps
and converts the resulting KeyError into -32601 "Method not found", killing
ping keepalives from any client that negotiated the modern era (e.g.
fastmcp.Client with mode="auto").

The fix below registers the version-agnostic top-level models for the missing
(method, version) rows, rebinding both the module attributes and the
keyword-only `surface` defaults that captured the original mappings at
definition time. Validation semantics for every other method are unchanged.
Remove this module once an mcp/mcp-types release closes #3273 and our
dependency floor includes it.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)

_METHOD = "ping"
_VERSION = "2026-07-28"


def _patch_surface(module: ModuleType, attr: str, model: type) -> None:
    """Add ("ping", "2026-07-28") to one surface map and its bound defaults."""
    original = getattr(module, attr)
    key = (_METHOD, _VERSION)
    if key in original:
        return  # upstream fix already present (or patch ran twice)

    patched: dict[tuple[str, str], Any] = {**original, key: model}
    setattr(module, attr, type(original)(patched))

    # Validation/serialization functions captured the mapping as a
    # keyword-only `surface` default at definition time; rebind those too.
    for obj in vars(module).values():
        kwdefaults = getattr(obj, "__kwdefaults__", None)
        if kwdefaults and kwdefaults.get("surface") is original:
            kwdefaults["surface"] = patched


def apply() -> None:
    """Patch the mcp-types surface maps so ping works on 2026-07-28."""
    try:
        import mcp_types.methods as methods
        from mcp_types import EmptyResult, PingRequest
    except ImportError:  # pragma: no cover - mcp-types always ships with mcp 2.x
        logger.debug("mcp_types not importable; ping patch skipped")
        return

    _patch_surface(methods, "CLIENT_REQUESTS", PingRequest)
    _patch_surface(methods, "SERVER_REQUESTS", PingRequest)
    _patch_surface(methods, "SERVER_RESULTS", EmptyResult)
    _patch_surface(methods, "CLIENT_RESULTS", EmptyResult)
    logger.debug("Applied ping surface patch for protocol %s", _VERSION)
