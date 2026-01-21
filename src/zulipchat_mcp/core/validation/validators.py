"""Parameter validation logic and utility functions."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ...utils.logging import get_logger
from ..exceptions import ValidationError
from .narrow import NarrowFilter
from .schemas import get_all_schemas
from .types import ParameterSchema, ToolSchema, ValidationMode

logger = get_logger(__name__)


class ParameterValidator:
    """Unified parameter validation with progressive disclosure support."""

    def __init__(self) -> None:
        """Initialize parameter validator with tool schemas."""
        self.tool_schemas: dict[str, ToolSchema] = get_all_schemas()

    def validate_tool_params(
        self,
        tool: str,
        params: dict[str, Any],
        mode: ValidationMode = ValidationMode.BASIC,
    ) -> dict[str, Any]:
        """Validate and filter parameters based on usage mode.

        Args:
            tool: Tool name to validate parameters for
            params: Parameters to validate
            mode: Validation mode (basic, advanced, expert)

        Returns:
            Validated and filtered parameters

        Raises:
            ValidationError: If parameters are invalid
        """
        schema = self.tool_schemas.get(tool)
        if not schema:
            logger.warning(f"No schema defined for tool {tool}, passing through params")
            return params

        # Normalize parameters: treat explicit None as "not provided" for validation
        # Many MCP clients include all function parameters with null values by default.
        # Dropping None values here ensures optional parameters don't trigger type errors
        # and required-parameter checks behave correctly.
        params = {k: v for k, v in params.items() if v is not None}

        validated: dict[str, Any] = {}
        errors = []

        # Determine which parameters are allowed based on mode
        allowed_params = set()
        if mode == ValidationMode.BASIC:
            allowed_params = schema.basic_params
        elif mode == ValidationMode.ADVANCED:
            allowed_params = schema.basic_params | schema.advanced_params
        elif mode == ValidationMode.EXPERT:
            allowed_params = (
                schema.basic_params | schema.advanced_params | schema.expert_params
            )

        # Check for required parameters
        for param_schema in schema.parameters:
            if param_schema.required and param_schema.name not in params:
                errors.append(f"Required parameter '{param_schema.name}' is missing")

        # Validate provided parameters
        for param_name, param_value in params.items():
            # Skip parameters not allowed in current mode
            if mode != ValidationMode.EXPERT and param_name not in allowed_params:
                logger.debug(f"Filtering out {param_name} in {mode.value} mode")
                continue

            # Find parameter schema
            param_schema = next(
                (p for p in schema.parameters if p.name == param_name), None
            )
            if not param_schema:
                if mode == ValidationMode.EXPERT:
                    # In expert mode, allow unknown parameters
                    validated[param_name] = param_value
                    continue
                else:
                    errors.append(f"Unknown parameter '{param_name}'")
                    continue

            # Validate parameter type and constraints
            try:
                validated_value = self._validate_param_value(param_schema, param_value)
                validated[param_name] = validated_value
            except Exception as e:
                errors.append(f"Invalid value for '{param_name}': {e}")

        # Add default values for missing optional parameters
        for param_schema in schema.parameters:
            if (
                param_schema.name not in validated
                and not param_schema.required
                and param_schema.default is not None
                and param_schema.name in allowed_params
            ):
                validated[param_schema.name] = param_schema.default

        if errors:
            raise ValidationError(self._humanize_errors(errors, tool))

        return validated

    def _validate_param_value(self, schema: ParameterSchema, value: Any) -> Any:
        """Validate a single parameter value against its schema.

        Args:
            schema: Parameter schema
            value: Value to validate

        Returns:
            Validated value (possibly converted)

        Raises:
            ValueError: If value is invalid
        """
        # Skip validation for None values on optional parameters
        if value is None and not schema.required:
            return None

        # Type validation and conversion
        if schema.type == "str" and not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value).__name__}")
        elif schema.type == "int":
            if not isinstance(value, int):
                # Try to convert from string
                if isinstance(value, str) and value.isdigit():
                    value = int(value)
                else:
                    raise ValueError(f"Expected integer, got {type(value).__name__}")
        elif schema.type == "float":
            if not isinstance(value, (int, float)):
                # Try to convert from string
                if isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        raise ValueError(
                            f"Expected number, got {type(value).__name__}"
                        ) from None
                else:
                    raise ValueError(f"Expected number, got {type(value).__name__}")
        elif schema.type == "bool":
            if not isinstance(value, bool):
                # Try to convert from string
                if isinstance(value, str):
                    if value.lower() in ("true", "1", "yes", "on"):
                        value = True
                    elif value.lower() in ("false", "0", "no", "off"):
                        value = False
                    else:
                        raise ValueError(f"Invalid boolean value: {value}")
                else:
                    raise ValueError(f"Expected boolean, got {type(value).__name__}")
        elif schema.type == "list" and not isinstance(value, list):
            raise ValueError(f"Expected list, got {type(value).__name__}")
        elif schema.type == "dict" and not isinstance(value, dict):
            raise ValueError(f"Expected dictionary, got {type(value).__name__}")
        elif schema.type == "bytes":
            if not isinstance(value, (bytes, bytearray)):
                # Try to encode string as UTF-8
                if isinstance(value, str):
                    value = value.encode("utf-8")
                else:
                    raise ValueError(f"Expected bytes, got {type(value).__name__}")
        elif schema.type == "datetime" and not isinstance(value, datetime):
            # Try to parse string as datetime
            if isinstance(value, str):
                try:
                    # Support ISO format and common patterns
                    if "T" in value or "+" in value or "Z" in value:
                        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    else:
                        # Try common formats
                        try:
                            from dateutil import parser

                            value = parser.parse(value)
                        except ImportError:
                            # Fall back to basic parsing
                            raise ValueError(
                                f"Invalid datetime format: {value}"
                            ) from None
                except ValueError:
                    raise ValueError(f"Invalid datetime format: {value}") from None
            else:
                raise ValueError(f"Expected datetime, got {type(value).__name__}")
        elif "|" in schema.type:
            # Handle union types like "str|list" or "str|int"
            allowed_types = schema.type.split("|")
            type_matched = False
            for allowed_type in allowed_types:
                allowed_type = allowed_type.strip()
                try:
                    # Try validation with each allowed type
                    temp_schema = ParameterSchema(
                        name=schema.name,
                        type=allowed_type,
                        description=schema.description,
                    )
                    self._validate_param_value(temp_schema, value)
                    type_matched = True
                    break
                except ValueError:
                    continue
            if not type_matched:
                raise ValueError(
                    f"Expected one of {allowed_types}, got {type(value).__name__}"
                )

        # Choice validation
        if schema.choices and value not in schema.choices:
            raise ValueError(f"Must be one of {schema.choices}")

        # Range validation
        if schema.min_value is not None and value < schema.min_value:
            raise ValueError(f"Must be at least {schema.min_value}")
        if schema.max_value is not None and value > schema.max_value:
            raise ValueError(f"Must be at most {schema.max_value}")

        # Pattern validation (for strings)
        if schema.pattern and isinstance(value, str):
            if not re.match(schema.pattern, value):
                raise ValueError(f"Does not match required pattern: {schema.pattern}")

        return value

    def _humanize_errors(self, errors: list[str], tool: str) -> str:
        """Convert technical validation errors to user-friendly messages.

        Args:
            errors: List of error messages
            tool: Tool name

        Returns:
            Human-readable error message
        """
        if len(errors) == 1:
            return f"Parameter validation failed for {tool}: {errors[0]}"
        else:
            error_list = "\n  - ".join(errors)
            return f"Parameter validation failed for {tool}:\n  - {error_list}"

    def get_tool_help(
        self, tool: str, mode: ValidationMode = ValidationMode.BASIC
    ) -> dict[str, Any]:
        """Get help information for a tool's parameters.

        Args:
            tool: Tool name
            mode: Validation mode

        Returns:
            Dictionary with parameter help information
        """
        schema = self.tool_schemas.get(tool)
        if not schema:
            return {"error": f"No schema defined for tool {tool}"}

        # Determine which parameters to show
        if mode == ValidationMode.BASIC:
            params_to_show = [
                p for p in schema.parameters if p.name in schema.basic_params
            ]
        elif mode == ValidationMode.ADVANCED:
            params_to_show = [
                p
                for p in schema.parameters
                if p.name in (schema.basic_params | schema.advanced_params)
            ]
        else:  # EXPERT
            params_to_show = schema.parameters

        return {
            "tool": tool,
            "description": schema.description,
            "mode": mode.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "choices": p.choices,
                    "level": (
                        "basic"
                        if p.basic_param
                        else "advanced" if p.advanced_param else "expert"
                    ),
                }
                for p in params_to_show
            ],
        }

    def suggest_mode(self, tool: str, params: dict[str, Any]) -> ValidationMode:
        """Suggest the appropriate validation mode based on provided parameters.

        Args:
            tool: Tool name
            params: Provided parameters

        Returns:
            Suggested validation mode
        """
        schema = self.tool_schemas.get(tool)
        if not schema:
            return ValidationMode.BASIC

        # Check what level of parameters are being used
        has_expert = any(p in schema.expert_params for p in params)
        has_advanced = any(p in schema.advanced_params for p in params)

        if has_expert:
            return ValidationMode.EXPERT
        elif has_advanced:
            return ValidationMode.ADVANCED
        else:
            return ValidationMode.BASIC

    def get_available_tools(self) -> list[str]:
        """Get list of all tools with validation schemas.

        Returns:
            List of tool names with schemas defined
        """
        return list(self.tool_schemas.keys())

    def validate_narrow_filters(self, narrow: list[Any]) -> list[NarrowFilter]:
        """Validate and convert narrow filters to NarrowFilter objects.

        Args:
            narrow: List of narrow filter dictionaries or NarrowFilter objects

        Returns:
            List of validated NarrowFilter objects

        Raises:
            ValidationError: If narrow filters are invalid
        """
        if not isinstance(narrow, list):
            raise ValidationError("Narrow must be a list of filter objects")

        validated_filters = []
        for i, filter_data in enumerate(narrow):
            try:
                if isinstance(filter_data, NarrowFilter):
                    validated_filters.append(filter_data)
                elif isinstance(filter_data, dict):
                    validated_filters.append(NarrowFilter.from_dict(filter_data))
                else:
                    raise ValidationError(
                        f"Invalid narrow filter type: {type(filter_data).__name__}"
                    )
            except Exception as e:
                raise ValidationError(
                    f"Invalid narrow filter at index {i}: {e}"
                ) from None

        return validated_filters

    def get_parameter_help(self, tool: str, parameter: str) -> dict[str, Any] | None:
        """Get detailed help for a specific parameter.

        Args:
            tool: Tool name
            parameter: Parameter name

        Returns:
            Parameter help information or None if not found
        """
        schema = self.tool_schemas.get(tool)
        if not schema:
            return None

        param_schema = next((p for p in schema.parameters if p.name == parameter), None)
        if not param_schema:
            return None

        return {
            "name": param_schema.name,
            "type": param_schema.type,
            "description": param_schema.description,
            "required": param_schema.required,
            "default": param_schema.default,
            "choices": param_schema.choices,
            "min_value": param_schema.min_value,
            "max_value": param_schema.max_value,
            "pattern": param_schema.pattern,
            "level": (
                "basic"
                if param_schema.basic_param
                else "advanced" if param_schema.advanced_param else "expert"
            ),
        }

    def validate_time_range(self, time_range: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize time range parameters.

        Args:
            time_range: Time range dictionary with 'start', 'end', 'days', etc.

        Returns:
            Normalized time range dictionary

        Raises:
            ValidationError: If time range is invalid
        """
        if not isinstance(time_range, dict):
            raise ValidationError("Time range must be a dictionary")

        validated: dict[str, Any] = {}

        # Handle different time range formats
        if "days" in time_range:
            days = time_range["days"]
            if not isinstance(days, int) or days <= 0:
                raise ValidationError("Days must be a positive integer")
            validated["days"] = days

        if "start" in time_range:
            start = time_range["start"]
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                except ValueError:
                    raise ValidationError(f"Invalid start datetime: {start}") from None
            elif not isinstance(start, datetime):
                raise ValidationError("Start time must be datetime or ISO string")
            validated["start"] = start

        if "end" in time_range:
            end = time_range["end"]
            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end.replace("Z", "+00:00"))
                except ValueError:
                    raise ValidationError(f"Invalid end datetime: {end}") from None
            elif not isinstance(end, datetime):
                raise ValidationError("End time must be datetime or ISO string")
            validated["end"] = end

        # Validate that start is before end
        if "start" in validated and "end" in validated:
            if validated["start"] >= validated["end"]:
                raise ValidationError("Start time must be before end time")

        return validated


# Global validator instance
_parameter_validator: ParameterValidator | None = None


def get_parameter_validator() -> ParameterValidator:
    """Get or create the global parameter validator instance.

    Returns:
        Global ParameterValidator instance
    """
    global _parameter_validator
    if _parameter_validator is None:
        _parameter_validator = ParameterValidator()
    return _parameter_validator
