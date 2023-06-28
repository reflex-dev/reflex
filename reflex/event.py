"""Define event classes to connect the frontend and backend."""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from reflex import constants
from reflex.base import Base
from reflex.utils import format
from reflex.vars import BaseVar, Var


class Event(Base):
    """An event that describes any state change in the app."""

    # The token to specify the client that the event is for.
    token: str

    # The event name.
    name: str

    # The routing data where event occurred
    router_data: Dict[str, Any] = {}

    # The event payload.
    payload: Dict[str, Any] = {}


class EventHandler(Base):
    """An event handler responds to an event to update the state."""

    # The function to call in response to the event.
    fn: Any

    class Config:
        """The Pydantic config."""

        # Needed to allow serialization of Callable.
        frozen = True

    def __call__(self, *args: Var) -> EventSpec:
        """Pass arguments to the handler to get an event spec.

        This method configures event handlers that take in arguments.

        Args:
            *args: The arguments to pass to the handler.

        Returns:
            The event spec, containing both the function and args.

        Raises:
            TypeError: If the arguments are invalid.
        """
        # Get the function args.
        fn_args = inspect.getfullargspec(self.fn).args[1:]
        fn_args = (Var.create_safe(arg) for arg in fn_args)

        # Construct the payload.
        values = []
        for arg in args:
            # Special case for file uploads.
            if isinstance(arg, FileUpload):
                return EventSpec(
                    handler=self,
                    client_handler_name="uploadFiles",
                )

            # Otherwise, convert to JSON.
            try:
                values.append(Var.create(arg, is_string=type(arg) is str))
            except TypeError as e:
                raise TypeError(
                    f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
                ) from e
        payload = tuple(zip(fn_args, values))

        # Return the event spec.
        return EventSpec(handler=self, args=payload)


class EventSpec(Base):
    """An event specification.

    Whereas an Event object is passed during runtime, a spec is used
    during compile time to outline the structure of an event.
    """

    # The event handler.
    handler: EventHandler

    # The handler on the client to process event.
    client_handler_name: str = ""

    # The arguments to pass to the function.
    args: Tuple[Tuple[Var, Var], ...] = ()

    class Config:
        """The Pydantic config."""

        # Required to allow tuple fields.
        frozen = True


class EventChain(Base):
    """Container for a chain of events that will be executed in order."""

    events: List[EventSpec]

    # Whether events are in fully controlled input.
    full_control: bool = False

    # State name when fully controlled.
    state_name: str = ""


class Target(Base):
    """A Javascript event target."""

    checked: bool = False
    value: Any = None


class FrontendEvent(Base):
    """A Javascript event."""

    target: Target = Target()
    key: str = ""
    value: Any = None


# The default event argument.
EVENT_ARG = BaseVar(name="_e", type_=FrontendEvent, is_local=True)


class FileUpload(Base):
    """Class to represent a file upload."""

    pass


# Special server-side events.
def server_side(name: str, sig: inspect.Signature, **kwargs) -> EventSpec:
    """A server-side event.

    Args:
        name: The name of the event.
        sig: The function signature of the event.
        **kwargs: The arguments to pass to the event.

    Returns:
        An event spec for a server-side event.
    """

    def fn():
        return None

    fn.__qualname__ = name
    fn.__signature__ = sig
    return EventSpec(
        handler=EventHandler(fn=fn),
        args=tuple(
            (Var.create_safe(k), Var.create_safe(v, is_string=type(v) is str))
            for k, v in kwargs.items()
        ),
    )


def redirect(path: Union[str, Var[str]]) -> EventSpec:
    """Redirect to a new path.

    Args:
        path: The path to redirect to.

    Returns:
        An event to redirect to the path.
    """
    return server_side("_redirect", get_fn_signature(redirect), path=path)


def console_log(message: Union[str, Var[str]]) -> EventSpec:
    """Do a console.log on the browser.

    Args:
        message: The message to log.

    Returns:
        An event to log the message.
    """
    return server_side("_console", get_fn_signature(console_log), message=message)


def window_alert(message: Union[str, Var[str]]) -> EventSpec:
    """Create a window alert on the browser.

    Args:
        message: The message to alert.

    Returns:
        An event to alert the message.
    """
    return server_side("_alert", get_fn_signature(window_alert), message=message)


def set_focus(ref: str) -> EventSpec:
    """Set focus to specified ref.

    Args:
        ref: The ref.

    Returns:
        An event to set focus on the ref
    """
    return server_side(
        "_set_focus",
        get_fn_signature(set_focus),
        ref=Var.create_safe(format.format_ref(ref)),
    )


def set_value(ref: str, value: Any) -> EventSpec:
    """Set the value of a ref.

    Args:
        ref: The ref.
        value: The value to set.

    Returns:
        An event to set the ref.
    """
    return server_side(
        "_set_value",
        get_fn_signature(set_value),
        ref=Var.create_safe(format.format_ref(ref)),
        value=value,
    )


def set_cookie(key: str, value: str) -> EventSpec:
    """Set a cookie on the frontend.

    Args:
        key: The key identifying the cookie.
        value: The value contained in the cookie.

    Returns:
        EventSpec: An event to set a cookie.
    """
    return server_side(
        "_set_cookie",
        get_fn_signature(set_cookie),
        key=key,
        value=value,
    )


def remove_cookie(key: str, options: Dict[str, Any] = {}) -> EventSpec:  # noqa: B006
    """Remove a cookie on the frontend.

    Args:
        key: The key identifying the cookie to be removed.
        options: Support all the cookie options from RFC 6265

    Returns:
        EventSpec: An event to remove a cookie.
    """
    return server_side(
        "_remove_cookie",
        get_fn_signature(remove_cookie),
        key=key,
        options=options,
    )


def set_local_storage(key: str, value: str) -> EventSpec:
    """Set a value in the local storage on the frontend.

    Args:
        key: The key identifying the variable in the local storage.
        value: The value contained in the local storage.

    Returns:
        EventSpec: An event to set a key-value in local storage.
    """
    return server_side(
        "_set_local_storage",
        get_fn_signature(set_local_storage),
        key=key,
        value=value,
    )


def clear_local_storage() -> EventSpec:
    """Set a value in the local storage on the frontend.

    Returns:
        EventSpec: An event to clear the local storage.
    """
    return server_side(
        "_clear_local_storage",
        get_fn_signature(clear_local_storage),
    )


def remove_local_storage(key: str) -> EventSpec:
    """Set a value in the local storage on the frontend.

    Args:
        key: The key identifying the variable in the local storage to remove.

    Returns:
        EventSpec: An event to remove an item based on the provided key in local storage.
    """
    return server_side(
        "_remove_local_storage",
        get_fn_signature(clear_local_storage),
        key=key,
    )


def set_clipboard(content: str) -> EventSpec:
    """Set the text in content in the clipboard.

    Args:
        content: The text to add to clipboard.

    Returns:
        EventSpec: An event to set some content in the clipboard.
    """
    return server_side(
        "_set_clipboard",
        get_fn_signature(set_clipboard),
        content=content,
    )


def get_event(state, event):
    """Get the event from the given state.

    Args:
        state: The state.
        event: The event.

    Returns:
        The event.
    """
    return f"{state.get_name()}.{event}"


def get_hydrate_event(state) -> str:
    """Get the name of the hydrate event for the state.

    Args:
        state: The state.

    Returns:
        The name of the hydrate event.
    """
    return get_event(state, constants.HYDRATE)


def call_event_handler(event_handler: EventHandler, arg: Var) -> EventSpec:
    """Call an event handler to get the event spec.

    This function will inspect the function signature of the event handler.
    If it takes in an arg, the arg will be passed to the event handler.
    Otherwise, the event handler will be called with no args.

    Args:
        event_handler: The event handler.
        arg: The argument to pass to the event handler.

    Returns:
        The event spec from calling the event handler.
    """
    args = inspect.getfullargspec(event_handler.fn).args
    if len(args) == 1:
        return event_handler()
    assert (
        len(args) == 2
    ), f"Event handler {event_handler.fn} must have 1 or 2 arguments."
    return event_handler(arg)


def call_event_fn(fn: Callable, arg: Var) -> List[EventSpec]:
    """Call a function to a list of event specs.

    The function should return either a single EventSpec or a list of EventSpecs.
    If the function takes in an arg, the arg will be passed to the function.
    Otherwise, the function will be called with no args.

    Args:
        fn: The function to call.
        arg: The argument to pass to the function.

    Returns:
        The event specs from calling the function.

    Raises:
        ValueError: If the lambda has an invalid signature.
    """
    # Import here to avoid circular imports.
    from reflex.event import EventHandler, EventSpec

    # Get the args of the lambda.
    args = inspect.getfullargspec(fn).args

    # Call the lambda.
    if len(args) == 0:
        out = fn()
    elif len(args) == 1:
        out = fn(arg)
    else:
        raise ValueError(f"Lambda {fn} must have 0 or 1 arguments.")

    # Convert the output to a list.
    if not isinstance(out, List):
        out = [out]

    # Convert any event specs to event specs.
    events = []
    for e in out:
        # Convert handlers to event specs.
        if isinstance(e, EventHandler):
            if len(args) == 0:
                e = e()
            elif len(args) == 1:
                e = e(arg)

        # Make sure the event spec is valid.
        if not isinstance(e, EventSpec):
            raise ValueError(f"Lambda {fn} returned an invalid event spec: {e}.")

        # Add the event spec to the chain.
        events.append(e)

    # Return the events.
    return events


def get_handler_args(event_spec: EventSpec, arg: Var) -> Tuple[Tuple[Var, Var], ...]:
    """Get the handler args for the given event spec.

    Args:
        event_spec: The event spec.
        arg: The controlled event argument.

    Returns:
        The handler args.
    """
    args = inspect.getfullargspec(event_spec.handler.fn).args

    return event_spec.args if len(args) > 1 else tuple()


def fix_events(
    events: Optional[List[Union[EventHandler, EventSpec]]], token: str
) -> List[Event]:
    """Fix a list of events returned by an event handler.

    Args:
        events: The events to fix.
        token: The user token.

    Returns:
        The fixed events.
    """
    # If the event handler returns nothing, return an empty list.
    if events is None:
        return []

    # If the handler returns a single event, wrap it in a list.
    if not isinstance(events, List):
        events = [events]

    # Fix the events created by the handler.
    out = []
    for e in events:
        if not isinstance(e, (EventHandler, EventSpec)):
            e = EventHandler(fn=e)
        # Otherwise, create an event from the event spec.
        if isinstance(e, EventHandler):
            e = e()
        assert isinstance(e, EventSpec), f"Unexpected event type, {type(e)}."
        name = format.format_event_handler(e.handler)
        payload = {k.name: v.name for k, v in e.args}

        # Create an event and append it to the list.
        out.append(
            Event(
                token=token,
                name=name,
                payload=payload,
            )
        )

    return out


def get_fn_signature(fn: Callable) -> inspect.Signature:
    """Get the signature of a function.

    Args:
        fn: The function.

    Returns:
        The signature of the function.
    """
    signature = inspect.signature(fn)
    new_param = inspect.Parameter(
        "state", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Any
    )
    return signature.replace(parameters=(new_param, *signature.parameters.values()))


# A set of common event triggers.
EVENT_TRIGGERS: Set[str] = {
    "on_focus",
    "on_blur",
    "on_click",
    "on_context_menu",
    "on_double_click",
    "on_mouse_down",
    "on_mouse_enter",
    "on_mouse_leave",
    "on_mouse_move",
    "on_mouse_out",
    "on_mouse_over",
    "on_mouse_up",
    "on_scroll",
}
