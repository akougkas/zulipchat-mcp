"""Tests for core/validation/schemas.py."""

from src.zulipchat_mcp.core.validation.schemas import (
    get_all_schemas,
    get_events_schemas,
    get_files_schemas,
    get_messaging_schemas,
    get_search_schemas,
    get_streams_schemas,
    get_users_schemas,
)
from src.zulipchat_mcp.core.validation.types import ToolSchema


class TestSchemas:
    """Tests for tool schemas."""

    def test_get_all_schemas(self):
        """Test that get_all_schemas returns a dictionary of ToolSchemas."""
        schemas = get_all_schemas()
        assert isinstance(schemas, dict)
        assert len(schemas) > 0

        for name, schema in schemas.items():
            assert isinstance(name, str)
            assert isinstance(schema, ToolSchema)
            assert schema.name == name
            assert len(schema.parameters) > 0

    def test_schema_structure(self):
        """Test structure of a specific schema (e.g. messaging.message)."""
        schemas = get_messaging_schemas()
        assert "messaging.message" in schemas
        schema = schemas["messaging.message"]

        # Check specific params
        param_names = [p.name for p in schema.parameters]
        assert "to" in param_names
        assert "content" in param_names
        assert "type" in param_names

        # Check categorization
        assert "to" in schema.basic_params
        assert "content" in schema.basic_params

    def test_individual_getters(self):
        """Test individual schema getter functions."""
        assert len(get_messaging_schemas()) > 0
        assert len(get_streams_schemas()) > 0
        assert len(get_users_schemas()) > 0
        assert len(get_events_schemas()) > 0
        assert len(get_search_schemas()) > 0
        assert len(get_files_schemas()) > 0

    def test_no_duplicate_tools(self):
        """Test that get_all_schemas doesn't have duplicate keys (implicit in dict, but check count)."""
        all_schemas = get_all_schemas()
        count = (
            len(get_messaging_schemas())
            + len(get_streams_schemas())
            + len(get_users_schemas())
            + len(get_events_schemas())
            + len(get_search_schemas())
            + len(get_files_schemas())
        )
        assert len(all_schemas) == count
