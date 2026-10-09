"""Preserve Zulip error codes and retry instructions at the MCP boundary."""

from typing import Any


def api_error(response: dict[str, Any], fallback: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "error",
        "error": response.get("msg") or fallback,
    }
    if response.get("code") is not None:
        result["error_code"] = response["code"]
    retry = response.get("retry-after")
    if retry is not None:
        result["retry_after_seconds"] = retry
    if response.get("code") == "RATE_LIMIT_HIT":
        result["retryable"] = True
    elif "retryable" in response:
        result["retryable"] = response["retryable"]
    return result
