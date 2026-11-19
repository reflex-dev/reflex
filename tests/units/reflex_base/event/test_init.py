"""Tests for trigger-argument placeholders and the event chains built on them."""

from typing import Any, cast

from reflex_base.client_state import client_state
from reflex_base.event import (
    EventArgVar,
    EventChain,
    LambdaEventCallback,
    event_arg_placeholder,
    event_args_signature,
    no_args_event_spec,
    parse_args_spec,
    passthrough_event_spec,
)
from reflex_base.vars.base import Var
from reflex_base.vars.number import NumberVar

import reflex as rx


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


def test_cond_between_function_and_none_is_a_no_op_when_false() -> None:
    """A `None` branch of a cond around a client state setter is skipped, not called."""
    flag = client_state("", name="flag")
    chain = Var.create(
        EventChain.create(
            [rx.cond(Var.create(False), flag.set("x"), None)],
            args_spec=no_args_event_spec,
        )
    )
    assert (
        str(chain)
        == '((...args) => ((false ? (() => (flagRxClientStateSet("x"))) : null)?.(...args)))'
    )


def test_cond_between_function_and_none_inside_lambda_is_a_no_op_when_false() -> None:
    """The same cond returned from a lambda gets the optional call too."""
    flag = client_state("", name="flag")
    chain = Var.create(
        EventChain.create(
            cast(
                "LambdaEventCallback[Any]",
                lambda v: rx.cond(v == "go", flag.set(v), None),
            ),
            args_spec=passthrough_event_spec(str),
        )
    )
    assert (
        str(chain)
        == '((_ev_0) => (((_ev_0?.valueOf?.() === "go"?.valueOf?.()) ? ((_ev_0) => (flagRxClientStateSet(_ev_0))) : null)?.(_ev_0)))'
    )
