"""Tests for function vars and the call operations built from them."""

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
