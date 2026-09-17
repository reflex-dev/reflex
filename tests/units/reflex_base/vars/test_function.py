"""Tests for reflex_base.vars.function."""

from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import (
    FunctionStringVar,
    ReflexCallable,
    VarOperationCall,
)
from reflex_base.vars.sequence import LiteralStringVar


@pytest.fixture
def my_func() -> FunctionStringVar[ReflexCallable[..., str]]:
    """A function var to call in the tests.

    Returns:
        A function var returning a string.
    """
    return FunctionStringVar.create("myFunc", _var_type=ReflexCallable[..., str])


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ({"a": 1}, '(myFunc(({ ["a"] : 1 })))'),
        ([1, 2], "(myFunc([1, 2]))"),
        ({1, 2}, "(myFunc([1, 2]))"),
        ("a", '(myFunc("a"))'),
        (None, "(myFunc(null))"),
    ],
)
def test_call_converts_args_to_vars(
    my_func: FunctionStringVar, arg: Any, expected: str
):
    """Raw Python args are converted to Vars up front, keeping the call hashable.

    Args:
        my_func: The function var to call.
        arg: The raw Python argument to call the function with.
        expected: The expected JavaScript expression.
    """
    call = my_func.call(arg)

    assert all(isinstance(call_arg, Var) for call_arg in call._args)
    assert str(call) == expected
    # Unhashable args used to blow up here, since CachedVarOperation hashes its fields.
    assert hash(call) == hash(my_func.call(arg))


def test_call_with_unhashable_arg_in_f_string(my_func: FunctionStringVar):
    """A call with an unhashable arg can be embedded in an f-string.

    Args:
        my_func: The function var to call.
    """
    call = my_func.call({"a": 1})

    assert (
        str(LiteralStringVar.create(f"prefix {call}"))
        == '("prefix "+(myFunc(({ ["a"] : 1 }))))'
    )


def test_call_keeps_var_data_of_nested_args(my_func: FunctionStringVar):
    """Var data of Vars nested inside raw container args is still collected.

    Args:
        my_func: The function var to call.
    """
    inner = Var(
        _js_expr="innerThing",
        _var_data=VarData(
            imports={"some-lib": [ImportVar(tag="innerThing")]},
            hooks="const innerThing = 1;",
        ),
    )

    var_data = my_func.call({"a": inner})._get_all_var_data()

    assert var_data is not None
    assert var_data.imports == (("some-lib", (ImportVar(tag="innerThing"),)),)
    assert var_data.hooks == ("const innerThing = 1;",)


def test_partial_with_unhashable_arg(my_func: FunctionStringVar):
    """Partially applying a function with an unhashable arg keeps it hashable.

    Args:
        my_func: The function var to call.
    """
    partial = my_func.partial({"a": 1})

    assert str(partial) == '((...args) => (myFunc(({ ["a"] : 1 }), ...args)))'
    assert hash(partial) == hash(my_func.partial({"a": 1}))


def test_create_leaves_vars_untouched(my_func: FunctionStringVar):
    """Args that are already Vars are passed through without being re-wrapped.

    Args:
        my_func: The function var to call.
    """
    arg = LiteralVar.create({"a": 1})

    assert VarOperationCall.create(my_func, arg)._args[0] is arg
