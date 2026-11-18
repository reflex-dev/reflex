"""Tests for reflex_base.vars.sequence."""

import operator
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var
from reflex_base.vars.sequence import ArrayVar


def _array(var_type: Any, js_expr: str = "state.maybe") -> ArrayVar:
    var = Var(_js_expr=js_expr, _var_type=var_type).guess_type()
    assert isinstance(var, ArrayVar)
    return var


_ITEMS = Var(_js_expr="state.items").to(list[str])

_OPERATIONS: list[Callable[[ArrayVar], Var]] = [
    lambda array: array.length(),
    lambda array: array.contains("x"),
    lambda array: array.contains("x", "name"),
    lambda array: array.join(","),
    lambda array: array.reverse(),
    lambda array: array.pluck("name"),
    operator.itemgetter(slice(1, None)),
    lambda array: array * 2,
    lambda array: array + _ITEMS,
    lambda array: _ITEMS + array,
    lambda array: array.map(lambda item: item),
    lambda array: array.filter(lambda item: item),
    lambda array: array.reduce(operator.add, ""),
    lambda array: array.flat_map(lambda item: [item]),
]


@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize("var_type", [list[str] | None, tuple[str, ...] | None])
def test_optional_array_operations_treat_none_as_empty(
    operation: Callable[[ArrayVar], Var], var_type: Any
):
    """Every operation on an optional array reads a null value as an empty array."""
    assert "(state.maybe ?? [])" in str(operation(_array(var_type)))


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_array_operations_do_not_guard_a_required_array(
    operation: Callable[[ArrayVar], Var],
):
    """An array that cannot be None compiles without the null guard."""
    assert "??" not in str(operation(_array(list[str])))


def test_optional_array_operation_results():
    """The null guard keeps the element type and drops None from the array type."""
    maybe = _array(list[str] | None)
    assert str(maybe.length()) == "(state.maybe ?? []).length"
    assert str(maybe.contains("x")) == '(state.maybe ?? []).includes("x")'
    assert str(maybe.join(",")) == '(state.maybe ?? []).join(",")'
    assert maybe.reverse()._var_type == list[str]
    # Indexing is already null-safe, and the var itself still reads as None.
    assert str(maybe[0]) == "state.maybe?.at?.(0)"
    assert str(maybe.is_none()) == "!(isNotNullOrUndefined(state.maybe))"


_COMPARE_ARRAYS = ImportVar(tag="compareArrays", is_default=True, install=False)
_COMPARE_DATETIME = ImportVar(tag="compareDatetime", is_default=True, install=False)


@pytest.mark.parametrize(
    ("operation", "operator"),
    [
        (operator.lt, "<"),
        (operator.le, "<="),
        (operator.gt, ">"),
        (operator.ge, ">="),
    ],
)
def test_array_ordering_compiles_to_compare_arrays(
    operation: Callable[[Any, Any], Var], operator: str
):
    """Array ordering compiles to a compareArrays call, not a raw JS comparison.

    Args:
        operation: The Python comparison operator function.
        operator: The JS operator applied to the compareArrays result.
    """
    comparison = operation(Var.create([1, 10, 0]), [1, 9, 0])
    var_data = comparison._get_all_var_data()

    assert str(comparison) == f"(compareArrays([1, 10, 0], [1, 9, 0]) {operator} 0)"
    assert var_data is not None
    assert dict(var_data.imports) == {"$/utils/helpers/array.js": (_COMPARE_ARRAYS,)}


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        (
            [date(2024, 1, 1)],
            '(compareArrays(["2024-01-01"], ["2024-01-01"], compareDatetime) < 0)',
        ),
        (
            [datetime(2024, 1, 1, 12)],
            '(compareArrays(["2024-01-01 12:00:00"], ["2024-01-01 12:00:00"], compareDatetime) < 0)',
        ),
        (
            [[date(2024, 1, 1)]],
            '(compareArrays([["2024-01-01"]], [["2024-01-01"]], compareDatetime) < 0)',
        ),
    ],
)
def test_date_array_ordering_passes_compare_datetime(items: list, expected: str):
    """Dates reach the frontend as strings, so their lists order through compareDatetime.

    Args:
        items: A list of dates or datetimes, possibly nested.
        expected: The compiled comparison.
    """
    comparison = Var.create(items) < items
    var_data = comparison._get_all_var_data()

    assert str(comparison) == expected
    assert var_data is not None
    assert dict(var_data.imports) == {
        "$/utils/helpers/array.js": (_COMPARE_ARRAYS,),
        "$/utils/helpers/datetime.js": (_COMPARE_DATETIME,),
    }
