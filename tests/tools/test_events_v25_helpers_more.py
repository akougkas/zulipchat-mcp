"""Cover get_active_queues helper in events_v25."""

from __future__ import annotations

from zulipchat_mcp.tools.events_v25 import get_active_queues, _active_queues


def test_get_active_queues_returns_dict() -> None:
    # Ensure at least one fake queue for coverage
    _active_queues.setdefault("q-test", {"created_at": 0.0, "lifespan": 10, "client": None, "event_types": ["message"]})
    info = get_active_queues()
    assert isinstance(info, dict)
    assert "q-test" in info

