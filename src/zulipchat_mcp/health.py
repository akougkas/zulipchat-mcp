"""Compatibility wrapper for health module - imports from utils.health."""

# Re-export everything from utils.health for backward compatibility
from .utils.health import *
from .utils.health import __all__ as _utils_all

__all__ = _utils_all if _utils_all else []