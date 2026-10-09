"""Cross-posts preserve source Markdown and one operation's identity."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP

from zulipchat_mcp.core.client import ZulipClientWrapper
from zulipchat_mcp.tools import messaging


@pytest.mark.parametrize("apply_markdown", [None, False, True])
@pytest.mark.parametrize("sdk_method", [True, False])
def test_message_wrapper_rendering_option(apply_markdown, sdk_method):
    sdk = MagicMock() if sdk_method else SimpleNamespace(call_endpoint=MagicMock())
    wrapper = object.__new__(ZulipClientWrapper)
    wrapper._client = sdk
    wrapper.get_message(42, apply_markdown=apply_markdown)
    request = {} if apply_markdown is None else {"apply_markdown": apply_markdown}
    if sdk_method:
        sdk.get_message.assert_called_once_with(message_id=42, **request)
    else:
        sdk.call_endpoint.assert_called_once_with(
            "messages/42", method="GET", request=request
        )


async def test_cross_post_wire_preserves_markdown_and_captured_identity(monkeypatch):
    raw = "**bold** [link](https://example.test) @**Alice**\n```\ncode\n```"
    first = MagicMock()
    other = MagicMock()

    def fetch(message_id, *, apply_markdown):
        assert message_id == 42
        assert apply_markdown is False
        # Model another stdio request switching the active account during the fetch.
        monkeypatch.setattr(messaging, "get_client", lambda: other)
        return {"result": "success", "message": {"content": raw, "subject": "topic"}}

    first.get_message.side_effect = fetch
    first.send_message.side_effect = [
        {"result": "success", "id": 101},
        {"result": "success", "id": 102},
    ]
    monkeypatch.setattr(messaging, "get_client", lambda: first)
    server = FastMCP("cross-post", tasks=False)
    server.tool(messaging.cross_post_message)
    async with Client(server) as client:
        result = (
            await client.call_tool(
                "cross_post_message",
                {
                    "source_message_id": 42,
                    "target_streams": ["one", "two"],
                    "add_reference": False,
                },
            )
        ).data
    assert result["successful"] == 2
    assert [call.args for call in first.send_message.call_args_list] == [
        ("stream", "one", raw, "topic"),
        ("stream", "two", raw, "topic"),
    ]
    other.send_message.assert_not_called()


@pytest.mark.parametrize(
    "failure", [RuntimeError("connection lost"), {"result": "error", "msg": "denied"}]
)
async def test_cross_post_retains_confirmed_sends_after_failure(monkeypatch, failure):
    client = MagicMock()
    client.get_message.return_value = {
        "result": "success",
        "message": {"content": "source", "subject": "topic"},
    }
    client.send_message.side_effect = [{"result": "success", "id": 101}, failure]
    monkeypatch.setattr(messaging, "get_client", lambda: client)
    result = await messaging.cross_post_message(42, ["one", "two"])
    assert result["status"] == "partial"
    assert result["successful"] == result["failed"] == 1
    assert result["results"][0]["message_id"] == 101
    assert result["results"][1]["status"] == "error"
    assert client.send_message.call_count == 2
