"""Tests for core/validation/narrow.py."""

import pytest
from datetime import datetime
from pydantic import ValidationError as PydanticValidationError
from src.zulipchat_mcp.core.validation.narrow import (
    NarrowFilter,
    NarrowOperator,
    NarrowBuilder,
    ValidationError,
)


class TestNarrowFilter:
    """Tests for NarrowFilter model."""

    def test_init_positional(self):
        """Test initialization with positional arguments."""
        nf = NarrowFilter(NarrowOperator.STREAM, "general")
        assert nf.operator == NarrowOperator.STREAM
        assert nf.operand == "general"
        assert nf.negated is False

    def test_init_keyword(self):
        """Test initialization with keyword arguments."""
        nf = NarrowFilter(operator=NarrowOperator.TOPIC, operand="stuff", negated=True)
        assert nf.operator == NarrowOperator.TOPIC
        assert nf.operand == "stuff"
        assert nf.negated is True

    def test_validate_operand_id_must_be_int(self):
        """Test that ID operator requires integer operand."""
        with pytest.raises(PydanticValidationError, match="ID operator requires integer operand"):
            NarrowFilter(NarrowOperator.ID, "123")
    
    def test_validate_operand_stream_must_be_str(self):
        """Test that STREAM operator requires string operand."""
        with pytest.raises(PydanticValidationError, match="NarrowOperator.STREAM operator requires string operand"):
            NarrowFilter(NarrowOperator.STREAM, 123)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        nf = NarrowFilter(NarrowOperator.SENDER, "me@example.com", negated=True)
        data = nf.to_dict()
        assert data == {
            "operator": "sender",
            "operand": "me@example.com",
            "negated": True,
        }

    def test_to_dict_not_negated(self):
        """Test conversion to dictionary when not negated."""
        nf = NarrowFilter(NarrowOperator.SEARCH, "query")
        data = nf.to_dict()
        assert data == {
            "operator": "search",
            "operand": "query",
        }
        assert "negated" not in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {"operator": "stream", "operand": "devel"}
        nf = NarrowFilter.from_dict(data)
        assert nf.operator == NarrowOperator.STREAM
        assert nf.operand == "devel"
        assert nf.negated is False

    def test_from_dict_invalid_operator(self):
        """Test creation from dictionary with invalid operator."""
        data = {"operator": "invalid", "operand": "stuff"}
        with pytest.raises(ValidationError, match="Invalid narrow operator"):
            NarrowFilter.from_dict(data)

    def test_from_dict_invalid_data(self):
        """Test creation from dictionary with missing operand (raises Pydantic error caught)."""
        data = {"operator": "stream"}
        with pytest.raises(ValidationError, match="Invalid narrow filter data"):
            NarrowFilter.from_dict(data)
            
    def test_str_representation(self):
        """Test string representation."""
        nf = NarrowFilter(NarrowOperator.STREAM, "general")
        assert str(nf) == "NarrowFilter(operator=stream, operand=general)"

    def test_equality(self):
        """Test equality comparison."""
        nf1 = NarrowFilter(NarrowOperator.STREAM, "general")
        nf2 = NarrowFilter(NarrowOperator.STREAM, "general")
        nf3 = NarrowFilter(NarrowOperator.STREAM, "random")
        nf4 = "Not a filter"
        
        assert nf1 == nf2
        assert nf1 != nf3
        assert nf1 != nf4


class TestNarrowBuilder:
    """Tests for NarrowBuilder."""

    def test_builder_methods(self):
        """Test fluent builder methods."""
        builder = NarrowBuilder()
        builder.stream("general").topic("stuff").sender("me@example.com")
        
        assert len(builder.filters) == 3
        assert builder.filters[0].operator == NarrowOperator.STREAM
        assert builder.filters[1].operator == NarrowOperator.TOPIC
        assert builder.filters[2].operator == NarrowOperator.SENDER

    def test_has_and_is(self):
        """Test has() and is_filter() methods."""
        builder = NarrowBuilder()
        builder.has("attachment").is_filter("private", negated=True)
        
        assert builder.filters[0].operator == NarrowOperator.HAS
        assert builder.filters[0].operand == "attachment"
        assert builder.filters[1].operator == NarrowOperator.IS
        assert builder.filters[1].operand == "private"
        assert builder.filters[1].negated is True

    def test_search(self):
        """Test search() method."""
        builder = NarrowBuilder()
        builder.search("keyword")
        assert builder.filters[0].operator == NarrowOperator.SEARCH
        assert builder.filters[0].operand == "keyword"

    def test_time_range(self):
        """Test time_range() method."""
        builder = NarrowBuilder()
        dt1 = datetime(2023, 1, 1, 12, 0, 0)
        dt2 = datetime(2023, 1, 2, 12, 0, 0)
        
        builder.time_range(dt1, dt2)
        
        assert len(builder.filters) == 2
        assert builder.filters[0].operand == "after:2023-01-01T12:00:00"
        assert builder.filters[1].operand == "before:2023-01-02T12:00:00"

    def test_build(self):
        """Test build() returns list of dicts."""
        builder = NarrowBuilder()
        result = builder.stream("general").build()
        assert result == [{"operator": "stream", "operand": "general"}]

    def test_from_dict_static(self):
        """Test static from_dict method."""
        data = [{"operator": "stream", "operand": "general"}]
        filters = NarrowBuilder.from_dict(data)
        assert len(filters) == 1
        assert filters[0].operator == NarrowOperator.STREAM
