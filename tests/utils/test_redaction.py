"""Secrets never leave for Zulip in what a bridged agent sends."""

import pytest

from zulipchat_mcp.tools import messaging
from zulipchat_mcp.utils.redaction import redact, secret_values


def test_secret_values_come_from_credential_named_variables_only():
    values = secret_values(
        {
            "DEPLOY_TOKEN": "deploy-value-0123456789",
            "KEYBOARD_LAYOUT": "us-international",
        },
        {"DB_PASSWORD": "short", "HOME": "/home/someone/projects"},
        extra=["BotKey0123456789BotKey0123456789", None],
    )
    assert values == ["BotKey0123456789BotKey0123456789", "deploy-value-0123456789"]


def test_redact_replaces_known_values_and_unmistakable_shapes():
    text = (
        "token deploy-value-0123456789 and ghp_" + "a" * 36 + "\n"
        "key = OwnerKey0123456789OwnerKey012345\n"
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----\n"
        "the build passed"
    )
    cleaned = redact(text, ["deploy-value-0123456789"])
    for leaked in ("deploy-value", "ghp_", "OwnerKey", "PRIVATE KEY"):
        assert leaked not in cleaned
    assert cleaned.endswith("the build passed") and cleaned.count("[redacted]") == 4


@pytest.mark.asyncio
async def test_a_bridged_agents_own_messages_are_redacted(monkeypatch):
    from unittest.mock import MagicMock

    sent = []
    client = MagicMock(identity="user", base_url="https://example.com")
    client.send_message.side_effect = lambda kind, to, content, topic: (
        sent.append(content) or {"result": "success", "id": len(sent)}
    )
    client.edit_message.side_effect = lambda **kwargs: (
        sent.append(kwargs["content"]) or {"result": "success"}
    )
    config = MagicMock()
    config.get_zulip_client_config.return_value = {
        "api_key": "BotKey0123456789BotKey0123456789"
    }
    monkeypatch.setattr(messaging, "get_client", lambda: client)
    monkeypatch.setattr(messaging, "get_config_manager", lambda: config)
    monkeypatch.setattr(messaging, "_agent_secrets", None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-value-0123456789")
    leaky = "here: anthropic-value-0123456789 / BotKey0123456789BotKey0123456789"

    # An ordinary host: the person at the keyboard decides what is sent.
    monkeypatch.delenv("ZULIPCHAT_AGENT_STATE", raising=False)
    await messaging.send_message("stream", "dev", leaky, "t")
    assert sent[-1] == leaky

    monkeypatch.setenv("ZULIPCHAT_AGENT_STATE", "/tmp/state.sqlite3")
    await messaging.send_message("stream", "dev", leaky, "t", allow_duplicate=True)
    assert sent[-1] == "here: [redacted] / [redacted]"
    await messaging.edit_message(5, content=leaky)
    assert sent[-1] == "here: [redacted] / [redacted]"
