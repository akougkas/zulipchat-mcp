"""Translate Zulip narrow operators to the names a server understands."""

from __future__ import annotations

from typing import Any

# Current operator names and the feature level that introduced each.
_CURRENT_OPERATORS = {
    "stream": ("channel", 250),
    "streams": ("channels", 250),
    "pm-with": ("dm", 177),
    "group-pm-with": ("dm-including", 177),
}
_LEGACY_OPERATORS = {
    new: (old, level) for old, (new, level) in _CURRENT_OPERATORS.items()
}


def wire_narrow(narrow: list[Any], supports: Any) -> list[Any]:
    """Rewrite narrow operators to the names the server understands.

    Callers may use either legacy (stream, pm-with, group-pm-with, is:private)
    or current (channel, dm, dm-including, is:dm) names. `supports(level)`
    reports whether the server is at least that feature level. Accepts dict
    terms and [operator, operand] pairs.
    """

    def convert(operator: str, operand: Any) -> tuple[str, Any]:
        if operator == "is" and operand in ("private", "dm"):
            return operator, "dm" if supports(177) else "private"
        if operator in _CURRENT_OPERATORS:
            new, level = _CURRENT_OPERATORS[operator]
            return (new if supports(level) else operator), operand
        if operator in _LEGACY_OPERATORS:
            old, level = _LEGACY_OPERATORS[operator]
            return (operator if supports(level) else old), operand
        return operator, operand

    result: list[Any] = []
    for term in narrow:
        if isinstance(term, dict) and "operator" in term:
            operator, operand = convert(term["operator"], term.get("operand"))
            result.append({**term, "operator": operator, "operand": operand})
        elif isinstance(term, (list, tuple)) and len(term) == 2:
            result.append(list(convert(term[0], term[1])))
        else:
            result.append(term)
    return result
