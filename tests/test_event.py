import pytest

from pynecone import event
from pynecone.event import Event, EventHandler, EventSpec
from pynecone.utils import format
from pynecone.vars import Var


def make_var(value) -> Var:
    """Make a variable.

    Args:
        value: The value of the var.

    Returns:
        The var.
    """
    var = Var.create(value)
    assert var is not None
    return var


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

    def test_fn_with_args(_, arg1, arg2):
        pass

    test_fn_with_args.__qualname__ = "test_fn_with_args"

    handler = EventHandler(fn=test_fn)
    event_spec = handler()

    assert event_spec.handler == handler
    assert event_spec.args == ()
    assert format.format_event(event_spec) == 'E("test_fn", {})'

    handler = EventHandler(fn=test_fn_with_args)
    event_spec = handler(make_var("first"), make_var("second"))

    # Test passing vars as args.
    assert event_spec.handler == handler
    assert event_spec.args == (("arg1", "first"), ("arg2", "second"))
    assert (
        format.format_event(event_spec)
        == 'E("test_fn_with_args", {arg1:first,arg2:second})'
    )

    # Passing args as strings should format differently.
    event_spec = handler("first", "second")  # type: ignore
    assert (
        format.format_event(event_spec)
        == 'E("test_fn_with_args", {arg1:"first",arg2:"second"})'
    )

    first, second = 123, "456"
    handler = EventHandler(fn=test_fn_with_args)
    event_spec = handler(first, second)  # type: ignore
    assert (
        format.format_event(event_spec)
        == 'E("test_fn_with_args", {arg1:123,arg2:"456"})'
    )

    assert event_spec.handler == handler
    assert event_spec.args == (
        ("arg1", format.json_dumps(first)),
        ("arg2", format.json_dumps(second)),
    )

    handler = EventHandler(fn=test_fn_with_args)
    with pytest.raises(TypeError):
        handler(test_fn)  # type: ignore


def test_event_redirect():
    """Test the event redirect function."""
    spec = event.redirect("/path")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_redirect"
    assert spec.args == (("path", "/path"),)
    assert format.format_event(spec) == 'E("_redirect", {path:"/path"})'
    spec = event.redirect(Var.create_safe("path"))
    assert format.format_event(spec) == 'E("_redirect", {path:path})'


def test_event_console_log():
    """Test the event console log function."""
    spec = event.console_log("message")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_console"
    assert spec.args == (("message", "message"),)
    assert format.format_event(spec) == 'E("_console", {message:"message"})'
    spec = event.console_log(Var.create_safe("message"))
    assert format.format_event(spec) == 'E("_console", {message:message})'


def test_event_window_alert():
    """Test the event window alert function."""
    spec = event.window_alert("message")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_alert"
    assert spec.args == (("message", "message"),)
    assert format.format_event(spec) == 'E("_alert", {message:"message"})'
    spec = event.window_alert(Var.create_safe("message"))
    assert format.format_event(spec) == 'E("_alert", {message:message})'


def test_set_value():
    """Test the event window alert function."""
    spec = event.set_value("input1", "")
    assert isinstance(spec, EventSpec)
    assert spec.handler.fn.__qualname__ == "_set_value"
    assert spec.args == (
        ("ref", Var.create_safe("ref_input1")),
        ("value", ""),
    )
    assert format.format_event(spec) == 'E("_set_value", {ref:ref_input1,value:""})'
    spec = event.set_value("input1", Var.create_safe("message"))
    assert (
        format.format_event(spec) == 'E("_set_value", {ref:ref_input1,value:message})'
    )
