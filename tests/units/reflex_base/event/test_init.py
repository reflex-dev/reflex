"""Tests for the trigger-argument placeholders ``parse_args_spec`` hands out."""

from typing import cast

from reflex_base.event import (
    EventArgVar,
    event_arg_placeholder,
    event_args_signature,
    parse_args_spec,
    passthrough_event_spec,
)
from reflex_base.vars.base import Var
from reflex_base.vars.number import NumberVar


def test_parse_args_spec_hands_out_positioned_placeholders() -> None:
    """Each argument is a placeholder that knows the trigger's full signature."""
    placeholders, _annotations = parse_args_spec(passthrough_event_spec(int, str))
    args = [event_arg_placeholder(placeholder) for placeholder in placeholders]
    assert all(isinstance(arg, EventArgVar) for arg in args)
    assert [arg._js_expr for arg in args] == ["_ev_0", "_ev_1"]  # pyright: ignore [reportOptionalMemberAccess]
    assert all(arg._signature == ("_ev_0", "_ev_1") for arg in args)  # pyright: ignore [reportOptionalMemberAccess]
    # The caller holds the typed cast, which is still recognized as the placeholder.
    assert placeholders[0]._var_type is int


def test_event_args_signature_covers_every_argument_up_to_the_last_read() -> None:
    """The declaration follows the trigger's order and includes skipped leading args."""
    placeholders, _annotations = parse_args_spec(passthrough_event_spec(int, int))
    first, second = (cast("NumberVar", placeholder) for placeholder in placeholders)
    assert event_args_signature(second - first) == ("_ev_0", "_ev_1")
    assert event_args_signature(second) == ("_ev_0", "_ev_1")
    assert event_args_signature(first + 1) == ("_ev_0",)
    assert event_args_signature(Var.create(42)) == ()
    assert event_args_signature(Var("_ev_0")) == ()


def test_event_args_signature_looks_through_a_function_body() -> None:
    """A function value is searched through its body, not treated as a leaf."""
    from reflex_base.vars.function import ArgsFunctionOperationBuilder

    (arg,), _annotations = parse_args_spec(passthrough_event_spec(int))
    prev = cast("NumberVar", Var("prev", _var_type=int).guess_type())
    updater = ArgsFunctionOperationBuilder.create(
        args_names=("prev",), return_expr=prev + cast("NumberVar", arg)
    )
    assert event_args_signature(updater) == ("_ev_0",)


def test_event_args_signature_reaches_into_a_nested_lambda() -> None:
    """A placeholder closed over by a nested function is found whatever its body reads."""
    from reflex_base.vars.function import ArgsFunctionOperationBuilder

    (arg,), _annotations = parse_args_spec(passthrough_event_spec(int))
    # One leaf of the body reads the parameter by text, which makes
    # ``get_leaf_vars`` keep the whole function as one opaque leaf.
    field = cast("NumberVar", Var("item.count", _var_type=int).guess_type())
    nested = ArgsFunctionOperationBuilder.create(
        args_names=("item",), return_expr=field + cast("NumberVar", arg)
    )
    assert event_args_signature(nested) == ("_ev_0",)
