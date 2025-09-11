"""Compatibility wrapper for client module - imports from core.client."""

# Re-export everything from core.client for backward compatibility
from .core.client import *
from .core.client import __all__ as _core_all

__all__ = _core_all if _core_all else []