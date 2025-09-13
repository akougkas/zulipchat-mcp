"""Optional real Zulip integration tests.

These tests exercise live Zulip endpoints using credentials from .env or the
environment. They are marked as integration and skipped by default.

How to run locally (outside CI):
- Create a .env file with: ZULIP_EMAIL, ZULIP_API_KEY, ZULIP_SITE
- Optionally set RUN_REAL_ZULIP_TESTS=1 to force-enable
- Run: uv run pytest -q -m integration

Notes:
- Tests are read-only (no message sends or stream mutations)
- Keep them fast and deterministic; prefer simple GET endpoints
"""

from __future__ import annotations

import asyncio
import os

import pytest
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


def _have_creds() -> bool:
    return bool(
        os.getenv("ZULIP_EMAIL")
        and os.getenv("ZULIP_API_KEY")
        and os.getenv("ZULIP_SITE")
    )


require_real = pytest.mark.skipif(
    not (
        _have_creds()
        and os.getenv("RUN_REAL_ZULIP_TESTS", "0") in {"1", "true", "True"}
    ),
    reason="Real Zulip credentials not provided or RUN_REAL_ZULIP_TESTS not enabled",
)


@pytest.mark.integration
@require_real
def test_zulip_python_client_basic_auth() -> None:
    import zulip

    client = zulip.Client(
        email=os.environ["ZULIP_EMAIL"],
        api_key=os.environ["ZULIP_API_KEY"],
        site=os.environ["ZULIP_SITE"],
    )

    # Simple, read-only endpoints
    profile = client.get_profile()
    assert profile.get("result") == "success"
    assert profile.get("email")

    users = client.get_users(request={"client_gravatar": False})
    assert users.get("result") == "success"
    assert isinstance(users.get("members"), list)


@pytest.mark.integration
@require_real
def test_get_streams_via_python_client() -> None:
    import zulip

    client = zulip.Client(
        email=os.environ["ZULIP_EMAIL"],
        api_key=os.environ["ZULIP_API_KEY"],
        site=os.environ["ZULIP_SITE"],
    )

    streams = client.get_streams(include_public=True, include_subscribed=True)
    assert streams.get("result") == "success"
    assert isinstance(streams.get("streams"), list)


@pytest.mark.integration
@require_real
def test_manage_streams_list_via_tool() -> None:
    # Exercise the v2.5.0 tool through Identity/Config layers
    from zulipchat_mcp.tools.streams_v25 import manage_streams

    async def _run():
        res = await manage_streams(
            operation="list", include_public=True, include_subscribed=True
        )
        assert res.get("status") == "success"
        assert res.get("operation") == "list"
        assert isinstance(res.get("streams"), list)

    asyncio.run(_run())
