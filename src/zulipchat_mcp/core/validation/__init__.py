"""Parameter validation module for ZulipChat MCP.

This module provides simplified parameter validation following the
'simple by default, powerful when needed' principle.
"""

from __future__ import annotations

# Export main classes and functions
from .narrow import NarrowBuilder, NarrowFilter, NarrowOperator

# New simplified validators
from .simple_validators import NarrowHelper, SimpleValidator, validate_tool_params
from .simple_validators import ValidationMode as SimpleMode
from .types import ParameterSchema, ToolSchema, ValidationMode
from .validators import ParameterValidator, get_parameter_validator

__all__ = [
    "NarrowFilter",
    "NarrowBuilder",
    "NarrowOperator",
    "ParameterSchema",
    "ToolSchema",
    "ValidationMode",
    "ParameterValidator",
    "get_parameter_validator",
    # Simplified exports
    "SimpleValidator",
    "NarrowHelper",
    "SimpleMode",
    "validate_tool_params",
]
