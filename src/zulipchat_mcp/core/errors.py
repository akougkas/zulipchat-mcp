"""One error shape for every tool result.

An error result is ``{"status": "error", "error": {...}}`` where the error
object always has ``code``, ``message`` and ``retryable``, plus
``retry_after_seconds`` when the server named a wait and ``recovery`` naming
the tool to call next when there is one. A partial result carries the same
object beside the data it did return.
"""

from __future__ import annotations

from typing import Any

ERROR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Present when status is error or partial.",
    "properties": {
        "code": {
            "type": "string",
            "description": "Stable error code, e.g. INVALID_ARGUMENT, NOT_FOUND, "
            "RATE_LIMIT_HIT, or the code Zulip returned.",
        },
        "message": {"type": "string", "description": "What went wrong."},
        "retryable": {
            "type": "boolean",
            "description": "True only when repeating the same call later can "
            "succeed unchanged.",
        },
        "retry_after_seconds": {
            "type": "number",
            "description": "How long to wait before retrying.",
        },
        "recovery": {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "description": "Tool to call next."},
                "hint": {"type": "string", "description": "What to do."},
            },
            "required": ["hint"],
        },
    },
    "required": ["code", "message", "retryable"],
    "additionalProperties": True,
}


def error_object(
    message: str,
    code: str = "INVALID_ARGUMENT",
    *,
    retryable: bool = False,
    retry_after_seconds: float | None = None,
    recovery_tool: str | None = None,
    hint: str | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if retry_after_seconds is not None:
        error["retry_after_seconds"] = retry_after_seconds
    if hint is not None or recovery_tool is not None:
        recovery: dict[str, Any] = {"hint": hint or f"Call {recovery_tool}."}
        if recovery_tool is not None:
            recovery["tool"] = recovery_tool
        error["recovery"] = recovery
    return error


def tool_error(
    message: str,
    code: str = "INVALID_ARGUMENT",
    *,
    retryable: bool = False,
    retry_after_seconds: float | None = None,
    recovery_tool: str | None = None,
    hint: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """An error result; extra fields (candidates, partial counts) sit beside it."""
    return {
        "status": "error",
        "error": error_object(
            message,
            code,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
            recovery_tool=recovery_tool,
            hint=hint,
        ),
        **fields,
    }


def internal_error(exc: BaseException) -> dict[str, Any]:
    """An unexpected failure; the outcome of a write is unknown, so no retry."""
    return tool_error(str(exc) or type(exc).__name__, "INTERNAL_ERROR")


def _seconds(value: Any) -> float | None:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def api_error(
    response: dict[str, Any],
    fallback: str,
    *,
    recovery_tool: str | None = None,
    hint: str | None = None,
) -> dict[str, Any]:
    """Preserve Zulip's error code and retry instruction at the MCP boundary."""
    code = response.get("code")
    retry_after = _seconds(response.get("retry-after"))
    retryable = code == "RATE_LIMIT_HIT" or bool(response.get("retryable", False))
    return tool_error(
        response.get("msg") or fallback,
        str(code) if code else "ZULIP_ERROR",
        retryable=retryable,
        retry_after_seconds=retry_after,
        recovery_tool=recovery_tool,
        hint=hint,
    )


def normalize_error(data: dict[str, Any]) -> dict[str, Any]:
    """Bring a legacy error result (string error, error_code, suggestions) to shape.

    Idempotent: a canonical result comes back unchanged.
    """
    raw = data.get("error")
    if isinstance(raw, dict) and {"code", "message", "retryable"} <= raw.keys():
        return data
    rest = {
        k: v
        for k, v in data.items()
        if k
        not in {
            "error",
            "error_code",
            "code",
            "retryable",
            "retry_after_seconds",
            "suggestion",
            "suggestions",
        }
    }
    source = raw if isinstance(raw, dict) else {}
    message = str(source.get("message") or raw or data.get("status") or "error")
    code = source.get("code") or data.get("error_code") or data.get("code")
    suggestions = source.get("suggestions") or data.get("suggestions")
    hint = data.get("suggestion") or (
        "; ".join(map(str, suggestions)) if suggestions else None
    )
    recovery = source.get("recovery") if isinstance(source, dict) else None
    error = error_object(
        message,
        str(code) if code else "TOOL_ERROR",
        retryable=bool(source.get("retryable", data.get("retryable", False))),
        retry_after_seconds=_seconds(
            source.get("retry_after_seconds", data.get("retry_after_seconds"))
        ),
        recovery_tool=(recovery or {}).get("tool"),
        hint=(recovery or {}).get("hint") or hint,
    )
    return {**rest, "error": error}
