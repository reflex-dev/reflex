"""Tests for trigger-argument placeholders and the event chains built on them."""

from typing import Any, cast

import pytest
from reflex_base.client_state import client_state
from reflex_base.event import (
    EventArgVar,
    EventChain,
    LambdaEventCallback,
    _BrowserCallSpec,
    event_arg_placeholder,
    event_args_signature,
    no_args_event_spec,
    parse_args_spec,
    passthrough_event_spec,
)
from reflex_base.utils.exceptions import EventHandlerValueError
from reflex_base.utils.types import Unset
from reflex_base.vars.base import LiteralVar, Var
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


def test_script_events_keep_their_timeout_off_the_wire():
    """A script event's timeout stays on the spec: neither its payload nor its compiled trigger has it."""
    specs = cast(
        "list[_BrowserCallSpec]",
        [
            rx.call_script("1", timeout=5),
            rx.call_function("() => 1", timeout=None),
            rx.run_script("2", timeout=1.5),
        ],
    )
    assert [(spec._to_event().payload, spec.timeout) for spec in specs] == [
        ({"javascript_code": "1", "callback": None}, 5),
        ({"function": "() => 1", "callback": None}, None),
        ({"function": "(() => 2)", "callback": None}, 1.5),
    ]
    assert str(LiteralVar.create(specs[0])) == (
        '(ReflexEvent("_call_script", ({ ["javascript_code"] : "1", '
        '["callback"] : null }), ({  })))'
    )
    assert isinstance(cast("_BrowserCallSpec", rx.call_script("1")).timeout, Unset)


def test_copies_of_a_script_event_keep_its_timeout():
    """A copy with new args or event actions is still awaitable with the same timeout."""
    spec = cast("_BrowserCallSpec", rx.call_script("1", timeout=5))
    copies = [
        spec.with_args(spec.args),
        spec.add_args(),
        spec.stop_propagation,
        spec.debounce(10),
    ]
    assert [(type(copy), copy.timeout) for copy in copies] == [
        (_BrowserCallSpec, 5)
    ] * 4


@pytest.mark.parametrize(
    "timeout", [0, -5, float("inf"), float("nan"), True, "30"], ids=repr
)
@pytest.mark.parametrize("script", [rx.call_script, rx.call_function, rx.run_script])
def test_script_events_reject_a_timeout_that_is_not_positive_seconds(
    script: Any, timeout: Any
):
    """A call's timeout follows the rule of browser_call_timeout, checked as the event is built.

    Args:
        script: The function building the script event.
        timeout: The invalid timeout.
    """
    with pytest.raises(EventHandlerValueError) as err:
        script("1", timeout=timeout)
    assert str(err.value) == (
        f"timeout is {timeout!r}, but awaited browser calls need a positive, "
        "finite number of seconds to wait for a result. Set timeout to a number "
        "of seconds such as 30, or to None to wait without a limit."
    )
