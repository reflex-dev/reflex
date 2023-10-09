"""Define event classes to connect the frontend and backend."""
from __future__ import annotations

import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from reflex import constants
from reflex.base import Base
from reflex.utils import console, format
from reflex.utils.types import ArgsSpec
from reflex.vars import BaseVar, Var

if TYPE_CHECKING:
    from reflex.state import State


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


BACKGROUND_TASK_MARKER = "_reflex_background_task"


def background(fn):
    """Decorator to mark event handler as running in the background.

    Args:
        fn: The function to decorate.

    Returns:
        The same function, but with a marker set.


    Raises:
        TypeError: If the function is not a coroutine function or async generator.
    """
    if not inspect.iscoroutinefunction(fn) and not inspect.isasyncgenfunction(fn):
        raise TypeError("Background task must be async function or generator.")
    setattr(fn, BACKGROUND_TASK_MARKER, True)
    return fn


def _no_chain_background_task(
    state_cls: Type["State"], name: str, fn: Callable
) -> Callable:
    """Protect against directly chaining a background task from another event handler.

    Args:
        state_cls: The state class that the event handler is in.
        name: The name of the background task.
        fn: The background task coroutine function / generator.

    Returns:
        A compatible coroutine function / generator that raises a runtime error.

    Raises:
        TypeError: If the background task is not async.
    """
    call = f"{state_cls.__name__}.{name}"
    message = (
        f"Cannot directly call background task {name!r}, use "
        f"`yield {call}` or `return {call}` instead."
    )
    if inspect.iscoroutinefunction(fn):

        async def _no_chain_background_task_co(*args, **kwargs):
            raise RuntimeError(message)

        return _no_chain_background_task_co
    if inspect.isasyncgenfunction(fn):

        async def _no_chain_background_task_gen(*args, **kwargs):
            yield
            raise RuntimeError(message)

        return _no_chain_background_task_gen

    raise TypeError(f"{fn} is marked as a background task, but is not async.")


class EventHandler(Base):
    """An event handler responds to an event to update the state."""

    # The function to call in response to the event.
    fn: Any

    class Config:
        """The Pydantic config."""

        # Needed to allow serialization of Callable.
        frozen = True

    @property
    def is_background(self) -> bool:
        """Whether the event handler is a background task.

        Returns:
            True if the event handler is marked as a background task.
        """
        return getattr(self.fn, BACKGROUND_TASK_MARKER, False)

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
                    # `files` is defined in the Upload component's _use_hooks
                    args=((Var.create_safe("files"), Var.create_safe("files")),),
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

    args_spec: Optional[Callable]


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


def redirect(path: str | Var[str], external: Optional[bool] = False) -> EventSpec:
    """Redirect to a new path.

    Args:
        path: The path to redirect to.
        external: Whether to open in new tab or not.

    Returns:
        An event to redirect to the path.
    """
    return server_side(
        "_redirect", get_fn_signature(redirect), path=path, external=external
    )


def console_log(message: str | Var[str]) -> EventSpec:
    """Do a console.log on the browser.

    Args:
        message: The message to log.

    Returns:
        An event to log the message.
    """
    return server_side("_console", get_fn_signature(console_log), message=message)


def window_alert(message: str | Var[str]) -> EventSpec:
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
    console.deprecate(
        feature_name=f"rx.set_cookie",
        reason="and has been replaced by rx.Cookie, which can be used as a state var",
        deprecation_version="0.2.9",
        removal_version="0.3.0",
    )
    return server_side(
        "_set_cookie",
        get_fn_signature(set_cookie),
        key=key,
        value=value,
    )


def remove_cookie(key: str, options: dict[str, Any] = {}) -> EventSpec:  # noqa: B006
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
    console.deprecate(
        feature_name=f"rx.set_local_storage",
        reason="and has been replaced by rx.LocalStorage, which can be used as a state var",
        deprecation_version="0.2.9",
        removal_version="0.3.0",
    )
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


def download(url: str, filename: Optional[str] = None) -> EventSpec:
    """Download the file at a given path.

    Args:
        url : The URL to the file to download.
        filename : The name that the file should be saved as after download.

    Raises:
        ValueError: If the URL provided is invalid.

    Returns:
        EventSpec: An event to download the associated file.
    """
    if not url.startswith("/"):
        raise ValueError("The URL argument should start with a /")

    # if filename is not provided, infer it from url
    if filename is None:
        filename = url.rpartition("/")[-1]

    return server_side(
        "_download",
        get_fn_signature(download),
        url=url,
        filename=filename,
    )


def call_script(javascript_code: str) -> EventSpec:
    """Create an event handler that executes arbitrary javascript code.

    Args:
        javascript_code: The code to execute.

    Returns:
        EventSpec: An event that will execute the client side javascript.
    """
    return server_side(
        "_call_script",
        get_fn_signature(call_script),
        javascript_code=javascript_code,
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
    return get_event(state, constants.CompileVars.HYDRATE)


def call_event_handler(
    event_handler: EventHandler, arg_spec: Union[Var, ArgsSpec]
) -> EventSpec:
    """Call an event handler to get the event spec.

    This function will inspect the function signature of the event handler.
    If it takes in an arg, the arg will be passed to the event handler.
    Otherwise, the event handler will be called with no args.

    Args:
        event_handler: The event handler.
        arg_spec: The lambda that define the argument(s) to pass to the event handler.

    Raises:
        ValueError: if number of arguments expected by event_handler doesn't match the spec.

    Returns:
        The event spec from calling the event handler.
    """
    args = inspect.getfullargspec(event_handler.fn).args

    # handle new API using lambda to define triggers
    if isinstance(arg_spec, ArgsSpec):
        parsed_args = parse_args_spec(arg_spec)  # type: ignore

        if len(args) == len(["self", *parsed_args]):
            return event_handler(*parsed_args)  # type: ignore
        else:
            source = inspect.getsource(arg_spec)  # type: ignore
            raise ValueError(
                f"number of arguments in {event_handler.fn.__name__} "
                f"doesn't match the definition '{source.strip().strip(',')}'"
            )
    else:
        console.deprecate(
            feature_name="EVENT_ARG API for triggers",
            reason="Replaced by new API using lambda allow arbitrary number of args",
            deprecation_version="0.2.8",
            removal_version="0.3.0",
        )
        if len(args) == 1:
            return event_handler()
        assert (
            len(args) == 2
        ), f"Event handler {event_handler.fn} must have 1 or 2 arguments."
        return event_handler(arg_spec)  # type: ignore


def parse_args_spec(arg_spec: ArgsSpec):
    """Parse the args provided in the ArgsSpec of an event trigger.

    Args:
        arg_spec: The spec of the args.

    Returns:
        The parsed args.
    """
    spec = inspect.getfullargspec(arg_spec)
    return arg_spec(
        *[
            BaseVar(
                name=f"_{l_arg}",
                type_=spec.annotations.get(l_arg, FrontendEvent),
                is_local=True,
            )
            for l_arg in spec.args
        ]
    )


def call_event_fn(fn: Callable, arg: Union[Var, ArgsSpec]) -> list[EventSpec]:
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

    if isinstance(arg, ArgsSpec):
        out = fn(*parse_args_spec(arg))  # type: ignore
    else:
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
                e = e(arg)  # type: ignore

        # Make sure the event spec is valid.
        if not isinstance(e, EventSpec):
            raise ValueError(f"Lambda {fn} returned an invalid event spec: {e}.")

        # Add the event spec to the chain.
        events.append(e)

    # Return the events.
    return events


def get_handler_args(event_spec: EventSpec) -> tuple[tuple[Var, Var], ...]:
    """Get the handler args for the given event spec.

    Args:
        event_spec: The event spec.

    Returns:
        The handler args.
    """
    args = inspect.getfullargspec(event_spec.handler.fn).args

    return event_spec.args if len(args) > 1 else tuple()


def fix_events(
    events: list[EventHandler | EventSpec] | None,
    token: str,
    router_data: dict[str, Any] | None = None,
) -> list[Event]:
    """Fix a list of events returned by an event handler.

    Args:
        events: The events to fix.
        token: The user token.
        router_data: The optional router data to set in the event.

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
        payload = {k.name: v._decode() for k, v in e.args}  # type: ignore

        # Create an event and append it to the list.
        out.append(
            Event(
                token=token,
                name=name,
                payload=payload,
                router_data=router_data or {},
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
