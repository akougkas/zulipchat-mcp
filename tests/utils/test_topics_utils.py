"""Tests for utils.topics helpers."""

from __future__ import annotations

from zulipchat_mcp.utils.topics import project_from_path, topic_input, topic_chat, topic_status


def test_project_from_path_variants() -> None:
    assert project_from_path(None) == "Project"
    assert project_from_path("") == "Project"
    assert project_from_path("/a/b/c") == "c"


def test_topic_builders() -> None:
    assert topic_input("Proj", "123").startswith("Agents/Input/Proj/123")
    assert topic_chat("Proj", "Bot", "sess").startswith("Agents/Chat/Proj/Bot/sess")
    assert topic_status("Bot") == "Agents/Status/Bot"

