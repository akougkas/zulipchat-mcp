"""Type definitions for parameter validation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ValidationMode(Enum):
    """Validation modes for parameter disclosure."""

    BASIC = "basic"  # Only essential parameters
    ADVANCED = "advanced"  # All parameters including optional ones
    EXPERT = "expert"  # All parameters with internal/debug options


class ParameterSchemaBase(BaseModel):
    """Base schema definition for tool parameters."""

    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None
    basic_param: bool = False  # Is this a basic parameter?
    advanced_param: bool = False  # Is this an advanced parameter?
    expert_param: bool = False  # Is this an expert parameter?
    choices: list[Any] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    pattern: str | None = None  # Regex pattern for strings


class ParameterSchema:
    """Schema definition for tool parameters with flexible constructor."""

    def __init__(
        self,
        name_or_arg1: str | None = None,
        param_type_or_arg2: type | str | None = None,
        required_or_arg3: bool | None = None,
        description: str = "",
        default: Any = None,
        validation_modes: set[ValidationMode] | None = None,
        **kwargs: Any
    ) -> None:
        """Initialize parameter schema.
        
        Supports multiple call patterns:
        1. ParameterSchema(name="...", param_type=..., ...)  # keyword args
        2. ParameterSchema("name", str, True, ...)  # positional args
        """
        # Detect if called with keyword arguments based on the first parameter name
        if isinstance(name_or_arg1, str) and 'param_type' in kwargs:
            # Keyword argument mode
            self.name = name_or_arg1
            self.param_type = kwargs.pop('param_type', str)
            self.required = kwargs.pop('required', False)
            self.description = kwargs.pop('description', "")
            self.default = kwargs.pop('default', None)
            self.validation_modes = kwargs.pop('validation_modes', set())
        elif param_type_or_arg2 is not None or required_or_arg3 is not None:
            # Positional argument mode
            self.name = name_or_arg1 or ""
            self.param_type = param_type_or_arg2 or str
            self.required = required_or_arg3 if required_or_arg3 is not None else False
            self.description = description
            self.default = default
            self.validation_modes = validation_modes or set()
        else:
            # Keyword-only mode (when called with name= keyword)
            self.name = kwargs.get('name', name_or_arg1 or "")
            self.param_type = kwargs.get('param_type', param_type_or_arg2 or str)
            self.required = kwargs.get('required', required_or_arg3 if required_or_arg3 is not None else False)
            self.description = kwargs.get('description', description)
            self.default = kwargs.get('default', default)
            self.validation_modes = kwargs.get('validation_modes', validation_modes or set())
            # Remove handled kwargs
            for key in ['name', 'param_type', 'required', 'description', 'default', 'validation_modes']:
                kwargs.pop(key, None)

        # Initialize optional attributes with defaults
        self.choices = None
        self.min_value = None
        self.max_value = None
        self.pattern = None

        # Handle any additional kwargs
        for key, value in kwargs.items():
            # Handle 'type' keyword argument by mapping it to param_type
            if key == 'type':
                self.param_type = value
            else:
                setattr(self, key, value)

    @property
    def type(self) -> str:
        """Get type as string for compatibility."""
        if isinstance(self.param_type, type):
            return self.param_type.__name__
        return str(self.param_type)


class ToolSchemaBase(BaseModel):
    """Base complete schema for a tool."""

    name: str
    description: str
    parameters: list[Any]  # Will be ParameterSchema instances
    basic_params: set[str] = Field(default_factory=set)
    advanced_params: set[str] = Field(default_factory=set)
    expert_params: set[str] = Field(default_factory=set)

    def model_post_init(self, __context: Any) -> None:
        """Categorize parameters into basic, advanced, and expert after initialization."""
        for param in self.parameters:
            # If no level is explicitly set, default to basic
            if hasattr(param, 'basic_param'):
                if not param.basic_param and not param.advanced_param and not param.expert_param:
                    param.basic_param = True

                if param.basic_param:
                    self.basic_params.add(param.name)
                if param.advanced_param:
                    self.advanced_params.add(param.name)
                if param.expert_param:
                    self.expert_params.add(param.name)


class ToolSchema:
    """Complete schema for a tool with flexible constructor."""

    def __init__(
        self,
        name_or_arg1: str | None = None,
        description_or_arg2: str | None = None,
        parameters_or_arg3: list[Any] | None = None,
        **kwargs: Any
    ) -> None:
        """Initialize tool schema.
        
        Supports multiple call patterns:
        1. ToolSchema(name="...", description="...", parameters=[...])  # keyword args
        2. ToolSchema("name", "description", [...])  # positional args
        """
        # Handle positional arguments
        if description_or_arg2 is not None or parameters_or_arg3 is not None:
            # Positional mode
            self.name = name_or_arg1 or ""
            self.description = description_or_arg2 or ""
            self.parameters = parameters_or_arg3 or []
        else:
            # Keyword mode
            self.name = kwargs.get('name', name_or_arg1 or "")
            self.description = kwargs.get('description', "")
            self.parameters = kwargs.get('parameters', [])

        # Initialize parameter sets
        self.basic_params = set()
        self.advanced_params = set()
        self.expert_params = set()

        # Categorize parameters
        for param in self.parameters:
            # Handle both validation_modes and individual level flags
            if hasattr(param, 'validation_modes') and param.validation_modes:
                modes = param.validation_modes
                if ValidationMode.BASIC in modes:
                    self.basic_params.add(param.name)
                if ValidationMode.ADVANCED in modes:
                    self.advanced_params.add(param.name)
                if ValidationMode.EXPERT in modes:
                    self.expert_params.add(param.name)
            else:
                # Use individual level flags
                if getattr(param, 'basic_param', False):
                    self.basic_params.add(param.name)
                if getattr(param, 'advanced_param', False):
                    self.advanced_params.add(param.name)
                if getattr(param, 'expert_param', False):
                    self.expert_params.add(param.name)
