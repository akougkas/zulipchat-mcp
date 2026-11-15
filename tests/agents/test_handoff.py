"""ask_owner from inside a bridged agent; teleport_chat to an agent bot."""

import threading
from unittest.mock import MagicMock

import pytest

from zulipchat_mcp.agents.store import BridgeStore
from zulipchat_mcp.tools import handoff


@pytest.fixture
def bridged(tmp_path, monkeypatch):
    store = BridgeStore(tmp_path / "clio.sqlite3")
    store.bind(
        "ch:5:release", "s1", "/w", {"type": "stream", "to": 5, "topic": "Release"}
    )
    client = MagicMock()
    client.send_message.return_value = {"result": "success", "id": 9}
    monkeypatch.setattr(handoff, "get_client", lambda: client)
    monkeypatch.setenv("ZULIPCHAT_AGENT_STATE", str(store.path))
    monkeypatch.setenv("ZULIPCHAT_AGENT_CONVERSATION", "ch:5:release")
    return store, client


@pytest.mark.asyncio
async def test_question_is_posted_in_place_and_answered_by_the_bridge(bridged):
    store, client = bridged

    def owner_answers():
        while not (q := store.open_question("ch:5:release")):
            pass
        store.answer(q["id"], "main, please")

    threading.Thread(target=owner_answers, daemon=True).start()
    result = await handoff.ask_owner("Which branch?", wait_seconds=10)
    assert result == {
        "status": "success",
        "question_id": result["question_id"],
        "answer": "main, please",
    }
    args = client.send_message.call_args.args
    assert args[0:2] == ("stream", 5) and args[3] == "Release"
    assert "Which branch?" in args[2]


@pytest.mark.asyncio
async def test_timeout_keeps_the_question_open_for_a_later_wait(bridged):
    store, client = bridged
    pending = await handoff.ask_owner("Deploy?", wait_seconds=0)
    assert pending["status"] == "pending"
    store.answer(pending["question_id"], "yes")
    again = await handoff.ask_owner(question_id=pending["question_id"], wait_seconds=0)
    assert again["answer"] == "yes"
    assert client.send_message.call_count == 1


@pytest.mark.asyncio
async def test_questions_cannot_cross_conversations(bridged, monkeypatch):
    store, _ = bridged
    other = store.ask("dm:7", "question", "secret?", [], 30)
    result = await handoff.ask_owner(question_id=other, wait_seconds=0)
    assert result["error_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_ask_owner_outside_the_bridge_is_refused(monkeypatch):
    monkeypatch.delenv("ZULIPCHAT_AGENT_STATE", raising=False)
    result = await handoff.ask_owner("hi")
    assert result["error_code"] == "NOT_BRIDGED"


def test_ask_owner_is_registered_only_inside_the_bridge(monkeypatch):
    from tests.tools.test_tool_tiers import ToolCountingMCP
    from zulipchat_mcp.tools import register_core_tools

    monkeypatch.delenv("ZULIPCHAT_AGENT_STATE", raising=False)
    plain = ToolCountingMCP()
    register_core_tools(plain)
    monkeypatch.setenv("ZULIPCHAT_AGENT_STATE", "/tmp/x")
    bridged = ToolCountingMCP()
    register_core_tools(bridged)
    assert bridged.tool_names - plain.tool_names == {"ask_owner"}


@pytest.fixture
def agent_bot(tmp_path, monkeypatch):
    """An agent bot named clio backed by the fake ACP agent and a mocked Zulip."""
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    from zulipchat_mcp.agents import teleport as teleport_module

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    work = tmp_path / "work"
    work.mkdir()
    agents = tmp_path / "config" / "zulipchat-mcp" / "agents"
    agents.mkdir(parents=True)
    fake = [sys.executable, str(Path(__file__).with_name("fake_acp_agent.py"))]
    (agents / "clio.toml").write_text(
        f'zuliprc = "{tmp_path / "bot.zuliprc"}"\n'
        f"command = {fake!r}\n".replace("'", '"') + f'cwd = "{work}"\n'
    )
    bot = MagicMock()
    bot.send_message.return_value = {"result": "success", "id": 77}
    monkeypatch.setattr(teleport_module, "ConfigManager", lambda **_: None)
    monkeypatch.setattr(teleport_module, "ZulipClientWrapper", lambda _: bot)
    monkeypatch.setattr(teleport_module, "bot_owner_id", lambda _: 7)
    return SimpleNamespace(work=work, bot=bot)


def test_cli_teleport_resumes_the_newest_session_in_the_workspace(agent_bot, capsys):
    from zulipchat_mcp.agents.cli import main
    from zulipchat_mcp.agents.config import load_agents

    assert main(["teleport", "clio", "--cwd", str(agent_bot.work)]) == 0
    (config,) = load_agents()
    bound = BridgeStore(config.state_path).conversation("dm:7")
    assert bound["session_id"] == "live" and bound["cwd"] == str(agent_bot.work)
    assert bound["destination"] == {"type": "private", "to": [7]}
    kind, to, text = agent_bot.bot.send_message.call_args.args
    assert (kind, to) == ("private", [7])
    assert "`live` (Refactor)" in text
    assert "resume live (Refactor)" in capsys.readouterr().out


def test_cli_teleport_refuses_a_workspace_outside_allowed_dirs(
    agent_bot, tmp_path, capsys
):
    from zulipchat_mcp.agents.cli import main

    assert main(["teleport", "clio", "--session", "s9", "--cwd", str(tmp_path)]) == 1
    assert "not in clio's allowed_dirs" in capsys.readouterr().err
    agent_bot.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_teleport_chat_binds_the_given_session(agent_bot, monkeypatch):
    from zulipchat_mcp.agents.config import load_agents

    monkeypatch.setattr(handoff, "local_access_allowed", lambda: True)
    result = await handoff.teleport_chat("clio", "Over to you", session_id="s42")
    assert result["status"] == "success" and result["resumes_session"] == "s42"
    (config,) = load_agents()
    assert BridgeStore(config.state_path).conversation("dm:7")["session_id"] == "s42"
