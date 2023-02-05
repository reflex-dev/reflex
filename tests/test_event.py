from pynecone.event import Event, EventHandler
from pynecone.var import Var


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

    def test_fn_with_args(_, arg1, arg2):
        pass

    handler = EventHandler(fn=test_fn)
    event_spec = handler()

    assert event_spec.handler == handler
    assert event_spec.local_args == ()
    assert event_spec.args == ()

    handler = EventHandler(fn=test_fn_with_args)
    event_spec = handler(make_var("first"), make_var("second"))

    assert event_spec.handler == handler
    assert event_spec.local_args == ()
    assert event_spec.args == (("arg1", "first"), ("arg2", "second"))
