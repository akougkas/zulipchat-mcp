"""Create agent bots and store their credentials.

Clients are ``zulip.Client`` instances or ``ZulipClientWrapper`` objects;
both reach the REST API through ``call_endpoint``. Calls are synchronous.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

GENERIC_BOT = 1
GUEST_ROLE = 600


class ProvisionError(RuntimeError):
    """Zulip refused a provisioning call or returned an unusable response."""


def _call(client: Any, path: str, method: str, request: dict[str, Any]) -> Any:
    endpoint = getattr(client, "call_endpoint", None) or client.client.call_endpoint
    response = endpoint(path, method=method, request=request)
    if not isinstance(response, dict) or response.get("result") != "success":
        message = response.get("msg") if isinstance(response, dict) else response
        raise ProvisionError(f"{method} /{path} failed: {message}")
    return response


def create_agent_bot(
    owner_client: Any, full_name: str, short_name: str
) -> dict[str, Any]:
    """Create a Generic bot owned by the caller via ``POST /bots``.

    Zulip only lets human, non-guest accounts create bots, so the owner's
    profile is checked first. Returns ``user_id``, ``email``, ``api_key``
    and ``full_name``.
    """
    me = _call(owner_client, "users/me", "GET", {})
    if me.get("is_bot"):
        raise ProvisionError("agent bots must be created with a human API key")
    if me.get("role") == GUEST_ROLE:
        raise ProvisionError("guest accounts cannot create bots")
    created = _call(
        owner_client,
        "bots",
        "POST",
        {"full_name": full_name, "short_name": short_name, "bot_type": GENERIC_BOT},
    )
    user_id, api_key = created.get("user_id"), created.get("api_key")
    if not isinstance(user_id, int) or not api_key:
        raise ProvisionError("POST /bots returned no user_id or api_key")
    email = created.get("email")
    if not email:
        email = _call(owner_client, f"users/{user_id}", "GET", {})["user"]["email"]
    return {
        "user_id": user_id,
        "email": email,
        "api_key": api_key,
        "full_name": full_name,
    }


def write_bot_zuliprc(path: str | Path, email: str, api_key: str, site: str) -> Path:
    """Write a 0600 zuliprc, creating missing directories as 0700.

    An existing file is never overwritten: ``FileExistsError`` is raised.
    """
    for value in (email, api_key, site):
        if "\n" in value or "\r" in value:
            raise ValueError("zuliprc values must be single-line")
    target = Path(path).expanduser()
    missing = [p for p in (target.parent, *target.parent.parents) if not p.exists()]
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(f"[api]\nemail={email}\nkey={api_key}\nsite={site}\n")
    os.chmod(target, 0o600)
    return target


def bot_owner_id(bot_client: Any) -> int | None:
    """Return the bot owner's user ID, or None when the bot has no owner.

    Raises ``ProvisionError`` when Zulip refuses either profile read.
    """
    me = _call(bot_client, "users/me", "GET", {})
    profile = _call(bot_client, f"users/{me['user_id']}", "GET", {})
    owner = profile.get("user", {}).get("bot_owner_id")
    return owner if isinstance(owner, int) else None
