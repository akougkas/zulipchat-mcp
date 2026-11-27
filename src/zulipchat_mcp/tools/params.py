"""Parameter types shared by tool signatures.

Descriptions and bounds declared here reach the advertised inputSchema and are
enforced by argument validation before a tool runs.
"""

from typing import Annotated, Any

from pydantic import Field

MAX_CONTENT_CHARS = 50000

MessageId = Annotated[int, Field(gt=0, description="Zulip message ID.")]
UserId = Annotated[int, Field(gt=0, description="Zulip user ID.")]
StreamId = Annotated[int, Field(gt=0, description="Zulip channel (stream) ID.")]
MessageIds = Annotated[
    list[Annotated[int, Field(gt=0)]],
    Field(min_length=1, max_length=1000, description="Zulip message IDs."),
]
Topic = Annotated[
    str, Field(min_length=1, max_length=60, description="Topic name within a channel.")
]
Content = Annotated[
    str,
    Field(
        min_length=1,
        max_length=MAX_CONTENT_CHARS,
        description="Message text in Zulip Markdown.",
    ),
]
Name = Annotated[str, Field(min_length=1, max_length=200)]
"""A bounded name, email or other identifier inside a union type."""
Timestamp = Annotated[str, Field(max_length=64)]
"""A bounded ISO 8601 string inside a union type."""

Fresh = Annotated[
    bool,
    Field(description="Bypass the 15-second read snapshot and fetch from Zulip now."),
]
Cursor = Annotated[
    str | None,
    Field(
        max_length=200,
        description="next_cursor from the previous page of the same call; omit "
        "for the first page.",
    ),
]


def page_size(maximum: int, what: str = "items") -> Any:
    """A page-size Field: 1..maximum."""
    return Field(
        ge=1,
        le=maximum,
        description=f"Most {what} to return in this page (1-{maximum}).",
    )
