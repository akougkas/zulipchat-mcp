"""Tests for core/validation/simple_validators.py."""

import pytest

from src.zulipchat_mcp.core.validation.simple_validators import (
    NarrowHelper,
    SimpleValidator,
    ValidationMode,
    get_validator,
    validate_tool_params,
)


class TestSimpleValidator:
    """Tests for SimpleValidator."""

    @pytest.fixture
    def validator(self):
        return SimpleValidator()

    def test_validate_params_basic_mode(self, validator):
        """Test validation in basic mode filters excess params."""
        tool = "messaging.message"
        params = {
            "operation": "send",
            "type": "stream",
            "to": "general",
            "content": "hello",
            "extra_param": "should be filtered",
        }

        result = validator.validate_params(tool, params, ValidationMode.BASIC)

        assert "extra_param" not in result
        assert result["content"] == "hello"

    def test_validate_params_advanced_mode(self, validator):
        """Test validation in advanced mode keeps all params."""
        tool = "messaging.message"
        params = {
            "operation": "send",
            "type": "stream",
            "to": "general",
            "content": "hello",
            "extra_param": "allowed",
        }

        result = validator.validate_params(tool, params, ValidationMode.ADVANCED)

        assert "extra_param" in result
        assert result["extra_param"] == "allowed"

    def test_validate_params_expert_mode(self, validator):
        """Test validation in expert mode."""
        tool = "messaging.message"
        params = {
            "operation": "send",
            "type": "stream",
            "to": "general",
            "content": "hello",
            "weird_param": "allowed",
        }

        result = validator.validate_params(tool, params, ValidationMode.EXPERT)

        assert "weird_param" in result

    def test_missing_required_params(self, validator):
        """Test validation raises error for missing required params."""
        tool = "messaging.message"
        params = {
            "operation": "send",
            # missing type, to, content
        }

        with pytest.raises(ValueError, match="Missing required parameters"):
            validator.validate_params(tool, params, ValidationMode.BASIC)

    def test_unknown_tool_no_validation(self, validator):
        """Test validation for unknown tool allows everything (default behavior)."""
        tool = "unknown_tool"
        params = {"any": "thing"}

        # In BASIC mode, unknown tool has no BASIC_PARAMS entry, so allowed_params is empty set
        # Thus everything filtered out?
        result = validator.validate_params(tool, params, ValidationMode.BASIC)
        assert result == {}

        # In ADVANCED mode
        result = validator.validate_params(tool, params, ValidationMode.ADVANCED)
        assert result == params

    def test_get_parameter_help(self, validator):
        """Test get_parameter_help returns correct info."""
        tool = "messaging.message"

        help_basic = validator.get_parameter_help(tool, ValidationMode.BASIC)
        assert help_basic["mode"] == "basic"
        assert "basic_params" in help_basic

        help_advanced = validator.get_parameter_help(tool, ValidationMode.ADVANCED)
        assert help_advanced["mode"] == "advanced"


class TestNarrowHelper:
    """Tests for NarrowHelper."""

    def test_static_methods(self):
        """Test static helper methods."""
        assert NarrowHelper.stream("general") == {
            "operator": "stream",
            "operand": "general",
        }
        assert NarrowHelper.topic("testing") == {
            "operator": "topic",
            "operand": "testing",
        }
        assert NarrowHelper.sender("me@example.com") == {
            "operator": "sender",
            "operand": "me@example.com",
        }
        assert NarrowHelper.search_text("hello") == {
            "operator": "search",
            "operand": "hello",
        }
        assert NarrowHelper.has_attachment() == {
            "operator": "has",
            "operand": "attachment",
        }
        assert NarrowHelper.is_private() == {"operator": "is", "operand": "private"}

    def test_build_basic_narrow(self):
        """Test build_basic_narrow combines filters."""
        narrow = NarrowHelper.build_basic_narrow(
            stream="general", topic="python", sender="me@example.com", text="bug"
        )

        assert len(narrow) == 4
        assert narrow[0] == {"operator": "stream", "operand": "general"}
        assert narrow[1] == {"operator": "topic", "operand": "python"}
        assert narrow[2] == {"operator": "sender", "operand": "me@example.com"}
        assert narrow[3] == {"operator": "search", "operand": "bug"}

    def test_build_basic_narrow_partial(self):
        """Test build_basic_narrow with partial args."""
        narrow = NarrowHelper.build_basic_narrow(stream="general")
        assert len(narrow) == 1
        assert narrow[0] == {"operator": "stream", "operand": "general"}


def test_global_validator():
    """Test global validator singleton access."""
    v1 = get_validator()
    v2 = get_validator()
    assert v1 is v2
    assert isinstance(v1, SimpleValidator)


def test_validate_tool_params_convenience():
    """Test convenience function."""
    params = {
        "operation": "send",
        "type": "stream",
        "to": "general",
        "content": "hello",
    }
    result = validate_tool_params("messaging.message", params)
    assert result == params
