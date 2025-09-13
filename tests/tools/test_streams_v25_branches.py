"""Targeted branch tests for streams_v25 internals to lift coverage."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.asyncio
async def test_execute_stream_operation_unknown_returns_error() -> None:
    m = importlib.import_module("zulipchat_mcp.tools.streams_v25")

    class DummyClient:
        pass

    out = await m._execute_stream_operation(DummyClient(), {"operation": "noop"})
    assert out["status"] == "error" and "Unknown operation" in out["error"]


@pytest.mark.asyncio
async def test_execute_topic_operation_unknown_returns_error() -> None:
    m = importlib.import_module("zulipchat_mcp.tools.streams_v25")

    class DummyClient:
        pass

    out = await m._execute_topic_operation(DummyClient(), {"operation": "noop"})
    assert out["status"] == "error" and "Unknown operation" in out["error"]


def test_resolve_stream_id_int_and_error_paths() -> None:
    m = importlib.import_module("zulipchat_mcp.tools.streams_v25")

    class DummyClient:
        def get_stream_id(self, name):  # type: ignore[no-redef]
            raise RuntimeError("boom")

    # int passes through
    assert m._resolve_stream_id(DummyClient(), 42) == 42
    # name path with exception returns None
    assert m._resolve_stream_id(DummyClient(), "general") is None
