"""Agent declarations and the durable bridge store."""

import time

import pytest

from zulipchat_mcp.agents.config import load_agent
from zulipchat_mcp.agents.store import BridgeStore


def write(tmp_path, body, name="clio"):
    path = tmp_path / f"{name}.toml"
    path.write_text(body)
    return path


def test_agent_file_resolves_paths_and_defaults(tmp_path):
    work = tmp_path / "work"
    (work / "repo").mkdir(parents=True)
    agent = load_agent(
        write(
            tmp_path,
            f'zuliprc = "{tmp_path}/bot.zuliprc"\ncommand = ["clio-coder", "acp"]\n'
            f'cwd = "{work}"\nallow = [42]\n',
        )
    )
    assert agent.name == "clio" and agent.allow == {42}
    assert agent.allowed_dirs == [work]
    assert agent.permits_dir(work / "repo")
    assert not agent.permits_dir(tmp_path)


@pytest.mark.parametrize(
    "body, reason",
    [
        ('command = ["x"]\n', "zuliprc"),
        ('zuliprc = "z"\ncommand = []\n', "command"),
        ('zuliprc = "z"\ncommand = ["x"]\nallow = ["bob@x.com"]\n', "allow"),
        ('zuliprc = "z"\ncommand = ["x"]\nsudo = true\n', "unknown keys"),
        (
            'zuliprc = "z"\ncommand = ["x"]\ncwd = "/"\nallowed_dirs = ["/tmp/x"]\n',
            "cwd",
        ),
    ],
)
def test_invalid_agent_files_are_rejected_with_a_reason(tmp_path, body, reason):
    with pytest.raises(ValueError, match=reason):
        load_agent(write(tmp_path, body))


def test_agent_names_are_constrained(tmp_path):
    with pytest.raises(ValueError, match="lowercase"):
        load_agent(write(tmp_path, 'zuliprc = "z"\ncommand = ["x"]\n', name="Bad Name"))


def test_store_binds_sessions_and_journals_turns(tmp_path):
    store = BridgeStore(tmp_path / "s.sqlite3")
    store.bind("dm:7", "sess-1", "/w", {"type": "private", "to": [7]})
    assert store.conversation("dm:7")["destination"] == {"type": "private", "to": [7]}
    store.start_turn(10, "dm:7")
    store.start_turn(11, "dm:7")
    store.finish_turn(10)
    assert [t["message_id"] for t in store.interrupted_turns()] == [11]
    assert (tmp_path / "s.sqlite3").stat().st_mode & 0o777 == 0o600


def test_questions_answer_once_oldest_first_and_expire(tmp_path):
    store = BridgeStore(tmp_path / "s.sqlite3")
    first = store.ask("dm:7", "permission", "rm -rf build", ["a", "r"], 30)
    second = store.ask("dm:7", "question", "which branch?", [], 30)
    assert store.open_question("dm:7")["id"] == first
    assert store.open_question("ch:1:x") is None
    assert store.answer(first, "allow")
    assert not store.answer(first, "deny")
    assert store.open_question("dm:7")["id"] == second
    expired = store.ask("dm:8", "question", "late?", [], minutes=-1)
    assert store.open_question("dm:8") is None
    assert not store.answer(expired, "now")
    assert store.question(first)["answer"] == "allow"
    assert time.time() > store.question(expired)["deadline"]
