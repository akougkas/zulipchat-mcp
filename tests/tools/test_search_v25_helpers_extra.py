"""Extra helper tests for search_v25 highlights extraction."""

from __future__ import annotations

from zulipchat_mcp.tools.search_v25 import _extract_search_highlights


def test_extract_search_highlights_basic() -> None:
    text = "This is a simple message mentioning Python deployment guide."
    highlights = _extract_search_highlights(text, "python guide")
    assert isinstance(highlights, list)
    assert any("python" in h.lower() for h in highlights)


def test_extract_search_highlights_empty_query() -> None:
    assert _extract_search_highlights("content", " ") == []

