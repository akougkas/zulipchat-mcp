"""Command conditions must inspect data without executing Python code."""

import pytest

from zulipchat_mcp.core.conditions import evaluate_condition


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("len(context.get('search_results', [])) > 0", True),
        ("context['x'] > 1 and context.get('missing') is None", True),
        ("not context['x'] or context['x'] in [1, 2]", True),
        ("-1 < context['x'] <= 2", True),
        ("context.get('missing', {}).get('key', False)", False),
        ("False and context['missing']", False),
    ],
)
def test_conditions_support_documented_data_operations(expression, expected):
    assert evaluate_condition(expression, {"x": 2, "search_results": [1]}) is expected


@pytest.mark.parametrize(
    "expression",
    [
        "().__class__.__base__.__subclasses__()",
        "context.__class__",
        "__import__('os').getcwd()",
        "context.clear()",
        "[x for x in context]",
        "2 ** 1000000000",
        "'x' * 1000000000",
        "len(context, unexpected=True)",
        "True " * 1000,
    ],
)
def test_conditions_reject_code_execution_and_unbounded_work(expression):
    context = {"keep": "unchanged"}
    with pytest.raises(ValueError):
        evaluate_condition(expression, context)
    assert context == {"keep": "unchanged"}
