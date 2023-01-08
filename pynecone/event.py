"""Define event classes to connect the frontend and backend."""
from __future__ import annotations

import inspect
import json
from typing import Any, Callable, Dict, List, Set, Tuple

from pynecone.base import Base
from pynecone.var import BaseVar, Var


class Event(Base):
    """An event that describes any state change in the app."""

    # The token to specify the client that the event is for.
    token: str

    # The event name.
    name: str

    # The routing data where event occured
    router_data: Dict[str, Any] = {}

    # The event payload.
    payload: Dict[str, Any] = {}


class EventHandler(Base):
    """An event handler responds to an event to update the state."""

    # The function to call in response to the event.
    fn: Callable

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

        # Construct the payload.
        values = []
        for arg in args:
            # If it is a Var, add the full name.
            if isinstance(arg, Var):
                values.append(arg.full_name)
                continue

            # Otherwise, convert to JSON.
            try:
                values.append(json.dumps(arg))
            except TypeError:
                raise TypeError(
                    f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
                )
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

    # The local arguments on the frontend.
    local_args: Tuple[str, ...] = ()

    # The arguments to pass to the function.
    args: Tuple[Any, ...] = ()

    class Config:
        """The Pydantic config."""

        # Required to allow tuple fields.
        frozen = True


class EventChain(Base):
    """Container for a chain of events that will be executed in order."""

    events: List[EventSpec]


class Target(Base):
    """A Javascript event target."""

    checked: bool = False
    value: Any = None


class FrontendEvent(Base):
    """A Javascript event."""

    target: Target = Target()


# The default event argument.
EVENT_ARG = BaseVar(name="_e", type_=FrontendEvent, is_local=True)


# Special server-side events.
def redirect(path: str) -> Event:
    """Redirect to a new path.

    Args:
        path: The path to redirect to.

    Returns:
        An event to redirect to the path.
    """
    return Event(
        token="",
        name="_redirect",
        payload={"path": path},
    )


def console_log(message: str) -> Event:
    """Do a console.log on the browser.

    Args:
        message: The message to log.

    Returns:
        An event to log the message.
    """
    return Event(
        token="",
        name="_console",
        payload={"message": message},
    )


def window_alert(message: str) -> Event:
    """Create a window alert on the browser.

    Args:
        message: The message to alert.

    Returns:
        An event to alert the message.
    """
    return Event(
        token="",
        name="_alert",
        payload={"message": message},
    )


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
