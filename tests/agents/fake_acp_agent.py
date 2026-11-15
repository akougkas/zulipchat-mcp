"""Minimal stdlib ACP agent used by the ACP client tests.

Environment knobs:
  FAKE_ACP_CAPS   comma list of "resume", "load", "close", "list" (default all)
  FAKE_ACP_LOG    file that receives one line per received method
  FAKE_ACP_AUTH   when set, session/new fails with -32000
  FAKE_ACP_NOISE  when set, initialize is preceded by an oversize stdout line
"""

import json
import os
import sys
import threading

CAPS = set(os.environ.get("FAKE_ACP_CAPS", "resume,load,close,list").split(","))
LOG = os.environ.get("FAKE_ACP_LOG")

sessions = {}
client_meta = {}  # clientCapabilities._meta from initialize
waiting = {}  # outgoing request id or session id -> pending prompt
next_id = 0


write_lock = threading.Lock()


def send(message):
    with write_lock:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        sys.stdout.flush()


def update(session_id, body):
    send(
        {
            "method": "session/update",
            "params": {"sessionId": session_id, "update": body},
        }
    )


def chunk(session_id, text):
    update(
        session_id,
        {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": text},
        },
    )


def finish(prompt, stop_reason="end_turn"):
    send({"id": prompt["id"], "result": {"stopReason": stop_reason}})


def request(method, params):
    global next_id
    next_id += 1
    send({"id": f"agent-{next_id}", "method": method, "params": params})
    return f"agent-{next_id}"


def handle_prompt(message):
    params = message["params"]
    session_id = params["sessionId"]
    text = params["prompt"][0]["text"]
    sessions[session_id].append(text)
    prompt = {"id": message["id"], "session": session_id}
    chunk(session_id, "echo: ")
    chunk(session_id, text)
    update(
        session_id,
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "call-1",
            "title": "Read file",
            "kind": "read",
            "status": "pending",
        },
    )
    update(
        session_id,
        {
            "sessionUpdate": "tool_call_update",
            "toolCallId": "call-1",
            "status": "completed",
        },
    )
    if "die-now" in text:
        sys.exit(3)
    if "needs-permission" in text:
        waiting[
            request(
                "session/request_permission",
                {
                    "sessionId": session_id,
                    "toolCall": {"toolCallId": "call-2", "title": "Write file"},
                    "options": [
                        {
                            "optionId": "allow_once",
                            "name": "Allow",
                            "kind": "allow_once",
                        },
                        {
                            "optionId": "reject_once",
                            "name": "Reject",
                            "kind": "reject_once",
                        },
                    ],
                },
            )
        ] = prompt
    elif "needs-interview" in text:
        waiting[
            request(
                "_clio-coder/interview/request",
                {
                    "sessionId": session_id,
                    "interviewId": "interview-1",
                    "questions": [
                        {
                            "question": "Which database?",
                            "header": "Storage",
                            "options": [
                                {"label": "DuckDB", "description": "embedded"},
                                {"label": "Postgres"},
                            ],
                        },
                        {"question": "Anything else?"},
                    ],
                },
            )
        ] = prompt
    elif "worker-ask" in text:
        ask_id = request(
            "session/request_permission",
            {
                "sessionId": session_id,
                "toolCall": {
                    "toolCallId": "call-3",
                    "title": "Run command",
                    "rawInput": {"command": "rm -rf build"},
                },
                "options": [
                    {"optionId": "allow-once", "name": "Approve", "kind": "allow_once"},
                    {"optionId": "reject-once", "name": "Deny", "kind": "reject_once"},
                ],
                "_meta": {
                    "clio-coder/workerAsk": {"requestId": "w-1", "agentId": "scout"},
                    "clio-coder/decision": {
                        "title": "Delete the build tree",
                        "consequenceLines": ["Removes build/ recursively."],
                    },
                },
            },
        )
        waiting[ask_id] = prompt
        if "withdraw" in text:
            threading.Timer(
                0.5,
                send,
                [
                    {
                        "method": "_clio-coder/permission/withdraw",
                        "params": {"sessionId": session_id, "requestId": "w-1"},
                    }
                ],
            ).start()
    elif "sleepy" in text:
        update(
            session_id,
            {
                "sessionUpdate": "plan",
                "entries": [
                    {"content": "read the code", "status": "completed"},
                    {"content": "run the tests", "status": "in_progress"},
                    {"content": "commit", "status": "pending"},
                ],
            },
        )
        update(
            session_id,
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-9",
                "title": "Run `pytest -q`",
                "status": "in_progress",
            },
        )
        threading.Timer(1.2, finish, [prompt]).start()
    elif "show-meta" in text:
        chunk(session_id, " meta " + json.dumps(client_meta, sort_keys=True))
        finish(prompt)
    elif "fs-read" in text:
        waiting[
            request("fs/read_text_file", {"sessionId": session_id, "path": "/x"})
        ] = prompt
    elif "slow" in text:
        waiting[session_id] = prompt
    else:
        finish(prompt)


def handle_response(message):
    prompt = waiting.pop(message["id"], None)
    if prompt is None:
        return
    if "error" in message:
        chunk(prompt["session"], f" error {message['error']['code']}")
        finish(prompt)
        return
    result = message["result"]
    if "outcome" not in result:  # an interview reply
        chunk(prompt["session"], " interview " + json.dumps(result, sort_keys=True))
        finish(prompt)
        return
    outcome = result["outcome"]
    if outcome["outcome"] == "cancelled":
        finish(prompt, "cancelled")
        return
    chunk(prompt["session"], f" chose {outcome['optionId']}")
    finish(prompt)


def handle(message):
    method = message.get("method")
    if LOG and method:
        with open(LOG, "a") as log:
            log.write(method + "\n")
    if method is None:
        handle_response(message)
        return
    params = message.get("params") or {}
    if method == "initialize":
        client_meta.update(params.get("clientCapabilities", {}).get("_meta") or {})
        if os.environ.get("FAKE_ACP_NOISE"):
            sys.stdout.write("{" + "x" * 200_000 + "}\n")
        send({"method": "_vendor/ping", "params": {}})
        session_caps = {"close": {}} if "close" in CAPS else {}
        if "list" in CAPS:
            session_caps["list"] = {}
        if "resume" in CAPS:
            session_caps["resume"] = {}
        send(
            {
                "id": message["id"],
                "result": {
                    "protocolVersion": 1,
                    "agentCapabilities": {
                        "loadSession": "load" in CAPS,
                        "sessionCapabilities": session_caps,
                    },
                    "authMethods": [],
                },
            }
        )
    elif method == "session/new":
        if os.environ.get("FAKE_ACP_AUTH"):
            send(
                {
                    "id": message["id"],
                    "error": {"code": -32000, "message": "Authentication required"},
                }
            )
            return
        session_id = f"sess-{len(sessions) + 1}"
        sessions[session_id] = []
        send({"id": message["id"], "result": {"sessionId": session_id}})
    elif method in ("session/load", "session/resume"):
        session_id = params.get("sessionId")
        if session_id not in sessions:
            send(
                {
                    "id": message["id"],
                    "error": {"code": -32002, "message": "Session not found"},
                }
            )
            return
        if method == "session/load":
            for text in sessions[session_id]:
                chunk(session_id, f"replayed {text}")
        send({"id": message["id"], "result": {}})
    elif method == "session/list":
        send(
            {
                "id": message["id"],
                "result": {
                    "sessions": [
                        {
                            "sessionId": "old",
                            "cwd": params["cwd"],
                            "updatedAt": "2026-11-01T00:00:00Z",
                        },
                        {
                            "sessionId": "live",
                            "cwd": params["cwd"],
                            "updatedAt": "2026-11-15T09:00:00Z",
                            "title": "Refactor",
                        },
                        {
                            "sessionId": "elsewhere",
                            "cwd": "/other",
                            "updatedAt": "2026-11-16T00:00:00Z",
                        },
                    ]
                },
            }
        )
    elif method == "session/close":
        sessions.pop(params.get("sessionId"), None)
        send({"id": message["id"], "result": {}})
    elif method == "session/prompt":
        handle_prompt(message)
    elif method == "session/cancel":
        prompt = waiting.pop(params.get("sessionId"), None)
        if prompt is not None:
            finish(prompt, "cancelled")
    elif "id" in message:
        send({"id": message["id"], "error": {"code": -32601, "message": "nope"}})


def main():
    print("fake acp agent booting")
    sys.stdout.flush()
    for line in sys.stdin:
        if line.strip():
            handle(json.loads(line))


if __name__ == "__main__":
    main()
