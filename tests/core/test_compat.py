"""Tests for core/compat.py - the temporary ping surface patch.

Tracks upstream https://github.com/modelcontextprotocol/python-sdk/issues/3273;
when an mcp/mcp-types release ships the fix, the "already present" path covers
it and this module (and file) should be deleted.
"""

import subprocess
import sys

from src.zulipchat_mcp.core import compat


def test_upstream_still_requires_patch():
    """Fail when the installed mcp-types release makes this patch obsolete."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import mcp_types.methods as methods; "
                "assert ('ping', '2026-07-28') not in methods.CLIENT_REQUESTS"
            ),
        ],
        check=True,
    )


def test_patch_registers_ping_for_modern_era():
    import mcp_types.methods as methods

    # Importing the package must apply the patch for embedded server entry points.
    assert ("ping", "2026-07-28") in methods.CLIENT_REQUESTS
    assert ("ping", "2026-07-28") in methods.SERVER_REQUESTS
    assert ("ping", "2026-07-28") in methods.SERVER_RESULTS
    assert ("ping", "2026-07-28") in methods.CLIENT_RESULTS


def test_patch_rebinds_validation_defaults():
    """validate/serialize functions must see the patched surface via defaults."""
    compat.apply()

    from mcp_types.methods import (
        parse_client_request,
        serialize_server_result,
        validate_client_request,
        validate_server_result,
    )

    validate_client_request("ping", "2026-07-28", None)
    req = parse_client_request("ping", "2026-07-28", None)
    assert type(req).__name__ == "PingRequest"

    dumped = serialize_server_result("ping", "2026-07-28", {})
    assert dumped == {}
    validate_server_result("ping", "2026-07-28", {})


def test_patch_is_idempotent():
    compat.apply()
    compat.apply()  # second call must not raise or duplicate

    import mcp_types.methods as methods

    assert list(methods.CLIENT_REQUESTS).count(("ping", "2026-07-28")) == 1


def test_patch_does_not_write_protocol_stdout(capsys):
    compat.apply()

    assert capsys.readouterr().out == ""


def test_patch_preserves_other_methods():
    """The patched maps must be supersets of the originals."""
    import mcp_types.methods as methods

    original_count = len(methods.CLIENT_REQUESTS)
    compat.apply()
    # At most one row added per surface; nothing removed.
    assert len(methods.CLIENT_REQUESTS) <= original_count + 1
    assert ("tools/call", "2026-07-28") in methods.CLIENT_REQUESTS
    assert ("initialize", "2025-11-25") in methods.CLIENT_REQUESTS
