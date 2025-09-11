"""Targeted tests for internal helpers in search_v25."""

from __future__ import annotations

from datetime import datetime, timedelta

from zulipchat_mcp.tools.search_v25 import _extract_search_highlights, TimeRange


def test_extract_search_highlights_basic() -> None:
    content = "This deployment failed due to error in pipeline."
    query = "deployment error"
    highlights = _extract_search_highlights(content, query)
    assert isinstance(highlights, list)
    assert highlights  # non-empty
    assert any("deployment" in h.lower() for h in highlights)


def test_time_range_to_narrow_filters_hours() -> None:
    tr = TimeRange(hours=2)
    filters = tr.to_narrow_filters()
    assert len(filters) == 1
    f = filters[0]
    assert f.operator.value == "search"
    assert "after:" in f.operand


def test_time_range_to_narrow_filters_full_range() -> None:
    start = datetime.now() - timedelta(days=3)
    end = datetime.now() - timedelta(days=1)
    tr = TimeRange(start=start, end=end)
    filters = tr.to_narrow_filters()
    # Two filters: after and before
    assert len(filters) == 2
    ops = [f.operand for f in filters]
    assert any(op.startswith("after:") for op in ops)
    assert any(op.startswith("before:") for op in ops)

