"""Tests for reflex_base.vars.sequence."""

import operator
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.vars.base import Var
from reflex_base.vars.sequence import ArrayVar, StringVar


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


def _string(var_type: Any, js_expr: str = "state.maybe") -> StringVar:
    var = Var(_js_expr=js_expr, _var_type=var_type).guess_type()
    assert isinstance(var, StringVar)
    return var


_SEP = Var(_js_expr="state.sep").to(str)

# Each operation with the JS it compiles to, given the JS of the string it reads.
_STRING_OPERATIONS: list[tuple[Callable[[StringVar], Var], str]] = [
    (lambda string: string.lower(), "{}.toLowerCase()"),
    (lambda string: string.upper(), "{}.toUpperCase()"),
    (
        lambda string: string.title(),
        (
            "{}.split(' ').map(word => word.charAt(0).toUpperCase()"
            " + word.slice(1).toLowerCase()).join(' ')"
        ),
    ),
    (
        lambda string: string.capitalize(),
        "(((s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase())({}))",
    ),
    (lambda string: string.strip(), "pyStrip({}, null)"),
    (lambda string: string.lstrip("-"), 'pyLstrip({}, "-")'),
    (lambda string: string.rstrip(_SEP), "pyRstrip({}, state.sep)"),
    (lambda string: string.contains("x"), '{}.includes("x")'),
    (lambda string: string.split(" "), '{}.split(" ")'),
    (lambda string: string.split(_SEP), "pyStrSplit({}, state.sep)"),
    (lambda string: string.startswith("x"), '{}.startsWith("x")'),
    (lambda string: string.endswith("x"), '{}.endsWith("x")'),
    (lambda string: string.replace("x", "y"), '{}.replaceAll("x", "y")'),
    (lambda string: string * 2, "{}.repeat(Math.max(0, 2))"),
    (lambda string: 2 * string, "{}.repeat(Math.max(0, 2))"),
]


@pytest.mark.parametrize(("operation", "expected"), _STRING_OPERATIONS)
def test_optional_string_operations_treat_none_as_empty(
    operation: Callable[[StringVar], Var], expected: str
):
    """Every operation on an optional string reads a null value as an empty string."""
    assert str(operation(_string(str | None))) == expected.format('(state.maybe ?? "")')


@pytest.mark.parametrize(("operation", "expected"), _STRING_OPERATIONS)
def test_string_operations_do_not_guard_a_required_string(
    operation: Callable[[StringVar], Var], expected: str
):
    """A string that cannot be None compiles without the null guard."""
    assert str(operation(_string(str))) == expected.format("state.maybe")


def test_optional_string_operation_results():
    """The null guard drops None from the result type; null-safe helpers need none."""
    maybe = _string(str | None)
    assert maybe.lower()._var_type is str
    assert maybe.split(" ")._var_type == list[str]
    # The code point helpers already read null as an empty string.
    assert str(maybe.length()) == "pyStrLength(state.maybe)"
    assert str(maybe[0]) == "pyStrAt(state.maybe, 0)"
    assert str(maybe[1:]) == "pyStrSlice(state.maybe, 1, null)"
    assert str(maybe.split()) == "pyStrChars(state.maybe)"
    assert str(maybe.reversed()) == 'pyStrChars(state.maybe).slice().reverse().join("")'
    # The var itself still reads as None.
    assert str(maybe.is_none()) == "!(isNotNullOrUndefined(state.maybe))"
