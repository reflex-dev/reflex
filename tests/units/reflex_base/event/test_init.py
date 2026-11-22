"""Tests for trigger-argument placeholders and the event chains built on them."""

from typing import Any, cast

import pytest
from reflex_base.client_state import client_state
from reflex_base.event import (
    EventArgVar,
    EventChain,
    EventHandler,
    EventSpec,
    LambdaEventCallback,
    call_event_fn,
    call_event_handler,
    event_arg_placeholder,
    event_args_signature,
    no_args_event_spec,
    parse_args_spec,
    passthrough_event_spec,
)
from reflex_base.utils.exceptions import EventFnArgMismatchError
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


def test_call_event_fn_passes_every_trigger_argument_to_varargs() -> None:
    """A callable taking ``*args`` gets all of a trigger's arguments, however many.

    ``*args`` is not a required argument, so a trigger with none is valid too.
    """
    received: list[tuple[str, ...]] = []

    def record(*args: Var) -> EventSpec:
        received.append(tuple(str(arg) for arg in args))
        return rx.noop()

    def no_args() -> list[Var]:
        return []

    call_event_fn(record, no_args, key="on_mount")
    call_event_fn(record, lambda a, b: [a, b], key="on_resize")
    assert received == [(), ("_a", "_b")]


def test_call_event_fn_passes_only_positional_arguments() -> None:
    """Keyword-only and ``**kwargs`` parameters take none of the trigger's arguments."""
    received: list[tuple[str, ...]] = []

    def record_kwargs(key: Var, **kwargs: Any) -> EventSpec:
        received.append((str(key), *kwargs))
        return rx.noop()

    def record_keyword_only(key: Var, *, flag: int = 1) -> EventSpec:
        received.append((str(key), str(flag)))
        return rx.noop()

    call_event_fn(record_kwargs, lambda a, b: [a, b], key="on_key_down")
    call_event_fn(record_keyword_only, lambda a, b: [a, b], key="on_key_down")
    assert received == [("_a",), ("_a", "1")]


class KeywordOnlyState(rx.State):
    """A state whose handler takes a keyword-only argument no trigger passes."""

    def handle(self, value: str, *, required: str):
        """Take the trigger's value and an argument it never sends.

        Args:
            value: The trigger's value.
            required: An argument no trigger passes.
        """


def test_a_required_keyword_only_parameter_of_a_handler_still_counts_as_required() -> (
    None
):
    """An event handler's arguments are sent by name, so the trigger must supply it."""
    with pytest.raises(EventFnArgMismatchError) as error:
        call_event_handler(
            cast(EventHandler, KeywordOnlyState.handle),
            lambda value: [value],
            key="on_change",
        )

    assert str(error.value) == (
        "Event on_change only provides 1 arguments, but "
        "KeywordOnlyState.handle requires at least 2 arguments to be passed to "
        "the event handler.\nSee https://reflex.dev/docs/events/event-arguments/"
    )


def test_a_callable_with_a_required_keyword_only_parameter_is_rejected() -> None:
    """A callable gets the trigger's arguments by position, so it never gets one.

    It is rejected however many arguments the trigger provides.
    """

    def record(value: Var, *, required: str) -> EventSpec:
        return rx.noop()

    with pytest.raises(EventFnArgMismatchError) as error:
        call_event_fn(record, lambda a, b: [a, b], key="on_change")

    assert str(error.value) == (
        f"Event on_change cannot pass the keyword-only argument 'required' of "
        f"{record}: a function given to an event trigger gets the trigger's "
        "arguments by position only. Give 'required' a default value, or move it "
        "before the `*` so it takes one of the trigger's arguments.\n"
        "See https://reflex.dev/docs/events/event-arguments/"
    )
