"""Unit tests for NarrowHelper utilities to improve coverage.

Covers basic builders, time filters, conversion helpers, validation,
description, and convenience wrappers.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (
            513,
            [
                {"operator": "channel", "operand": "general", "negated": True},
                ["dm", "a@x"],
                {"operator": "dm-including", "operand": 5},
                {"operator": "is", "operand": "dm"},
                {"operator": "channels", "operand": "public"},
            ],
        ),
        (
            200,
            [
                {"operator": "stream", "operand": "general", "negated": True},
                ["dm", "a@x"],
                {"operator": "dm-including", "operand": 5},
                {"operator": "is", "operand": "dm"},
                {"operator": "streams", "operand": "public"},
            ],
        ),
        (
            100,
            [
                {"operator": "stream", "operand": "general", "negated": True},
                ["pm-with", "a@x"],
                {"operator": "group-pm-with", "operand": 5},
                {"operator": "is", "operand": "private"},
                {"operator": "streams", "operand": "public"},
            ],
        ),
    ],
)
def test_wire_narrow_tracks_feature_level(level, expected):
    from zulipchat_mcp.utils.narrow_helpers import wire_narrow

    narrow = [
        {"operator": "stream", "operand": "general", "negated": True},
        ["pm-with", "a@x"],
        {"operator": "group-pm-with", "operand": 5},
        {"operator": "is", "operand": "private"},
        {"operator": "channels", "operand": "public"},
    ]
    assert wire_narrow(narrow, lambda needed: level >= needed) == expected
