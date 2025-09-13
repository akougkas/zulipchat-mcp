"""Unit tests for NarrowHelper utilities to improve coverage.

Covers basic builders, time filters, conversion helpers, validation,
description, and convenience wrappers.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from zulipchat_mcp.utils.narrow_helpers import (
    NarrowHelper,
    build_basic_narrow,
    simple_narrow,
)


def test_basic_builders_and_to_from_dict() -> None:
    nf = [
        NarrowHelper.stream("general"),
        NarrowHelper.topic("deploy"),
        NarrowHelper.sender("user@example.com"),
        NarrowHelper.search_text("bug"),
        NarrowHelper.has_attachment(),
        NarrowHelper.has_link(),
        NarrowHelper.has_image(),
        NarrowHelper.is_private(),
        NarrowHelper.is_starred(),
        NarrowHelper.is_mentioned(),
    ]
    assert NarrowHelper.validate_narrow_filters(nf)

    api = NarrowHelper.to_api_format(nf)
    back = NarrowHelper.from_dict_list(api)
    assert len(api) == len(back) == len(nf)

    desc = NarrowHelper.describe_narrow(nf[:3])
    assert "stream:general" in desc and "topic:deploy" in desc


def test_time_filters_and_ranges() -> None:
    now = datetime.now()
    nf_after = NarrowHelper.after_time(now)
    nf_before = NarrowHelper.before_time(now.isoformat())
    assert "after:" in nf_after.operand and "before:" in nf_before.operand

    last_h = NarrowHelper.last_hours(2)
    last_d = NarrowHelper.last_days(1)
    assert last_h.operator == last_d.operator

    rng = NarrowHelper.time_range(now - timedelta(days=1), now)
    assert len(rng) == 2


def test_build_basic_narrow_and_helpers() -> None:
    # Basic combination
    filters = build_basic_narrow(stream="dev", topic="t1", text="fix")
    assert any(f.operator.value == "stream" for f in filters)
    assert any(f.operator.value == "topic" for f in filters)
    assert any(f.operator.value == "search" for f in filters)

    # Combine narrows
    combined = NarrowHelper.combine_narrows(filters, [NarrowHelper.is_starred()])
    assert len(combined) == len(filters) + 1

    # Simple narrow returns API dicts
    simple = simple_narrow(stream="dev", text="deploy")
    assert isinstance(simple, list) and all("operator" in d for d in simple)
