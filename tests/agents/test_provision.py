"""Agent bot provisioning against mocked Zulip clients only."""

import stat
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.agents.provision import (
    ProvisionError,
    bot_owner_id,
    create_agent_bot,
    write_bot_zuliprc,
)


def fake_client(responses):
    """A client whose call_endpoint answers from ``{(method, path): response}``."""
    client = MagicMock()
    client.call_endpoint.side_effect = lambda path, method, request: responses[
        (method, path)
    ]
    return client


def owner(**profile):
    return {"result": "success", "user_id": 7, "is_bot": False, "role": 400, **profile}


def test_create_agent_bot_posts_a_generic_bot_and_looks_up_its_email():
    client = fake_client(
        {
            ("GET", "users/me"): owner(),
            ("POST", "bots"): {"result": "success", "user_id": 42, "api_key": "k"},
            ("GET", "users/42"): {
                "result": "success",
                "user": {"email": "agent-bot@zulip.example.com"},
            },
        }
    )
    bot = create_agent_bot(client, "Agent", "agent")
    assert bot == {
        "user_id": 42,
        "email": "agent-bot@zulip.example.com",
        "api_key": "k",
        "full_name": "Agent",
    }
    client.call_endpoint.assert_any_call(
        "bots",
        method="POST",
        request={"full_name": "Agent", "short_name": "agent", "bot_type": 1},
    )


def test_create_agent_bot_unwraps_a_client_wrapper():
    inner = fake_client(
        {
            ("GET", "users/me"): owner(),
            ("POST", "bots"): {
                "result": "success",
                "user_id": 42,
                "api_key": "k",
                "email": "agent-bot@zulip.example.com",
            },
        }
    )
    wrapper = SimpleNamespace(client=inner)
    assert create_agent_bot(wrapper, "Agent", "agent")["email"] == (
        "agent-bot@zulip.example.com"
    )
    assert inner.call_endpoint.call_count == 2


@pytest.mark.parametrize(
    ("profile", "reason"),
    [({"is_bot": True}, "human API key"), ({"role": 600}, "guest")],
)
def test_create_agent_bot_requires_a_human_member(profile, reason):
    client = fake_client({("GET", "users/me"): owner(**profile)})
    with pytest.raises(ProvisionError, match=reason):
        create_agent_bot(client, "Agent", "agent")
    assert client.call_endpoint.call_count == 1


def test_create_agent_bot_surfaces_zulip_errors():
    client = fake_client(
        {
            ("GET", "users/me"): owner(),
            ("POST", "bots"): {"result": "error", "msg": "Name is already in use."},
        }
    )
    with pytest.raises(ProvisionError, match="already in use"):
        create_agent_bot(client, "Agent", "agent")


def test_create_agent_bot_rejects_incomplete_success():
    client = fake_client(
        {("GET", "users/me"): owner(), ("POST", "bots"): {"result": "success"}}
    )
    with pytest.raises(ProvisionError, match="no user_id"):
        create_agent_bot(client, "Agent", "agent")


def test_write_bot_zuliprc_is_private_and_never_overwrites(tmp_path):
    target = tmp_path / "agents" / "agent" / "zuliprc"
    written = write_bot_zuliprc(target, "b@x.com", "key1", "https://x.com")
    assert written == target
    assert target.read_text() == (
        "[api]\nemail=b@x.com\nkey=key1\nsite=https://x.com\n"
    )
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(target.parent.parent.stat().st_mode) == 0o700
    with pytest.raises(FileExistsError):
        write_bot_zuliprc(target, "b@x.com", "key2", "https://x.com")
    assert "key1" in target.read_text()


def test_write_bot_zuliprc_rejects_multiline_values(tmp_path):
    with pytest.raises(ValueError):
        write_bot_zuliprc(tmp_path / "rc", "b@x.com", "k\nsite=evil", "https://x")
    assert not (tmp_path / "rc").exists()


def test_bot_owner_id_reads_the_bot_profile():
    client = fake_client(
        {
            ("GET", "users/me"): {"result": "success", "user_id": 42},
            ("GET", "users/42"): {"result": "success", "user": {"bot_owner_id": 7}},
        }
    )
    assert bot_owner_id(client) == 7


def test_bot_owner_id_is_none_without_an_owner():
    client = fake_client(
        {
            ("GET", "users/me"): {"result": "success", "user_id": 42},
            ("GET", "users/42"): {"result": "success", "user": {"is_bot": True}},
        }
    )
    assert bot_owner_id(client) is None
