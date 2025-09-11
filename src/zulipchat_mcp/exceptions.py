"""Compatibility wrapper for exceptions module - imports from core.exceptions."""

# Re-export everything from core.exceptions for backward compatibility
from .core.exceptions import *
from .core.exceptions import __all__ as _core_all

__all__ = _core_all if _core_all else []