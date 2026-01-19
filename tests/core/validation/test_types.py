"""Tests for core/validation/types.py."""

from src.zulipchat_mcp.core.validation.types import ParameterSchema, ToolSchema


class TestParameterSchema:
    """Tests for ParameterSchema."""

    def test_init_kwargs_mode(self):
        """Test initialization with kwargs."""
        ps = ParameterSchema(
            name="p1", type="str", description="desc", required=True, basic_param=True
        )
        assert ps.name == "p1"
        assert ps.type == "str"
        assert ps.required is True
        assert ps.basic_param is True

    def test_init_missing_flags_attributes(self):
        """Test that missing flags result in attributes being present (default False)."""
        # This currently FAILS in the codebase, we are adding this test to verify the fix
        ps = ParameterSchema(name="p1", type="str")

        # These assertions will fail before we fix types.py
        assert hasattr(ps, "basic_param")
        assert ps.basic_param is False
        assert hasattr(ps, "advanced_param")
        assert ps.advanced_param is False
        assert hasattr(ps, "expert_param")
        assert ps.expert_param is False

    def test_type_property(self):
        """Test type property returns string name."""
        ps = ParameterSchema(name="p1", param_type=int)
        assert ps.type == "int"

        ps = ParameterSchema(name="p2", type="str")
        assert ps.type == "str"


class TestToolSchema:
    """Tests for ToolSchema."""

    def test_init_categorizes_params(self):
        """Test that parameters are categorized into sets."""
        p1 = ParameterSchema(name="p1", type="str", basic_param=True)
        p2 = ParameterSchema(name="p2", type="str", advanced_param=True)
        p3 = ParameterSchema(name="p3", type="str", expert_param=True)

        ts = ToolSchema(name="tool", description="desc", parameters=[p1, p2, p3])

        assert "p1" in ts.basic_params
        assert "p2" in ts.advanced_params
        assert "p3" in ts.expert_params
