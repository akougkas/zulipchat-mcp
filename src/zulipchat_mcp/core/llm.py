"""Server-side LLM provider for analytics tools.

Replaces MCP sampling (deprecated in spec 2026-07-28, removed from the
FastMCP 4 server API) with a direct call to an LLM provider owned by this
server. Currently Anthropic-only, keyed off ANTHROPIC_API_KEY, matching the
fallback sampling handler the server previously configured.

The analytics tools keep their signatures and response shapes; only the
generation path changes. When no API key is configured, providers report
themselves unavailable so callers can degrade gracefully.
"""

from __future__ import annotations

import os
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MODEL_ENV_VAR = "ANTHROPIC_MODEL"
API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM provider is configured for server-side analytics."""


def _get_model() -> str:
    return os.getenv(MODEL_ENV_VAR, DEFAULT_MODEL)


def llm_available() -> bool:
    """Whether a server-side LLM provider is configured and importable."""
    if not os.getenv(API_KEY_ENV_VAR):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


async def generate(prompt: str, *, max_tokens: int = 2048) -> str:
    """Generate a text completion for an analytics prompt.

    Raises LLMUnavailableError if no provider is configured; provider/network
    errors propagate as-is so callers can wrap them in their tool responses.
    """
    if not llm_available():
        raise LLMUnavailableError(
            f"Server-side analytics require {API_KEY_ENV_VAR} to be set "
            "(MCP sampling was removed in the 2026-07-28 protocol)."
        )

    import anthropic

    client = anthropic.AsyncAnthropic()
    message = await client.messages.create(
        model=_get_model(),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )

    text = _extract_text(message)
    if not text:
        raise LLMUnavailableError("LLM response contained no text content")
    return text.strip()


def _extract_text(message: Any) -> str:
    """Extract the first text block from an Anthropic Messages response."""
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""
