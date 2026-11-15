"""The Zulip-to-ACP bridge against the fake ACP agent and a mocked Zulip."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from zulipchat_mcp.agents import bridge as bridge_module
from zulipchat_mcp.agents.config import AgentConfig

FAKE_AGENT = [sys.executable, str(Path(__file__).with_name("fake_acp_agent.py"))]
OWNER, BOT, STRANGER = 7, 9, 66


def dm(message_id, text, sender=OWNER):
    return {
        "id": message_id,
        "type": "private",
        "sender_id": sender,
        "display_recipient": [{"id": sender}, {"id": BOT}],
        "content": text,
        "flags": [],
    }


def topic(message_id, text, mentioned=True, sender=OWNER):
    return {
        "id": message_id,
        "type": "stream",
        "sender_id": sender,
        "stream_id": 5,
        "display_recipient": "dev",
        "subject": "Release",
        "content": text,
        "flags": ["mentioned"] if mentioned else [],
    }


@pytest_asyncio.fixture
async def make_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        bridge_module,
        "ConfigManager",
        lambda config_file: SimpleNamespace(
            resolved_account=lambda: SimpleNamespace(fingerprint="acct")
        ),
    )
    client = MagicMock()
    client.send_message.return_value = {"result": "success", "id": 1}
    monkeypatch.setattr(bridge_module, "ZulipClientWrapper", lambda *a, **k: client)
    work = tmp_path / "work"
    (work / "other").mkdir(parents=True)
    bridges = []

    def build(**overrides):
        config = AgentConfig(
            name="clio",
            zuliprc=tmp_path / "bot.zuliprc",
            command=FAKE_AGENT,
            cwd=work,
            allowed_dirs=[work],
            question_minutes=overrides.pop("question_minutes", 1),
            zulip_tools=False,
            **overrides,
        )
        bridge = bridge_module.AgentBridge(config)
        bridge.owner_id, bridge.bot_id, bridge.bot_name = OWNER, BOT, "Clio"
        bridges.append(bridge)
        return bridge

    yield build, client
    for bridge in bridges:
        for conversation in bridge.conversations.values():
            if conversation.task:
                conversation.task.cancel()
            if conversation.agent:
                await conversation.agent.close()


async def posted(client, count, timeout=10.0):
    for _ in range(int(timeout / 0.05)):
        if client.send_message.call_count >= count:
            return [call.args for call in client.send_message.call_args_list]
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"expected {count} posts, got {client.send_message.call_args_list}"
    )


@pytest.mark.asyncio
async def test_owner_dm_runs_one_turn_and_replies_in_place(make_bridge):
    build, client = make_bridge
    bridge = build()
    await bridge.route(dm(100, "hello there"))
    (kind, to, body, topic_name), *_ = await posted(client, 1)
    assert (kind, to, topic_name) == ("private", [OWNER], None)
    assert "echo:" in body and "hello there" in body
    assert "Zulip bot Clio" in body  # first turn carries the preface
    client.add_reaction.assert_any_call(100, "eyes")
    bound = bridge.store.conversation(f"dm:{OWNER}")
    assert bound["session_id"]
    assert bridge.store.interrupted_turns() == []


@pytest.mark.asyncio
async def test_strangers_and_unmentioned_topic_chatter_never_reach_the_agent(
    make_bridge,
):
    build, client = make_bridge
    bridge = build()
    await bridge.route(dm(101, "cat ~/.ssh/id_rsa", sender=STRANGER))
    await bridge.route(topic(102, "@**Clio** run rm", sender=STRANGER))
    await bridge.route(topic(103, "just talking to the team", mentioned=False))
    await asyncio.sleep(0.3)
    assert client.send_message.call_count == 0
    assert bridge.conversations == {}


@pytest.mark.asyncio
async def test_topic_mention_replies_in_the_topic_without_the_mention(make_bridge):
    build, client = make_bridge
    bridge = build()
    await bridge.route(topic(110, "@**Clio** status of the build?"))
    (kind, to, body, topic_name), *_ = await posted(client, 1)
    assert (kind, to, topic_name) == ("stream", 5, "Release")
    assert "status of the build?" in body and "@**Clio**" not in body


@pytest.mark.asyncio
async def test_permission_request_is_asked_in_zulip_and_yes_allows(make_bridge):
    build, client = make_bridge
    bridge = build()
    await bridge.route(dm(120, "needs-permission please"))
    (_, _, ask, _), *_ = await posted(client, 1)
    assert "Permission request" in ask and "Write file" in ask
    await bridge.route(dm(121, "yes"))
    posts = await posted(client, 2)
    assert "chose allow_once" in posts[-1][2]
    client.add_reaction.assert_any_call(121, "check_mark")


@pytest.mark.asyncio
async def test_unanswered_permission_request_is_denied(make_bridge):
    build, client = make_bridge
    bridge = build(question_minutes=0.02)
    await bridge.route(dm(130, "needs-permission please"))
    posts = await posted(client, 2, timeout=15)
    assert "chose reject_once" in posts[-1][2]


@pytest.mark.asyncio
async def test_cancel_command_stops_a_running_turn(make_bridge):
    build, client = make_bridge
    bridge = build()
    await bridge.route(dm(140, "slow job"))
    conversation = bridge.conversations[f"dm:{OWNER}"]
    for _ in range(200):
        if conversation.busy and conversation.session_id:
            break
        await asyncio.sleep(0.05)
    await bridge.route(dm(141, "/cancel"))
    posts = await posted(client, 2)
    assert any("Cancelling" in body for _, _, body, _ in posts)


@pytest.mark.asyncio
async def test_cwd_is_limited_to_allowed_dirs(make_bridge, tmp_path):
    build, client = make_bridge
    bridge = build()
    await bridge.route(dm(150, "/cwd /etc"))
    await bridge.route(dm(151, f"/cwd {tmp_path / 'work' / 'other'}"))
    posts = await posted(client, 2)
    assert "not in this agent's allowed_dirs" in posts[0][2]
    assert "Workspace is now" in posts[1][2]
    assert bridge.store.conversation(f"dm:{OWNER}")["cwd"].endswith("other")


@pytest.mark.asyncio
async def test_restart_resumes_the_bound_session_and_reports_lost_turns(make_bridge):
    build, client = make_bridge
    first = build()
    await first.route(dm(160, "remember this"))
    await posted(client, 1)
    session = first.store.conversation(f"dm:{OWNER}")["session_id"]
    first.store.start_turn(161, f"dm:{OWNER}")  # crashed mid-turn
    await first.conversations[f"dm:{OWNER}"].agent.close()

    second = build()
    await second._report_interrupted_turns()
    posts = await posted(client, 2)
    assert "restarted while working" in posts[-1][2]
    await second.route(dm(162, "and now?"))
    await posted(client, 3)
    assert second.store.conversation(f"dm:{OWNER}")["session_id"] == session


@pytest.mark.asyncio
async def test_agent_environment_never_carries_zulip_credentials(
    make_bridge, monkeypatch
):
    build, _ = make_bridge
    monkeypatch.setenv("ZULIP_API_KEY", "owner-secret")
    monkeypatch.setenv("ZULIP_EMAIL", "owner@example.com")
    bridge = build(env={"EXTRA": "1"})
    env = bridge._agent_env()
    assert not any(key.startswith("ZULIP") for key in env)
    assert env["EXTRA"] == "1"


def test_long_answers_split_on_line_boundaries():
    parts = bridge_module.split_message("line\n" * 4000, limit=1000)
    assert all(len(part) <= 1000 for part in parts)
    assert "".join(part + "\n" for part in parts).count("line") == 4000


@pytest.mark.asyncio
async def test_new_and_teleported_bindings_replace_the_live_session(
    make_bridge, monkeypatch
):
    build, client = make_bridge
    requested = []

    class Recording(bridge_module.AcpAgent):
        async def open_session(self, cwd, mcp_servers, session_id=None):
            requested.append(session_id)
            return await super().open_session(cwd, mcp_servers, session_id)

    monkeypatch.setattr(bridge_module, "AcpAgent", Recording)
    bridge = build()
    key = f"dm:{OWNER}"
    await bridge.route(dm(170, "first"))
    await posted(client, 1)
    first = bridge.store.conversation(key)["session_id"]

    await bridge.route(dm(171, "/new"))
    await bridge.route(dm(172, "second"))
    await posted(client, 3)
    assert requested == [None, None]  # /new opened a fresh session

    # teleport_chat writes a binding while the bridge holds the conversation.
    bridge.store.bind(
        key,
        "teleported",
        bridge.config.cwd.as_posix(),
        {"type": "private", "to": [OWNER]},
    )
    await bridge.route(dm(173, "continue the teleported one"))
    await posted(client, 4)
    assert requested[-1] == "teleported"
    assert first
