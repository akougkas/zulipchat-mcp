"""Cover legacy wrapper getters in messaging_v25."""

from __future__ import annotations

import asyncio

from zulipchat_mcp.tools.messaging_v25 import (
    get_legacy_edit_message,
    get_legacy_get_messages,
    get_legacy_send_message,
)


def test_legacy_wrapper_coroutines_exist() -> None:
    send = get_legacy_send_message()
    get = get_legacy_get_messages()
    edit = get_legacy_edit_message()
    # Just ensure they are awaitable and invoke without raising
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send("stream", "general", "hi", topic="t"))
    loop.run_until_complete(get())
    loop.run_until_complete(edit(1, content="x"))
