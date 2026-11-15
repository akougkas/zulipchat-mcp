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
