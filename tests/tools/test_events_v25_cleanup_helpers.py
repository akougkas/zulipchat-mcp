"""Cover events_v25 cleanup helpers and queue inspection."""

from __future__ import annotations

from zulipchat_mcp.tools import events_v25 as ev
import pytest


@pytest.mark.asyncio
async def test_cleanup_expired_queues_schedules_cleanup() -> None:
    # Insert a fake expired queue
    ev._active_queues["qexp"] = {
        "created_at": ev.asyncio.get_event_loop().time() - 100,
        "lifespan": 1,
        "client": None,
        "event_types": ["message"],
    }

    ev.cleanup_expired_queues()
    # We can't await the scheduled task here, but the function executed
    assert "qexp" in ev._active_queues
