"""Optional real Zulip integration tests.

These tests exercise live Zulip endpoints using credentials from zuliprc files.
They are marked as integration and skipped by default.

How to run locally (outside CI):
- Set ZULIP_CONFIG_FILE to point to your zuliprc file
- Set RUN_REAL_ZULIP_TESTS=1 to enable
- Run: uv run pytest -q -m integration

Example:
  ZULIP_CONFIG_FILE=~/.zuliprc RUN_REAL_ZULIP_TESTS=1 uv run pytest -m integration

Notes:
- Tests are read-only (no message sends or stream mutations)
- Keep them fast and deterministic; prefer simple GET endpoints
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest


def _find_zuliprc() -> str | None:
    """Find a zuliprc file in standard locations."""
    # Check explicit environment variable first
    if os.getenv("ZULIP_CONFIG_FILE"):
        path = os.path.expanduser(os.getenv("ZULIP_CONFIG_FILE", ""))
        if os.path.exists(path):
            return path

    # Check standard locations
    home = Path.home()
    candidates = [
        Path.cwd() / "zuliprc",
        home / ".zuliprc",
        home / ".config" / "zulip" / "zuliprc",
    ]

    # Also check for named zuliprc files (common pattern)
    for pattern_file in home.glob(".zuliprc-*"):
        candidates.append(pattern_file)

    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _have_creds() -> bool:
    """Check if we have valid credentials available."""
    return _find_zuliprc() is not None


require_real = pytest.mark.skipif(
    not (
        _have_creds()
        and os.getenv("RUN_REAL_ZULIP_TESTS", "0") in {"1", "true", "True"}
    ),
    reason="Real Zulip credentials not provided or RUN_REAL_ZULIP_TESTS not enabled",
)


def _get_client_kwargs() -> dict[str, str]:
    """Get kwargs for zulip.Client initialization."""
    config_file = _find_zuliprc()
    if not config_file:
        raise ValueError("No zuliprc file found")
    return {"config_file": config_file}


@pytest.mark.integration
@require_real
def test_zulip_python_client_basic_auth() -> None:
    import zulip

    client = zulip.Client(**_get_client_kwargs())

    # Simple, read-only endpoints
    profile = client.get_profile()
    assert profile.get("result") == "success"
    # assert profile.get("email") # Profile might not have email depending on permissions, check ID instead
    assert profile.get("user_id") or profile.get("email")

    users = client.get_users(request={"client_gravatar": False})
    assert users.get("result") == "success"
    assert isinstance(users.get("members"), list)


@pytest.mark.integration
@require_real
def test_get_streams_via_python_client() -> None:
    import zulip

    client = zulip.Client(**_get_client_kwargs())

    streams = client.get_streams(include_public=True, include_subscribed=True)
    assert streams.get("result") == "success"
    assert isinstance(streams.get("streams"), list)


@pytest.mark.integration
@require_real
def test_zulip_client_wrapper() -> None:
    """Test ZulipClientWrapper with zuliprc file."""
    from zulipchat_mcp.config import ConfigManager
    from zulipchat_mcp.core.client import ZulipClientWrapper

    config_file = _find_zuliprc()
    config = ConfigManager(config_file=config_file)
    assert config.validate_config()

    wrapper = ZulipClientWrapper(config)
    assert wrapper.identity in ("user", "bot")

    # Test lazy loading - should not be connected yet
    assert not wrapper.is_connected

    # Trigger connection via API call
    streams = wrapper.get_streams()
    assert streams.get("result") == "success"
    assert isinstance(streams.get("streams"), list)

    # Should be connected now
    assert wrapper.is_connected
