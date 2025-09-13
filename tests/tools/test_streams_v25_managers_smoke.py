"""Lightweight coverage tests for streams_v25 manager bootstrap."""

from __future__ import annotations

import importlib


def test_streams_v25_get_managers_initializes_globals() -> None:
    mod = importlib.import_module("zulipchat_mcp.tools.streams_v25")
    # Reset globals to force all branches
    mod._config_manager = None
    mod._identity_manager = None
    mod._parameter_validator = None

    cfg, ident, validator = mod._get_managers()

    # Basic sanity checks
    assert cfg is not None
    assert ident is not None
    assert validator is not None
