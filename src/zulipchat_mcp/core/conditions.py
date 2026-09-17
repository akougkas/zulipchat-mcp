"""Evaluate the small, data-only expression language used by command chains."""

from __future__ import annotations

import ast
import operator
from typing import Any

_COMPARISONS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
}


def evaluate_condition(expression: str, context: dict[str, Any]) -> bool:
    """Support comparisons, boolean logic, lookups, dict.get and len without eval.

    Attribute traversal, arbitrary calls, comprehensions and arithmetic are
    deliberately excluded. Size limits also bound the parser and tree walk.
    """
    if len(expression) > 4096:
        raise ValueError("Condition expression is too long")
    try:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 256:
            raise ValueError("Condition expression is too complex")

        def visit(node: ast.AST) -> Any:
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name) and node.id == "context":
                return context
            if isinstance(node, (ast.List, ast.Tuple)):
                values = [visit(item) for item in node.elts]
                return tuple(values) if isinstance(node, ast.Tuple) else values
            if isinstance(node, ast.Dict):
                if any(key is None for key in node.keys):
                    raise ValueError("Dictionary unpacking is not supported")
                return {
                    visit(key): visit(value)
                    for key, value in zip(node.keys, node.values, strict=True)
                    if key is not None
                }
            if isinstance(node, ast.Subscript):
                value, key = visit(node.value), visit(node.slice)
                if type(value) not in (dict, list, tuple, str):
                    raise ValueError("Lookups require a dictionary, list or string")
                return value[key]
            if isinstance(node, ast.UnaryOp):
                value = visit(node.operand)
                if isinstance(node.op, ast.Not):
                    return not value
                if isinstance(node.op, (ast.USub, ast.UAdd)) and type(value) in (
                    int,
                    float,
                ):
                    return -value if isinstance(node.op, ast.USub) else value
            if isinstance(node, ast.BoolOp):
                for item in node.values:
                    value = visit(item)
                    if isinstance(node.op, ast.And) and not value:
                        return value
                    if isinstance(node.op, ast.Or) and value:
                        return value
                return value
            if isinstance(node, ast.Compare):
                left = visit(node.left)
                for op, comparator in zip(node.ops, node.comparators, strict=True):
                    right = visit(comparator)
                    if not _COMPARISONS[type(op)](left, right):
                        return False
                    left = right
                return True
            if isinstance(node, ast.Call) and not node.keywords:
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "len"
                    and len(node.args) == 1
                ):
                    value = visit(node.args[0])
                    if type(value) not in (dict, list, tuple, str):
                        raise ValueError("len requires a dictionary, list or string")
                    return len(value)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and 1 <= len(node.args) <= 2
                ):
                    value = visit(node.func.value)
                    if type(value) is not dict:
                        raise ValueError("get requires a dictionary")
                    return value.get(*(visit(arg) for arg in node.args))
            raise ValueError(f"Unsupported condition syntax: {type(node).__name__}")

        return bool(visit(tree.body))
    except (
        SyntaxError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RecursionError,
    ) as e:
        raise ValueError(f"Invalid condition expression: {e}") from e
