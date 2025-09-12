"""Smoke tests for back-compat wrappers to improve coverage."""

from __future__ import annotations


def test_import_client_commands_exceptions() -> None:
    # Importing these modules should succeed and expose __all__
    import zulipchat_mcp.client as client_mod
    import zulipchat_mcp.commands as commands_mod
    import zulipchat_mcp.exceptions as exceptions_mod

    assert hasattr(client_mod, "__all__")
    assert hasattr(commands_mod, "__all__")
    assert hasattr(exceptions_mod, "__all__")

