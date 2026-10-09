"""Owner-only mention authorization: parsing, CLI/env plumbing and reporting."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp import server
from src.zulipchat_mcp.tools.system import server_info
from zulipchat_mcp.config import ConfigManager, MentionAllow, parse_mention_allow

OWNER = "owner@example.com"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_policy_admits_only_the_owner_case_insensitively(value):
    policy = parse_mention_allow(value)
    assert policy.mode == "owner_only" and policy == MentionAllow()
    assert policy.allows(7, "Owner@Example.COM", OWNER)
    assert not policy.allows(7, "other@example.com", OWNER)
    assert not policy.allows(7, None, OWNER)
    assert not policy.allows(7, "", "")


def test_explicit_list_extends_the_owner_default():
    policy = parse_mention_allow(" Pat@Example.com , 42,pat@example.com ")
    assert policy.mode == "allowlist"
    assert policy.emails == {"pat@example.com"} and policy.user_ids == {42}
    assert policy.allows(1, "PAT@example.com", OWNER)
    assert policy.allows(42, "other@example.com", OWNER)
    assert not policy.allows(43, "other@example.com", OWNER)
    assert policy.allows(1, OWNER, OWNER)


def test_numeric_ids_match_integers_only():
    policy = parse_mention_allow("42")
    assert policy.allows(42, "x@example.com", OWNER)
    assert not policy.allows("42", "x@example.com", OWNER)
    assert not policy.allows(True, "x@example.com", OWNER)


def test_everyone_admits_all_senders():
    policy = parse_mention_allow("Everyone")
    assert policy.mode == "everyone" and policy.allows(None, None, OWNER)


@pytest.mark.parametrize(
    "value",
    [
        "everyone,pat@example.com",
        "pat@example.com,,42",
        "pat@example.com,",
        "0",
        "-5",
        "4.2",
        "Pat Example",
        "pat@",
        "@example.com",
        "a@b@c",
        "owner",
        "9" * 300,
    ],
)
def test_bad_entries_are_rejected(value):
    with pytest.raises(ValueError):
        parse_mention_allow(value)


def test_summary_reports_policy_without_secrets():
    assert MentionAllow().summary(OWNER) == {
        "mode": "owner_only",
        "owner_email": OWNER,
        "emails": [],
        "user_ids": [],
    }
    listed = parse_mention_allow("b@example.com,a@example.com,9,3").summary(OWNER)
    assert listed == {
        "mode": "allowlist",
        "owner_email": None,
        "emails": ["a@example.com", "b@example.com"],
        "user_ids": [3, 9],
    }


def test_cli_value_overrides_the_environment_and_blank_means_unset(monkeypatch):
    monkeypatch.setattr(ConfigManager, "_find_default_config", lambda _: None)
    monkeypatch.delenv("ZULIPCHAT_MENTION_ALLOW", raising=False)
    assert ConfigManager().mention_allow_policy().mode == "owner_only"
    monkeypatch.setenv("ZULIPCHAT_MENTION_ALLOW", "env@example.com")
    assert ConfigManager().mention_allow_policy().emails == {"env@example.com"}
    cli = ConfigManager(mention_allow="everyone")
    assert cli.mention_allow_policy().mode == "everyone"
    monkeypatch.setenv("ZULIPCHAT_MENTION_ALLOW", "  ")
    assert ConfigManager().mention_allow_policy().mode == "owner_only"


@pytest.mark.parametrize("source", ["flag", "environment"])
def test_invalid_policy_fails_startup_before_any_initialization(monkeypatch, source):
    monkeypatch.delenv("ZULIPCHAT_MENTION_ALLOW", raising=False)
    argv = ["zulipchat-mcp"]
    if source == "flag":
        argv += ["--mention-allow", "not an entry"]
    else:
        monkeypatch.setenv("ZULIPCHAT_MENTION_ALLOW", "not an entry")
    monkeypatch.setattr(sys, "argv", argv)
    with patch.object(server, "init_config_manager") as init:
        with pytest.raises(SystemExit) as exc:
            server.main()
    assert exc.value.code == 2
    init.assert_not_called()


@pytest.mark.parametrize(
    "argv,env,expected",
    [
        (["--mention-allow", "a@example.com,7"], None, "a@example.com,7"),
        ([], "everyone", "everyone"),
        (["--mention-allow", "7"], "everyone", "7"),
        ([], None, None),
    ],
)
def test_policy_reaches_the_config_manager(monkeypatch, argv, env, expected):
    monkeypatch.delenv("ZULIPCHAT_MENTION_ALLOW", raising=False)
    if env is not None:
        monkeypatch.setenv("ZULIPCHAT_MENTION_ALLOW", env)
    monkeypatch.setattr(sys, "argv", ["zulipchat-mcp", *argv])
    cfg = MagicMock()
    cfg.validate_config.return_value = False
    with (
        patch.object(server, "setup_structured_logging"),
        patch.object(server, "get_logger", return_value=MagicMock()),
        patch.object(server, "init_config_manager", return_value=cfg) as init,
    ):
        with pytest.raises(SystemExit):
            server.main()
    assert init.call_args.kwargs["mention_allow"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "allow,expected",
    [
        (None, {"mode": "owner_only", "owner_email": OWNER, "emails": []}),
        ("everyone", {"mode": "everyone", "owner_email": None, "emails": []}),
        (
            "B@example.com,5",
            {"mode": "allowlist", "owner_email": None, "emails": ["b@example.com"]},
        ),
    ],
)
async def test_server_info_reports_effective_policy(monkeypatch, allow, expected):
    for name in (
        "ZULIP_CONFIG_FILE",
        "ZULIP_BOT_CONFIG_FILE",
        "ZULIPCHAT_MENTION_ALLOW",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ConfigManager, "_find_default_config", lambda _: None)
    monkeypatch.setenv("ZULIP_EMAIL", OWNER)
    monkeypatch.setenv("ZULIP_API_KEY", "secret-key")
    monkeypatch.setenv("ZULIP_SITE", "https://zulip.example")
    manager = ConfigManager(mention_allow=allow)
    with patch(
        "src.zulipchat_mcp.tools.system.get_config_manager", return_value=manager
    ):
        result = await server_info()
    report = result["mention_authorization"]
    assert {key: report[key] for key in expected} == expected
    assert report["user_ids"] == ([5] if allow and "5" in allow else [])
    assert "secret-key" not in str(result)


@pytest.mark.asyncio
async def test_server_info_surfaces_an_invalid_policy(monkeypatch):
    monkeypatch.setattr(ConfigManager, "_find_default_config", lambda _: None)
    monkeypatch.setenv("ZULIP_EMAIL", OWNER)
    monkeypatch.setenv("ZULIP_API_KEY", "secret-key")
    monkeypatch.setenv("ZULIP_SITE", "https://zulip.example")
    manager = ConfigManager(mention_allow="bad entry")
    with patch(
        "src.zulipchat_mcp.tools.system.get_config_manager", return_value=manager
    ):
        result = await server_info()
    assert result["mention_authorization"]["mode"] == "invalid"
