"""Helper tests for events_v25 internals: narrow conversion and filter matching."""

from __future__ import annotations

from zulipchat_mcp.core.validation import NarrowFilter
from zulipchat_mcp.tools.events_v25 import (
    _convert_narrow_to_api_format,
    _event_matches_filters,
)


def test_convert_narrow_to_api_format_mixed() -> None:
    nf = NarrowFilter(operator="stream", operand="general")
    out = _convert_narrow_to_api_format([nf, {"operator": "topic", "operand": "t1"}])
    assert isinstance(out, list)
    assert out[0]["operator"] == "stream"
    assert out[1]["operator"] == "topic"


def test_event_matches_filters_various() -> None:
    event = {"type": "message", "id": 1, "user": {"id": 5, "role": "admin"}}

    # No filters
    assert _event_matches_filters(event, None) is True

    # Direct equality
    assert _event_matches_filters(event, {"type": "message"}) is True
    assert _event_matches_filters(event, {"type": "reaction"}) is False

    # List membership
    assert _event_matches_filters(event, {"id": [1, 2, 3]}) is True
    assert _event_matches_filters(event, {"id": [2, 3]}) is False

    # Nested dict
    assert _event_matches_filters(event, {"user": {"id": 5}}) is True
    assert _event_matches_filters(event, {"user": {"role": "member"}}) is False
