"""Define event classes to connect the frontend and backend."""

from __future__ import annotations

import inspect
import urllib.parse
from base64 import b64encode
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    get_type_hints,
)

from reflex import constants
from reflex.base import Base
from reflex.utils import format
from reflex.utils.types import ArgsSpec
from reflex.vars import BaseVar, Var

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated


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

    @property
    def substate_token(self) -> str:
        """Get the substate token for the event.

        Returns:
            The substate token.
        """
        substate = self.name.rpartition(".")[0]
        return f"{self.token}_{substate}"


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


class EventActionsMixin(Base):
    """Mixin for DOM event actions."""

    # Whether to `preventDefault` or `stopPropagation` on the event.
    event_actions: Dict[str, Union[bool, int]] = {}

    @property
    def stop_propagation(self):
        """Stop the event from bubbling up the DOM tree.

        Returns:
            New EventHandler-like with stopPropagation set to True.
        """
        return self.copy(
            update={"event_actions": {"stopPropagation": True, **self.event_actions}},
        )

    @property
    def prevent_default(self):
        """Prevent the default behavior of the event.

        Returns:
            New EventHandler-like with preventDefault set to True.
        """
        return self.copy(
            update={"event_actions": {"preventDefault": True, **self.event_actions}},
        )

    def throttle(self, limit_ms: int):
        """Throttle the event handler.

        Args:
            limit_ms: The time in milliseconds to throttle the event handler.

        Returns:
            New EventHandler-like with throttle set to limit_ms.
        """
        return self.copy(
            update={"event_actions": {"throttle": limit_ms, **self.event_actions}},
        )

    def debounce(self, delay_ms: int):
        """Debounce the event handler.

        Args:
            delay_ms: The time in milliseconds to debounce the event handler.

        Returns:
            New EventHandler-like with debounce set to delay_ms.
        """
        return self.copy(
            update={"event_actions": {"debounce": delay_ms, **self.event_actions}},
        )


class EventHandler(EventActionsMixin):
    """An event handler responds to an event to update the state."""

    # The function to call in response to the event.
    fn: Any

    # The full name of the state class this event handler is attached to.
    # Empty string means this event handler is a server side event.
    state_full_name: str = ""

    class Config:
        """The Pydantic config."""

        # Needed to allow serialization of Callable.
        frozen = True

    @classmethod
    def __class_getitem__(cls, args_spec: str) -> Annotated:
        """Get a typed EventHandler.

        Args:
            args_spec: The args_spec of the EventHandler.

        Returns:
            The EventHandler class item.
        """
        return Annotated[cls, args_spec]

    @property
    def is_background(self) -> bool:
        """Whether the event handler is a background task.

        Returns:
            True if the event handler is marked as a background task.
        """
        return getattr(self.fn, BACKGROUND_TASK_MARKER, False)

    def __call__(self, *args: Any) -> EventSpec:
        """Pass arguments to the handler to get an event spec.

        This method configures event handlers that take in arguments.

        Args:
            *args: The arguments to pass to the handler.

        Returns:
            The event spec, containing both the function and args.

        Raises:
            EventHandlerTypeError: If the arguments are invalid.
        """
        from reflex.utils.exceptions import EventHandlerTypeError

        # Get the function args.
        fn_args = inspect.getfullargspec(self.fn).args[1:]
        fn_args = (Var.create_safe(arg, _var_is_string=False) for arg in fn_args)

        # Construct the payload.
        values = []
        for arg in args:
            # Special case for file uploads.
            if isinstance(arg, FileUpload):
                return arg.as_event_spec(handler=self)

            # Otherwise, convert to JSON.
            try:
                values.append(Var.create(arg, _var_is_string=isinstance(arg, str)))
            except TypeError as e:
                raise EventHandlerTypeError(
                    f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
                ) from e
        payload = tuple(zip(fn_args, values))

        # Return the event spec.
        return EventSpec(
            handler=self, args=payload, event_actions=self.event_actions.copy()
        )


class EventSpec(EventActionsMixin):
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

    def with_args(self, args: Tuple[Tuple[Var, Var], ...]) -> EventSpec:
        """Copy the event spec, with updated args.

        Args:
            args: The new args to pass to the function.

        Returns:
            A copy of the event spec, with the new args.
        """
        return type(self)(
            handler=self.handler,
            client_handler_name=self.client_handler_name,
            args=args,
            event_actions=self.event_actions.copy(),
        )

    def add_args(self, *args: Var) -> EventSpec:
        """Add arguments to the event spec.

        Args:
            *args: The arguments to add positionally.

        Returns:
            The event spec with the new arguments.

        Raises:
            EventHandlerTypeError: If the arguments are invalid.
        """
        from reflex.utils.exceptions import EventHandlerTypeError

        # Get the remaining unfilled function args.
        fn_args = inspect.getfullargspec(self.handler.fn).args[1 + len(self.args) :]
        fn_args = (Var.create_safe(arg, _var_is_string=False) for arg in fn_args)

        # Construct the payload.
        values = []
        for arg in args:
            try:
                values.append(Var.create(arg, _var_is_string=isinstance(arg, str)))
            except TypeError as e:
                raise EventHandlerTypeError(
                    f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
                ) from e
        new_payload = tuple(zip(fn_args, values))
        return self.with_args(self.args + new_payload)


class CallableEventSpec(EventSpec):
    """Decorate an EventSpec-returning function to act as both a EventSpec and a function.

    This is used as a compatibility shim for replacing EventSpec objects in the
    API with functions that return a family of EventSpec.
    """

    fn: Optional[Callable[..., EventSpec]] = None

    def __init__(self, fn: Callable[..., EventSpec] | None = None, **kwargs):
        """Initialize a CallableEventSpec.

        Args:
            fn: The function to decorate.
            **kwargs: The kwargs to pass to pydantic initializer
        """
        if fn is not None:
            default_event_spec = fn()
            super().__init__(
                fn=fn,  # type: ignore
                **default_event_spec.dict(),
                **kwargs,
            )
        else:
            super().__init__(**kwargs)

    def __call__(self, *args, **kwargs) -> EventSpec:
        """Call the decorated function.

        Args:
            *args: The args to pass to the function.
            **kwargs: The kwargs to pass to the function.

        Returns:
            The EventSpec returned from calling the function.

        Raises:
            EventHandlerTypeError: If the CallableEventSpec has no associated function.
        """
        from reflex.utils.exceptions import EventHandlerTypeError

        if self.fn is None:
            raise EventHandlerTypeError("CallableEventSpec has no associated function.")
        return self.fn(*args, **kwargs)


class EventChain(EventActionsMixin):
    """Container for a chain of events that will be executed in order."""

    events: List[EventSpec]

    args_spec: Optional[Callable]


# These chains can be used for their side effects when no other events are desired.
stop_propagation = EventChain(events=[], args_spec=lambda: []).stop_propagation
prevent_default = EventChain(events=[], args_spec=lambda: []).prevent_default


class Target(Base):
    """A Javascript event target."""

    checked: bool = False
    value: Any = None


class FrontendEvent(Base):
    """A Javascript event."""

    target: Target = Target()
    key: str = ""
    value: Any = None


class FileUpload(Base):
    """Class to represent a file upload."""

    upload_id: Optional[str] = None
    on_upload_progress: Optional[Union[EventHandler, Callable]] = None

    @staticmethod
    def on_upload_progress_args_spec(_prog: Dict[str, Union[int, float, bool]]):
        """Args spec for on_upload_progress event handler.

        Returns:
            The arg mapping passed to backend event handler
        """
        return [_prog]

    def as_event_spec(self, handler: EventHandler) -> EventSpec:
        """Get the EventSpec for the file upload.

        Args:
            handler: The event handler.

        Returns:
            The event spec for the handler.

        Raises:
            ValueError: If the on_upload_progress is not a valid event handler.
        """
        from reflex.components.core.upload import (
            DEFAULT_UPLOAD_ID,
            upload_files_context_var_data,
        )

        upload_id = self.upload_id or DEFAULT_UPLOAD_ID
        spec_args = [
            (
                Var.create_safe("files", _var_is_string=False),
                Var.create_safe(
                    f"filesById[{Var.create_safe(upload_id, _var_is_string=True)._var_name_unwrapped}]",
                    _var_is_string=False,
                )._replace(_var_data=upload_files_context_var_data),
            ),
            (
                Var.create_safe("upload_id", _var_is_string=False),
                Var.create_safe(upload_id, _var_is_string=True),
            ),
        ]
        if self.on_upload_progress is not None:
            on_upload_progress = self.on_upload_progress
            if isinstance(on_upload_progress, EventHandler):
                events = [
                    call_event_handler(
                        on_upload_progress,
                        self.on_upload_progress_args_spec,
                    ),
                ]
            elif isinstance(on_upload_progress, Callable):
                # Call the lambda to get the event chain.
                events = call_event_fn(
                    on_upload_progress, self.on_upload_progress_args_spec
                )  # type: ignore
            else:
                raise ValueError(f"{on_upload_progress} is not a valid event handler.")
            if isinstance(events, Var):
                raise ValueError(f"{on_upload_progress} cannot return a var {events}.")
            on_upload_progress_chain = EventChain(
                events=events,
                args_spec=self.on_upload_progress_args_spec,
            )
            formatted_chain = str(format.format_prop(on_upload_progress_chain))
            spec_args.append(
                (
                    Var.create_safe("on_upload_progress", _var_is_string=False),
                    BaseVar(
                        _var_name=formatted_chain.strip("{}"),
                        _var_type=EventChain,
                    ),
                ),
            )
        return EventSpec(
            handler=handler,
            client_handler_name="uploadFiles",
            args=tuple(spec_args),
            event_actions=handler.event_actions.copy(),
        )


# Alias for rx.upload_files
upload_files = FileUpload


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
            (
                Var.create_safe(k, _var_is_string=False),
                Var.create_safe(v, _var_is_string=isinstance(v, str)),
            )
            for k, v in kwargs.items()
        ),
    )


def redirect(
    path: str | Var[str],
    external: Optional[bool] = False,
    replace: Optional[bool] = False,
) -> EventSpec:
    """Redirect to a new path.

    Args:
        path: The path to redirect to.
        external: Whether to open in new tab or not.
        replace: If True, the current page will not create a new history entry.

    Returns:
        An event to redirect to the path.
    """
    return server_side(
        "_redirect",
        get_fn_signature(redirect),
        path=path,
        external=external,
        replace=replace,
    )


def console_log(message: str | Var[str]) -> EventSpec:
    """Do a console.log on the browser.

    Args:
        message: The message to log.

    Returns:
        An event to log the message.
    """
    return server_side("_console", get_fn_signature(console_log), message=message)


def back() -> EventSpec:
    """Do a history.back on the browser.

    Returns:
        An event to go back one page.
    """
    return call_script("window.history.back()")


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
        ref=Var.create_safe(format.format_ref(ref), _var_is_string=True),
    )


def scroll_to(elem_id: str) -> EventSpec:
    """Select the id of a html element for scrolling into view.

    Args:
        elem_id: the id of the element

    Returns:
        An EventSpec to scroll the page to the selected element.
    """
    js_code = f"document.getElementById('{elem_id}').scrollIntoView();"

    return call_script(js_code)


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
        ref=Var.create_safe(format.format_ref(ref), _var_is_string=True),
        value=value,
    )


def remove_cookie(key: str, options: dict[str, Any] | None = None) -> EventSpec:
    """Remove a cookie on the frontend.

    Args:
        key: The key identifying the cookie to be removed.
        options: Support all the cookie options from RFC 6265

    Returns:
        EventSpec: An event to remove a cookie.
    """
    options = options or {}
    options["path"] = options.get("path", "/")
    return server_side(
        "_remove_cookie",
        get_fn_signature(remove_cookie),
        key=key,
        options=options,
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
        get_fn_signature(remove_local_storage),
        key=key,
    )


def clear_session_storage() -> EventSpec:
    """Set a value in the session storage on the frontend.

    Returns:
        EventSpec: An event to clear the session storage.
    """
    return server_side(
        "_clear_session_storage",
        get_fn_signature(clear_session_storage),
    )


def remove_session_storage(key: str) -> EventSpec:
    """Set a value in the session storage on the frontend.

    Args:
        key: The key identifying the variable in the session storage to remove.

    Returns:
        EventSpec: An event to remove an item based on the provided key in session storage.
    """
    return server_side(
        "_remove_session_storage",
        get_fn_signature(remove_session_storage),
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


def download(
    url: str | Var | None = None,
    filename: Optional[str | Var] = None,
    data: str | bytes | Var | None = None,
) -> EventSpec:
    """Download the file at a given path or with the specified data.

    Args:
        url: The URL to the file to download.
        filename: The name that the file should be saved as after download.
        data: The data to download.

    Raises:
        ValueError: If the URL provided is invalid, both URL and data are provided,
            or the data is not an expected type.

    Returns:
        EventSpec: An event to download the associated file.
    """
    from reflex.components.core.cond import cond

    if isinstance(url, str):
        if not url.startswith("/"):
            raise ValueError("The URL argument should start with a /")

        # if filename is not provided, infer it from url
        if filename is None:
            filename = url.rpartition("/")[-1]

    if filename is None:
        filename = ""

    if data is not None:
        if url is not None:
            raise ValueError("Cannot provide both URL and data to download.")

        if isinstance(data, str):
            # Caller provided a plain text string to download.
            url = "data:text/plain," + urllib.parse.quote(data)
        elif isinstance(data, Var):
            # Need to check on the frontend if the Var already looks like a data: URI.
            is_data_url = data._replace(
                _var_name=(
                    f"typeof {data._var_full_name} == 'string' && "
                    f"{data._var_full_name}.startsWith('data:')"
                ),
                _var_type=bool,
                _var_is_string=False,
                _var_full_name_needs_state_prefix=False,
            )
            # If it's a data: URI, use it as is, otherwise convert the Var to JSON in a data: URI.
            url = cond(  # type: ignore
                is_data_url,
                data,
                "data:text/plain," + data.to_string(),  # type: ignore
            )
        elif isinstance(data, bytes):
            # Caller provided bytes, so base64 encode it as a data: URI.
            b64_data = b64encode(data).decode("utf-8")
            url = "data:application/octet-stream;base64," + b64_data
        else:
            raise ValueError(
                f"Invalid data type {type(data)} for download. Use `str` or `bytes`."
            )

    return server_side(
        "_download",
        get_fn_signature(download),
        url=url,
        filename=filename,
    )


def _callback_arg_spec(eval_result):
    """ArgSpec for call_script callback function.

    Args:
        eval_result: The result of the javascript execution.

    Returns:
        Args for the callback function
    """
    return [eval_result]


def call_script(
    javascript_code: str | Var[str],
    callback: EventSpec
    | EventHandler
    | Callable
    | List[EventSpec | EventHandler | Callable]
    | None = None,
) -> EventSpec:
    """Create an event handler that executes arbitrary javascript code.

    Args:
        javascript_code: The code to execute.
        callback: EventHandler that will receive the result of evaluating the javascript code.

    Returns:
        EventSpec: An event that will execute the client side javascript.
    """
    callback_kwargs = {}
    if callback is not None:
        callback_kwargs = {
            "callback": str(
                format.format_queue_events(
                    callback,
                    args_spec=lambda result: [result],
                ),
            ),
        }
    return server_side(
        "_call_script",
        get_fn_signature(call_script),
        javascript_code=javascript_code,
        **callback_kwargs,
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
    event_handler: EventHandler | EventSpec,
    arg_spec: ArgsSpec,
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
    parsed_args = parse_args_spec(arg_spec)  # type: ignore

    if isinstance(event_handler, EventSpec):
        # Handle partial application of EventSpec args
        return event_handler.add_args(*parsed_args)

    args = inspect.getfullargspec(event_handler.fn).args
    if len(args) == len(["self", *parsed_args]):
        return event_handler(*parsed_args)  # type: ignore
    else:
        source = inspect.getsource(arg_spec)  # type: ignore
        raise ValueError(
            f"number of arguments in {event_handler.fn.__qualname__} "
            f"doesn't match the definition of the event trigger '{source.strip().strip(',')}'"
        )


def parse_args_spec(arg_spec: ArgsSpec):
    """Parse the args provided in the ArgsSpec of an event trigger.

    Args:
        arg_spec: The spec of the args.

    Returns:
        The parsed args.
    """
    spec = inspect.getfullargspec(arg_spec)
    annotations = get_type_hints(arg_spec)
    return arg_spec(
        *[
            BaseVar(
                _var_name=f"_{l_arg}",
                _var_type=annotations.get(l_arg, FrontendEvent),
                _var_is_local=True,
            )
            for l_arg in spec.args
        ]
    )


def call_event_fn(fn: Callable, arg: Union[Var, ArgsSpec]) -> list[EventSpec] | Var:
    """Call a function to a list of event specs.

    The function should return a single EventSpec, a list of EventSpecs, or a
    single Var. If the function takes in an arg, the arg will be passed to the
    function. Otherwise, the function will be called with no args.

    Args:
        fn: The function to call.
        arg: The argument to pass to the function.

    Returns:
        The event specs from calling the function or a Var.

    Raises:
        EventHandlerValueError: If the lambda has an invalid signature.
    """
    # Import here to avoid circular imports.
    from reflex.event import EventHandler, EventSpec
    from reflex.utils.exceptions import EventHandlerValueError

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
            raise EventHandlerValueError(f"Lambda {fn} must have 0 or 1 arguments.")

    # If the function returns a Var, assume it's an EventChain and render it directly.
    if isinstance(out, Var):
        return out

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
            raise EventHandlerValueError(
                f"Lambda {fn} returned an invalid event spec: {e}."
            )

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
        if isinstance(e, Event):
            # If the event is already an event, append it to the list.
            out.append(e)
            continue
        if not isinstance(e, (EventHandler, EventSpec)):
            e = EventHandler(fn=e)
        # Otherwise, create an event from the event spec.
        if isinstance(e, EventHandler):
            e = e()
        assert isinstance(e, EventSpec), f"Unexpected event type, {type(e)}."
        name = format.format_event_handler(e.handler)
        payload = {k._var_name: v._decode() for k, v in e.args}  # type: ignore

        # Filter router_data to reduce payload size
        event_router_data = {
            k: v
            for k, v in (router_data or {}).items()
            if k in constants.route.ROUTER_DATA_INCLUDE
        }
        # Create an event and append it to the list.
        out.append(
            Event(
                token=token,
                name=name,
                payload=payload,
                router_data=event_router_data,
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
