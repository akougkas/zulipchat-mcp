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
from functools import lru_cache
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-opus-5"
MODEL_ENV_VAR = "ANTHROPIC_MODEL"
API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM provider is configured for server-side analytics."""


class LLMResponseError(RuntimeError):
    """Raised when an LLM provider returns no usable response text."""


def _get_model() -> str:
    return os.getenv(MODEL_ENV_VAR, "").strip() or DEFAULT_MODEL


def llm_available() -> bool:
    """Whether a server-side LLM provider is configured and importable."""
    if not os.getenv(API_KEY_ENV_VAR, "").strip():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _get_client(api_key: str) -> Any:
    """Build the shared Anthropic client."""
    import anthropic

    return anthropic.AsyncAnthropic(api_key=api_key)


async def generate(prompt: str, *, max_tokens: int = 8192) -> str:
    """Generate a text completion for an analytics prompt.

    Raises LLMUnavailableError if no provider is configured; provider/network
    errors propagate as-is so callers can wrap them in their tool responses.

    Current models think by default and max_tokens caps thinking plus response
    text together, so the budget is sized well above the length of an analytics
    summary to avoid truncating the answer mid-sentence.
    """
    if not llm_available():
        raise LLMUnavailableError(
            f"Server-side analytics require {API_KEY_ENV_VAR} to be set "
            "(MCP sampling is deprecated in the 2026-07-28 protocol)."
        )

    client = _get_client(os.environ[API_KEY_ENV_VAR])
    message = await client.messages.create(
        model=_get_model(),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low"},
    )

    text = _extract_text(message)
    if getattr(message, "stop_reason", None) == "max_tokens":
        raise LLMResponseError("LLM response was truncated at max_tokens")
    if text.strip():
        return text.strip()
    raise LLMResponseError("LLM response contained no text content")


def _extract_text(message: Any) -> str:
    """Join text blocks from an Anthropic Messages response."""
    return "".join(
        block.text
        for block in getattr(message, "content", []) or []
        if getattr(block, "type", None) == "text"
    )
