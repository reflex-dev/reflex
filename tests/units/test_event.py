import json
from collections.abc import Callable

import pytest

import reflex as rx
from reflex.constants.compiler import Hooks, Imports
from reflex.event import (
    BACKGROUND_TASK_MARKER,
    Event,
    EventChain,
    EventHandler,
    EventSpec,
    call_event_handler,
    event,
    fix_events,
)
from reflex.state import BaseState
from reflex.utils import format
from reflex.vars.base import Field, LiteralVar, Var, VarData, field


def make_var(value) -> Var:
    """Make a variable.

    Args:
        value: The value of the var.

    Returns:
        The var.
    """
    return Var(_js_expr=value)


def test_create_event():
    """Test creating an event."""
    event = Event(token="token", name="state.do_thing", payload={"arg": "value"})
    assert event.token == "token"
    assert event.name == "state.do_thing"
    assert event.payload == {"arg": "value"}


def test_call_event_handler():
    """Test that calling an event handler creates an event spec."""

    def test_fn():
        pass

    test_fn.__qualname__ = "test_fn"

    def fn_with_args(_, arg1, arg2):
        pass

    fn_with_args.__qualname__ = "fn_with_args"

    handler = EventHandler(fn=test_fn)
    event_spec = handler()

    assert event_spec.handler == handler
    assert event_spec.args == ()
    assert format.format_event(event_spec) == 'ReflexEvent("test_fn", {})'

    handler = EventHandler(fn=fn_with_args)
    event_spec = handler(make_var("first"), make_var("second"))

    # Test passing vars as args.
    assert event_spec.handler == handler
    assert event_spec.args[0][0].equals(Var(_js_expr="arg1"))
    assert event_spec.args[0][1].equals(Var(_js_expr="first"))
    assert event_spec.args[1][0].equals(Var(_js_expr="arg2"))
    assert event_spec.args[1][1].equals(Var(_js_expr="second"))
    assert (
        format.format_event(event_spec)
        == 'ReflexEvent("fn_with_args", {arg1:first,arg2:second})'
    )

    # Passing args as strings should format differently.
    event_spec = handler("first", "second")
    assert (
        format.format_event(event_spec)
        == 'ReflexEvent("fn_with_args", {arg1:"first",arg2:"second"})'
    )

    first, second = 123, "456"
    handler = EventHandler(fn=fn_with_args)
    event_spec = handler(first, second)
    assert (
        format.format_event(event_spec)
        == 'ReflexEvent("fn_with_args", {arg1:123,arg2:"456"})'
    )

    assert event_spec.handler == handler
    assert event_spec.args[0][0].equals(Var(_js_expr="arg1"))
    assert event_spec.args[0][1].equals(LiteralVar.create(first))
    assert event_spec.args[1][0].equals(Var(_js_expr="arg2"))
    assert event_spec.args[1][1].equals(LiteralVar.create(second))

    handler = EventHandler(fn=fn_with_args)
    with pytest.raises(TypeError):
        handler(test_fn)


def test_call_event_handler_partial():
    """Calling an EventHandler with incomplete args returns an EventSpec that can be extended."""

    def fn_with_args(_, arg1, arg2):
        pass

    fn_with_args.__qualname__ = "fn_with_args"

    def spec(a2: Var[str]) -> list[Var[str]]:
        return [a2]

    handler = EventHandler(fn=fn_with_args, state_full_name="BigState")
    event_spec = handler(make_var("first"))
    event_spec2 = call_event_handler(event_spec, spec)

    assert event_spec.handler == handler
    assert len(event_spec.args) == 1
    assert event_spec.args[0][0].equals(Var(_js_expr="arg1"))
    assert event_spec.args[0][1].equals(Var(_js_expr="first"))
    assert (
        format.format_event(event_spec)
        == 'ReflexEvent("BigState.fn_with_args", {arg1:first})'
    )

    assert event_spec2 is not event_spec
    assert event_spec2.handler == handler
    assert len(event_spec2.args) == 2
    assert event_spec2.args[0][0].equals(Var(_js_expr="arg1"))
    assert event_spec2.args[0][1].equals(Var(_js_expr="first"))
    assert event_spec2.args[1][0].equals(Var(_js_expr="arg2"))
    assert event_spec2.args[1][1].equals(Var(_js_expr="_a2", _var_type=str))
    assert (
        format.format_event(event_spec2)
        == 'ReflexEvent("BigState.fn_with_args", {arg1:first,arg2:_a2})'
    )


@pytest.mark.parametrize(
    ("arg1", "arg2"),
    [
        (1, 2),
        (1, "2"),
        ({"a": 1}, {"b": 2}),
    ],
)
def test_fix_events(arg1, arg2):
    """Test that chaining an event handler with args formats the payload correctly.

    Args:
        arg1: The first arg passed to the handler.
        arg2: The second arg passed to the handler.
    """

    def fn_with_args(_, arg1, arg2):
        pass

    fn_with_args.__qualname__ = "fn_with_args"

    handler = EventHandler(fn=fn_with_args)
    event_spec = handler(arg1, arg2)
    event = fix_events([event_spec], token="foo")[0]
    assert event.name == fn_with_args.__qualname__
    assert event.token == "foo"
    assert event.payload == {"arg1": arg1, "arg2": arg2}


@pytest.mark.parametrize(
    ("input", "output"),
    [
        (
            (path, is_external, replace, popup),
            f'ReflexEvent("_redirect", {{path:{json.dumps(path) if isinstance(path, str) else path._js_expr},external:{"true" if is_external else "false"},popup:{"true" if popup else "false"},replace:{"true" if replace else "false"}}})',
        )
        for path in ("/path", Var(_js_expr="path"))
        for is_external in (None, True, False)
        for replace in (None, True, False)
        for popup in (None, True, False)
    ],
)
def test_event_redirect(input, output):
    """Test the event redirect function.

    Args:
        input: The input for running the test.
        output: The expected output to validate the test.
    """
    path, is_external, replace, popup = input
    kwargs = {}
    if is_external is not None:
        kwargs["is_external"] = is_external
    if replace is not None:
        kwargs["replace"] = replace
    if popup is not None:
        kwargs["popup"] = popup
    spec = event.redirect(path, **kwargs)
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_redirect"
    assert format.format_event(spec) == output


def test_event_console_log():
    """Test the event console log function."""
    spec = event.console_log("message")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_call_function"
    assert spec.args[0][0].equals(Var(_js_expr="function"))
    assert spec.args[0][1].equals(
        Var('(() => (console["log"]("message")))', _var_type=Callable)
    )
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_call_function", {function:(() => (console["log"]("message"))),callback:null})'
    )
    spec = event.console_log(Var(_js_expr="message"))
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_call_function", {function:(() => (console["log"](message))),callback:null})'
    )
    spec2 = event.console_log(Var(_js_expr="message2")).add_args(Var("throwaway"))
    assert (
        format.format_event(spec2)
        == 'ReflexEvent("_call_function", {function:(() => (console["log"](message2))),callback:null})'
    )


def test_event_window_alert():
    """Test the event window alert function."""
    spec = event.window_alert("message")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_call_function"
    assert spec.args[0][0].equals(Var(_js_expr="function"))
    assert spec.args[0][1].equals(
        Var('(() => (window["alert"]("message")))', _var_type=Callable)
    )
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_call_function", {function:(() => (window["alert"]("message"))),callback:null})'
    )
    spec = event.window_alert(Var(_js_expr="message"))
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_call_function", {function:(() => (window["alert"](message))),callback:null})'
    )
    spec2 = event.window_alert(Var(_js_expr="message2")).add_args(Var("throwaway"))
    assert (
        format.format_event(spec2)
        == 'ReflexEvent("_call_function", {function:(() => (window["alert"](message2))),callback:null})'
    )


@pytest.mark.parametrize(
    ("func", "qualname"), [("set_focus", "_set_focus"), ("blur_focus", "_blur_focus")]
)
def test_focus(func: str, qualname: str):
    """Test the event set focus function.

    Args:
        func: The event function name.
        qualname: The sig qual name passed to JS.
    """
    spec = getattr(event, func)("input1")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == qualname
    assert spec.args[0][0].equals(Var(_js_expr="ref"))
    assert spec.args[0][1].equals(LiteralVar.create("ref_input1"))
    assert (
        format.format_event(spec) == f'ReflexEvent("{qualname}", {{ref:"ref_input1"}})'
    )
    spec = getattr(event, func)("input1")
    assert (
        format.format_event(spec) == f'ReflexEvent("{qualname}", {{ref:"ref_input1"}})'
    )


def test_set_value():
    """Test the event window alert function."""
    spec = event.set_value("input1", "")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_set_value"
    assert spec.args[0][0].equals(Var(_js_expr="ref"))
    assert spec.args[0][1].equals(LiteralVar.create("ref_input1"))
    assert spec.args[1][0].equals(Var(_js_expr="value"))
    assert spec.args[1][1].equals(LiteralVar.create(""))
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_set_value", {ref:"ref_input1",value:""})'
    )
    spec = event.set_value("input1", Var(_js_expr="message"))
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_set_value", {ref:"ref_input1",value:message})'
    )


def test_remove_cookie():
    """Test the event remove_cookie."""
    spec = event.remove_cookie("testkey")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_remove_cookie"
    assert spec.args[0][0].equals(Var(_js_expr="key"))
    assert spec.args[0][1].equals(LiteralVar.create("testkey"))
    assert spec.args[1][0].equals(Var(_js_expr="options"))
    assert spec.args[1][1].equals(LiteralVar.create({"path": "/"}))
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_remove_cookie", {key:"testkey",options:({ ["path"] : "/" })})'
    )


def test_remove_cookie_with_options():
    """Test the event remove_cookie with options."""
    options = {
        "path": "/foo",
        "domain": "example.com",
        "secure": True,
        "sameSite": "strict",
    }
    spec = event.remove_cookie("testkey", options)
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_remove_cookie"
    assert spec.args[0][0].equals(Var(_js_expr="key"))
    assert spec.args[0][1].equals(LiteralVar.create("testkey"))
    assert spec.args[1][0].equals(Var(_js_expr="options"))
    assert spec.args[1][1].equals(LiteralVar.create(options))
    assert (
        format.format_event(spec)
        == f'ReflexEvent("_remove_cookie", {{key:"testkey",options:{LiteralVar.create(options)!s}}})'
    )


def test_clear_local_storage():
    """Test the event clear_local_storage."""
    spec = event.clear_local_storage()
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_clear_local_storage"
    assert not spec.args
    assert format.format_event(spec) == 'ReflexEvent("_clear_local_storage", {})'


def test_remove_local_storage():
    """Test the event remove_local_storage."""
    spec = event.remove_local_storage("testkey")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_remove_local_storage"
    assert spec.args[0][0].equals(Var(_js_expr="key"))
    assert spec.args[0][1].equals(LiteralVar.create("testkey"))
    assert (
        format.format_event(spec)
        == 'ReflexEvent("_remove_local_storage", {key:"testkey"})'
    )


def test_event_actions():
    """Test DOM event actions, like stopPropagation and preventDefault."""
    # EventHandler
    handler = EventHandler(fn=lambda: None)
    assert not handler.event_actions
    sp_handler = handler.stop_propagation
    assert handler is not sp_handler
    assert sp_handler.event_actions == {"stopPropagation": True}
    pd_handler = handler.prevent_default
    assert handler is not pd_handler
    assert pd_handler.event_actions == {"preventDefault": True}
    both_handler = sp_handler.prevent_default
    assert both_handler is not sp_handler
    assert both_handler.event_actions == {
        "stopPropagation": True,
        "preventDefault": True,
    }

    throttle_handler = handler.throttle(300)
    assert handler is not throttle_handler
    assert throttle_handler.event_actions == {"throttle": 300}

    debounce_handler = handler.debounce(300)
    assert handler is not debounce_handler
    assert debounce_handler.event_actions == {"debounce": 300}

    all_handler = handler.stop_propagation.prevent_default.throttle(200).debounce(100)
    assert handler is not all_handler
    assert all_handler.event_actions == {
        "stopPropagation": True,
        "preventDefault": True,
        "throttle": 200,
        "debounce": 100,
    }

    assert not handler.event_actions

    # Convert to EventSpec should carry event actions
    sp_handler2 = handler.stop_propagation.throttle(200)
    spec = sp_handler2()
    assert spec.event_actions == {"stopPropagation": True, "throttle": 200}
    assert spec.event_actions == sp_handler2.event_actions
    assert spec.event_actions is not sp_handler2.event_actions
    # But it should be a copy!
    assert spec.event_actions is not sp_handler2.event_actions
    spec2 = spec.prevent_default
    assert spec is not spec2
    assert spec2.event_actions == {
        "stopPropagation": True,
        "preventDefault": True,
        "throttle": 200,
    }
    assert spec2.event_actions != spec.event_actions

    # The original handler should still not be touched.
    assert not handler.event_actions


def test_event_actions_on_state():
    class EventActionState(BaseState):
        def handler(self):
            pass

    handler = EventActionState.handler
    assert isinstance(handler, EventHandler)
    assert not handler.event_actions

    sp_handler = EventActionState.handler.stop_propagation  # pyright: ignore [reportFunctionMemberAccess]
    assert sp_handler.event_actions == {"stopPropagation": True}
    # should NOT affect other references to the handler
    assert not handler.event_actions


def test_event_var_data():
    class S(BaseState):
        x: Field[int] = field(0)

        @event
        def s(self, value: int):
            pass

        @event
        def s2(self):
            pass

    # Handler doesn't have any _var_data because it's just a str
    handler_var = Var.create(S.s2)
    assert handler_var._get_all_var_data() is None

    # Ensure spec carries _var_data
    spec_var = Var.create(S.s(S.x))
    assert spec_var._get_all_var_data() == S.x._get_all_var_data()

    # Needed to instantiate the EventChain
    def _args_spec(value: Var[int]) -> tuple[Var[int]]:
        return (value,)

    # Ensure chain carries _var_data
    chain_var = Var.create(
        EventChain(
            events=[S.s(S.x)],
            args_spec=_args_spec,
            invocation=rx.vars.FunctionStringVar.create(""),
        )
    )
    assert chain_var._get_all_var_data() == S.x._get_all_var_data()

    chain_var_data = Var.create(
        EventChain(
            events=[],
            args_spec=_args_spec,
        )
    )._get_all_var_data()
    assert chain_var_data is not None

    assert chain_var_data == VarData(
        imports=Imports.EVENTS,
        hooks={Hooks.EVENTS: None},
    )


def test_event_bound_method() -> None:
    class S(BaseState):
        @event
        def e(self, arg: str):
            print(arg)

    class Wrapper:
        def get_handler(self, arg: Var[str]):
            return S.e(arg)

    w = Wrapper()
    _ = rx.input(on_change=w.get_handler)


def test_event_decorator_with_event_actions():
    """Test that @rx.event decorator can accept event action parameters."""

    class MyTestState(BaseState):
        # Test individual event actions
        @event(stop_propagation=True)
        def handle_stop_prop(self):
            pass

        @event(prevent_default=True)
        def handle_prevent_default(self):
            pass

        @event(throttle=500)
        def handle_throttle(self):
            pass

        @event(debounce=300)
        def handle_debounce(self):
            pass

        @event(temporal=True)
        def handle_temporal(self):
            pass

        # Test multiple event actions combined
        @event(stop_propagation=True, prevent_default=True, throttle=1000)
        def handle_multiple(self):
            pass

        # Test with background parameter (existing functionality)
        @event(background=True, temporal=True)
        async def handle_background_temporal(self):
            pass

        # Test no event actions (existing behavior)
        @event
        def handle_no_actions(self):
            pass

    # Test individual event actions are applied
    stop_prop_handler = MyTestState.handle_stop_prop
    assert isinstance(stop_prop_handler, EventHandler)
    assert stop_prop_handler.event_actions == {"stopPropagation": True}

    prevent_default_handler = MyTestState.handle_prevent_default
    assert prevent_default_handler.event_actions == {"preventDefault": True}

    throttle_handler = MyTestState.handle_throttle
    assert throttle_handler.event_actions == {"throttle": 500}

    debounce_handler = MyTestState.handle_debounce
    assert debounce_handler.event_actions == {"debounce": 300}

    temporal_handler = MyTestState.handle_temporal
    assert temporal_handler.event_actions == {"temporal": True}

    # Test multiple event actions are combined correctly
    multiple_handler = MyTestState.handle_multiple
    assert multiple_handler.event_actions == {
        "stopPropagation": True,
        "preventDefault": True,
        "throttle": 1000,
    }

    # Test background + event actions work together
    bg_temporal_handler = MyTestState.handle_background_temporal
    assert bg_temporal_handler.event_actions == {"temporal": True}
    assert hasattr(bg_temporal_handler.fn, BACKGROUND_TASK_MARKER)  # pyright: ignore [reportAttributeAccessIssue]

    # Test no event actions (existing behavior preserved)
    no_actions_handler = MyTestState.handle_no_actions
    assert no_actions_handler.event_actions == {}


def test_event_decorator_actions_can_be_overridden():
    """Test that decorator event actions can still be overridden by chaining."""

    class MyTestState(BaseState):
        @event(throttle=500, stop_propagation=True)
        def handle_with_defaults(self):
            pass

    # Get the handler with default actions
    handler = MyTestState.handle_with_defaults
    assert handler.event_actions == {"throttle": 500, "stopPropagation": True}

    # Chain additional actions - should combine
    handler_with_prevent_default = handler.prevent_default
    assert handler_with_prevent_default.event_actions == {
        "throttle": 500,
        "stopPropagation": True,
        "preventDefault": True,
    }

    # Chain throttle with different value - should override
    handler_with_new_throttle = handler.throttle(1000)
    assert handler_with_new_throttle.event_actions == {
        "throttle": 1000,  # New value overrides default
        "stopPropagation": True,
    }

    # Original handler should be unchanged
    assert handler.event_actions == {"throttle": 500, "stopPropagation": True}


def test_event_decorator_with_none_values():
    """Test that None values in decorator don't create event actions."""

    class MyTestState(BaseState):
        @event(stop_propagation=None, prevent_default=None, throttle=None)
        def handle_all_none(self):
            pass

        @event(stop_propagation=True, prevent_default=None, throttle=500, debounce=None)
        def handle_mixed(self):
            pass

    # All None should result in no event actions
    all_none_handler = MyTestState.handle_all_none
    assert all_none_handler.event_actions == {}

    # Only non-None values should be included
    mixed_handler = MyTestState.handle_mixed
    assert mixed_handler.event_actions == {"stopPropagation": True, "throttle": 500}


def test_event_decorator_backward_compatibility():
    """Test that existing code without event action parameters continues to work."""

    class MyTestState(BaseState):
        @event
        def handle_old_style(self):
            pass

        @event(background=True)
        async def handle_old_background(self):
            pass

    # Old style without parameters should work unchanged
    old_handler = MyTestState.handle_old_style
    assert isinstance(old_handler, EventHandler)
    assert old_handler.event_actions == {}
    assert not hasattr(old_handler.fn, BACKGROUND_TASK_MARKER)  # pyright: ignore [reportAttributeAccessIssue]

    # Old background parameter should work unchanged
    bg_handler = MyTestState.handle_old_background
    assert bg_handler.event_actions == {}
    assert hasattr(bg_handler.fn, BACKGROUND_TASK_MARKER)  # pyright: ignore [reportAttributeAccessIssue]


def test_event_var_in_rx_cond():
    """Test that EventVar and EventChainVar cannot be used in rx.cond()."""
    from reflex.components.core.cond import cond as rx_cond

    class S(BaseState):
        @event
        def s(self):
            pass

    handler_var = Var.create(S.s)
    with pytest.raises(TypeError) as err:
        rx_cond(handler_var, rx.text("True"), rx.text("False"))
    assert "Cannot convert" in str(err.value)
    assert "to bool" in str(err.value)

    def _args_spec() -> tuple:
        return ()

    chain_var = Var.create(
        EventChain(
            events=[S.s()],
            args_spec=_args_spec,
        )
    )
    with pytest.raises(TypeError) as err:
        rx_cond(chain_var, rx.text("True"), rx.text("False"))
    assert "Cannot convert" in str(err.value)
    assert "to bool" in str(err.value)


def test_decentralized_event_with_args():
    """Test the decentralized event."""

    class S(BaseState):
        field: Field[str] = field("")

    @event
    def e(s: S, arg: str):
        s.field = arg

    _ = rx.input(on_change=e("foo"))


def test_decentralized_event_no_args():
    """Test the decentralized event with no args."""

    class S(BaseState):
        field: Field[str] = field("")

    @event
    def e(s: S):
        s.field = "foo"

    _ = rx.input(on_change=e())
    _ = rx.input(on_change=e)


class GlobalState(BaseState):
    """Global state for testing decentralized events."""

    field: Field[str] = field("")


@event
def f(s: GlobalState, arg: str):
    s.field = arg


def test_decentralized_event_global_state():
    """Test the decentralized event with a global state."""
    _ = rx.input(on_change=f("foo"))
    _ = rx.input(on_change=f)
