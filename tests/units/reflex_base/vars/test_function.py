"""Tests for function vars and the call operations built from them."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.vars.base import Var
from reflex_base.vars.function import FunctionVar, ReflexCallable


def test_call_on_optional_function_is_an_optional_call() -> None:
    """A function that may be null is called with `?.()` so null is a no-op."""
    fn = Var(_js_expr="fn", _var_type=ReflexCallable[[int], str] | None).to(FunctionVar)
    call = fn.call(1)
    assert str(call) == "(fn?.(1))"
    assert call._var_type == str | None


def test_call_on_optional_arrow_function_is_wrapped() -> None:
    """An inline arrow function is parenthesized before the optional call."""
    fn = Var(_js_expr="(x) => x", _var_type=ReflexCallable[[int], int] | None).to(
        FunctionVar
    )
    assert str(fn.call(1)) == "(((x) => x)?.(1))"


def test_call_on_required_function_is_a_plain_call() -> None:
    """A function that cannot be null keeps the direct call."""
    fn = Var(_js_expr="fn", _var_type=ReflexCallable[[int], str]).to(FunctionVar)
    call = fn.call(1)
    assert str(call) == "(fn(1))"
    assert call._var_type is str


def test_optional_call_result_gets_the_null_fallback() -> None:
    """An operation on the result of an optional call guards against undefined."""
    fn = Var(_js_expr="fn", _var_type=ReflexCallable[[], list[int]] | None).to(
        FunctionVar
    )
    assert str(fn.call().length()) == "((fn?.()) ?? []).length"


@pytest.mark.parametrize(
    ("function_type", "args", "expected", "expected_type"),
    [
        (Callable[[int], None] | None, (1,), "(fn?.(1))", type(None)),
        (Callable[[], None] | None, (), "(fn?.())", type(None)),
        (Callable[[int, int], str] | None, (1, 2), "(fn?.(1, 2))", str | None),
        (ReflexCallable[[int, int], str] | None, (1, 2), "(fn?.(1, 2))", str | None),
        (Callable[[int, int], str], (1, 2), "(fn(1, 2))", str),
    ],
)
def test_call_reads_the_return_type_from_any_arity(
    function_type: Any, args: tuple[Any, ...], expected: str, expected_type: Any
) -> None:
    """The return type is the last type argument, whatever the parameter count."""
    call = Var(_js_expr="fn", _var_type=function_type).to(FunctionVar).call(*args)
    assert str(call) == expected
    assert call._var_type == expected_type


def test_partial_on_optional_function_is_an_optional_call() -> None:
    """A partial application of a nullable function also skips null."""
    fn = Var(_js_expr="fn", _var_type=Callable[[int], None] | None).to(FunctionVar)
    assert str(fn.partial(1)) == "((...args) => (fn?.(1, ...args)))"
