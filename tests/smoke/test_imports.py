"""Smoke imports for consolidated v2.5.0 modules to boost coverage of import paths.

These are fast and validate that modules import without raising.
"""

def test_import_core_modules():
    import zulipchat_mcp.core.identity  # noqa: F401
    import zulipchat_mcp.core.error_handling  # noqa: F401
    import zulipchat_mcp.core.validation.validators  # noqa: F401
    import zulipchat_mcp.core.validation.simple_validators  # noqa: F401
    import zulipchat_mcp.core.validation.schemas  # noqa: F401
    import zulipchat_mcp.core.validation.narrow  # noqa: F401
    import zulipchat_mcp.core.migration  # noqa: F401


def test_import_tool_modules():
    import zulipchat_mcp.tools.messaging_v25  # noqa: F401
    import zulipchat_mcp.tools.streams_v25  # noqa: F401
    import zulipchat_mcp.tools.events_v25  # noqa: F401
    import zulipchat_mcp.tools.users_v25  # noqa: F401
    import zulipchat_mcp.tools.search_v25  # noqa: F401
    import zulipchat_mcp.tools.files_v25  # noqa: F401
    import zulipchat_mcp.tools.admin_v25  # noqa: F401


def test_import_utils_and_services():
    import zulipchat_mcp.utils.logging  # noqa: F401
    import zulipchat_mcp.utils.metrics  # noqa: F401
    import zulipchat_mcp.services.scheduler  # noqa: F401
