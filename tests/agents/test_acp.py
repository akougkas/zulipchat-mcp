"""ACP client contracts exercised against a stdlib fake agent subprocess."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from zulipchat_mcp.agents import acp
from zulipchat_mcp.agents.acp import AcpAgent, AcpError

FAKE = str(Path(__file__).with_name("fake_acp_agent.py"))


@pytest.fixture
def method_log(tmp_path):
    return tmp_path / "methods.log"


@pytest.fixture
async def make_agent(tmp_path, method_log):
    agents = []

    async def make(caps="resume,load,close", **kwargs):
        env = {**os.environ, "FAKE_ACP_CAPS": caps, "FAKE_ACP_LOG": str(method_log)}
        env.update(kwargs.pop("extra_env", {}))
        agent = AcpAgent([sys.executable, FAKE], env=env, request_timeout=10, **kwargs)
        agents.append(agent)
        return agent

    yield make
    for agent in agents:
        await agent.close()


def methods(log):
    return log.read_text().split() if log.exists() else []


async def test_start_skips_noise_and_returns_capabilities(make_agent, tmp_path):
    agent = await make_agent()
    caps = await agent.start()
    assert agent.alive
    assert caps == {
        "loadSession": True,
        "sessionCapabilities": {"close": {}, "resume": {}},
    }
    assert agent.capabilities is caps
    assert await agent.open_session(str(tmp_path), []) == "sess-1"


async def test_oversize_stdout_line_is_skipped(make_agent, monkeypatch):
    monkeypatch.setattr(acp, "MAX_LINE_BYTES", 64 * 1024)
    agent = await make_agent(extra_env={"FAKE_ACP_NOISE": "1"})
    assert (await agent.start())["loadSession"] is True


async def test_resume_is_preferred_for_known_session(make_agent, method_log, tmp_path):
    agent = await make_agent()
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    assert await agent.open_session(str(tmp_path), [], session_id) == session_id
    assert methods(method_log)[-1] == "session/resume"


async def test_load_replay_never_reaches_the_next_turn(
    make_agent, method_log, tmp_path
):
    agent = await make_agent(caps="load")
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    await agent.prompt(session_id, "first")
    assert await agent.open_session(str(tmp_path), [], session_id) == session_id
    assert methods(method_log)[-1] == "session/load"
    result = await agent.prompt(session_id, "second")
    assert result.text == "echo: second"


async def test_failed_resume_falls_back_to_new(make_agent, method_log, tmp_path):
    agent = await make_agent()
    await agent.start()
    assert await agent.open_session(str(tmp_path), [], "gone") == "sess-1"
    assert methods(method_log)[-2:] == ["session/resume", "session/new"]


async def test_without_resume_or_load_a_new_session_opens(
    make_agent, method_log, tmp_path
):
    agent = await make_agent(caps="")
    await agent.start()
    assert await agent.open_session(str(tmp_path), [], "old") == "sess-1"
    assert methods(method_log) == ["initialize", "session/new"]


async def test_auth_required_is_reported(make_agent, tmp_path):
    agent = await make_agent(extra_env={"FAKE_ACP_AUTH": "1"})
    await agent.start()
    with pytest.raises(AcpError) as excinfo:
        await agent.open_session(str(tmp_path), [])
    assert excinfo.value.code == "auth_required"
    assert excinfo.value.data["rpc_code"] == -32000


async def test_prompt_aggregates_text_and_tool_calls(make_agent, tmp_path):
    agent = await make_agent()
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    updates = []
    result = await agent.prompt(session_id, "hello", on_update=updates.append)
    assert result.stop_reason == "end_turn"
    assert result.text == "echo: hello"
    assert result.error is None
    assert result.tool_calls == [
        {"id": "call-1", "title": "Read file", "kind": "read", "status": "completed"}
    ]
    assert [u["sessionUpdate"] for u in updates] == [
        "agent_message_chunk",
        "agent_message_chunk",
        "tool_call",
        "tool_call_update",
    ]


async def test_permission_round_trip(make_agent, tmp_path):
    seen = []

    async def allow(session_id, params):
        seen.append((session_id, [o["optionId"] for o in params["options"]]))
        return {"outcome": {"outcome": "selected", "optionId": "allow_once"}}

    agent = await make_agent(on_permission=allow)
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    result = await agent.prompt(session_id, "needs-permission")
    assert result.text.endswith(" chose allow_once")
    assert seen == [(session_id, ["allow_once", "reject_once"])]


async def test_permission_without_handler_rejects_once(make_agent, tmp_path):
    agent = await make_agent()
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    result = await agent.prompt(session_id, "needs-permission")
    assert result.text.endswith(" chose reject_once")


async def test_client_methods_other_than_permission_are_refused(make_agent, tmp_path):
    agent = await make_agent()
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    result = await agent.prompt(session_id, "fs-read")
    assert result.text.endswith(" error -32601")


async def test_cancel_ends_a_slow_turn(make_agent, tmp_path):
    agent = await make_agent()
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    turn = asyncio.create_task(agent.prompt(session_id, "slow"))
    await asyncio.sleep(0.2)
    with pytest.raises(AcpError) as excinfo:
        await agent.prompt(session_id, "again")
    assert excinfo.value.code == "busy"
    await agent.cancel(session_id)
    result = await asyncio.wait_for(turn, 10)
    assert result.stop_reason == "cancelled"
    assert result.text == "echo: slow"


async def test_cancel_resolves_pending_permission_as_cancelled(make_agent, tmp_path):
    asked = asyncio.Event()
    handler_cancelled = asyncio.Event()

    async def wait_forever(session_id, params):
        asked.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            handler_cancelled.set()
            raise
        return {}

    agent = await make_agent(on_permission=wait_forever)
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    turn = asyncio.create_task(agent.prompt(session_id, "needs-permission"))
    await asyncio.wait_for(asked.wait(), 10)
    await agent.cancel(session_id)
    result = await asyncio.wait_for(turn, 10)
    assert result.stop_reason == "cancelled"
    assert handler_cancelled.is_set()


async def test_agent_death_fails_pending_and_future_calls(make_agent, tmp_path):
    agent = await make_agent()
    await agent.start()
    session_id = await agent.open_session(str(tmp_path), [])
    result = await asyncio.wait_for(agent.prompt(session_id, "die-now"), 10)
    assert result.stop_reason == "error"
    assert "agent_exited" in result.error
    assert result.text == "echo: die-now"
    assert not agent.alive
    with pytest.raises(AcpError) as excinfo:
        await agent.open_session(str(tmp_path), [])
    assert excinfo.value.code == "agent_exited"
    assert excinfo.value.data["returncode"] == 3


async def test_close_closes_advertised_sessions_and_stops_agent(
    make_agent, method_log, tmp_path
):
    agent = await make_agent()
    await agent.start()
    await agent.open_session(str(tmp_path), [])
    await agent.close()
    assert methods(method_log)[-1] == "session/close"
    assert not agent.alive


async def test_close_skips_session_close_when_not_advertised(
    make_agent, method_log, tmp_path
):
    agent = await make_agent(caps="load")
    await agent.start()
    await agent.open_session(str(tmp_path), [])
    await agent.close()
    assert "session/close" not in methods(method_log)
    assert not agent.alive


async def test_missing_binary_is_a_spawn_failure():
    with pytest.raises(AcpError) as excinfo:
        await AcpAgent(["/nonexistent/acp-agent"]).start()
    assert excinfo.value.code == "spawn_failed"
