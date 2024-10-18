"""Define event classes to connect the frontend and backend."""

from __future__ import annotations

import dataclasses
import inspect
import sys
import types
import urllib.parse
from base64 import b64encode
from functools import partial
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
    overload,
)

from typing_extensions import ParamSpec, get_args, get_origin

from reflex import constants
from reflex.utils import console, format
from reflex.utils.exceptions import EventFnArgMismatch, EventHandlerArgMismatch
from reflex.utils.types import ArgsSpec, GenericType
from reflex.vars import VarData
from reflex.vars.base import (
    LiteralNoneVar,
    LiteralVar,
    ToOperation,
    Var,
)
from reflex.vars.function import (
    ArgsFunctionOperation,
    FunctionStringVar,
    FunctionVar,
    VarOperationCall,
)
from reflex.vars.object import ObjectVar

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class Event:
    """An event that describes any state change in the app."""

    # The token to specify the client that the event is for.
    token: str

    # The event name.
    name: str

    # The routing data where event occurred
    router_data: Dict[str, Any] = dataclasses.field(default_factory=dict)

    # The event payload.
    payload: Dict[str, Any] = dataclasses.field(default_factory=dict)

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


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class EventActionsMixin:
    """Mixin for DOM event actions."""

    # Whether to `preventDefault` or `stopPropagation` on the event.
    event_actions: Dict[str, Union[bool, int]] = dataclasses.field(default_factory=dict)

    @property
    def stop_propagation(self):
        """Stop the event from bubbling up the DOM tree.

        Returns:
            New EventHandler-like with stopPropagation set to True.
        """
        return dataclasses.replace(
            self,
            event_actions={"stopPropagation": True, **self.event_actions},
        )

    @property
    def prevent_default(self):
        """Prevent the default behavior of the event.

        Returns:
            New EventHandler-like with preventDefault set to True.
        """
        return dataclasses.replace(
            self,
            event_actions={"preventDefault": True, **self.event_actions},
        )

    def throttle(self, limit_ms: int):
        """Throttle the event handler.

        Args:
            limit_ms: The time in milliseconds to throttle the event handler.

        Returns:
            New EventHandler-like with throttle set to limit_ms.
        """
        return dataclasses.replace(
            self,
            event_actions={"throttle": limit_ms, **self.event_actions},
        )

    def debounce(self, delay_ms: int):
        """Debounce the event handler.

        Args:
            delay_ms: The time in milliseconds to debounce the event handler.

        Returns:
            New EventHandler-like with debounce set to delay_ms.
        """
        return dataclasses.replace(
            self,
            event_actions={"debounce": delay_ms, **self.event_actions},
        )


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class EventHandler(EventActionsMixin):
    """An event handler responds to an event to update the state."""

    # The function to call in response to the event.
    fn: Any = dataclasses.field(default=None)

    # The full name of the state class this event handler is attached to.
    # Empty string means this event handler is a server side event.
    state_full_name: str = dataclasses.field(default="")

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
        fn_args = (Var(_js_expr=arg) for arg in fn_args)

        # Construct the payload.
        values = []
        for arg in args:
            # Special case for file uploads.
            if isinstance(arg, FileUpload):
                return arg.as_event_spec(handler=self)

            # Otherwise, convert to JSON.
            try:
                values.append(LiteralVar.create(arg))
            except TypeError as e:
                raise EventHandlerTypeError(
                    f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
                ) from e
        payload = tuple(zip(fn_args, values))

        # Return the event spec.
        return EventSpec(
            handler=self, args=payload, event_actions=self.event_actions.copy()
        )


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class EventSpec(EventActionsMixin):
    """An event specification.

    Whereas an Event object is passed during runtime, a spec is used
    during compile time to outline the structure of an event.
    """

    # The event handler.
    handler: EventHandler = dataclasses.field(default=None)  # type: ignore

    # The handler on the client to process event.
    client_handler_name: str = dataclasses.field(default="")

    # The arguments to pass to the function.
    args: Tuple[Tuple[Var, Var], ...] = dataclasses.field(default_factory=tuple)

    def __init__(
        self,
        handler: EventHandler,
        event_actions: Dict[str, Union[bool, int]] | None = None,
        client_handler_name: str = "",
        args: Tuple[Tuple[Var, Var], ...] = tuple(),
    ):
        """Initialize an EventSpec.

        Args:
            event_actions: The event actions.
            handler: The event handler.
            client_handler_name: The client handler name.
            args: The arguments to pass to the function.
        """
        if event_actions is None:
            event_actions = {}
        object.__setattr__(self, "event_actions", event_actions)
        object.__setattr__(self, "handler", handler)
        object.__setattr__(self, "client_handler_name", client_handler_name)
        object.__setattr__(self, "args", args or tuple())

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
        fn_args = (Var(_js_expr=arg) for arg in fn_args)

        # Construct the payload.
        values = []
        for arg in args:
            try:
                values.append(LiteralVar.create(arg))
            except TypeError as e:
                raise EventHandlerTypeError(
                    f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
                ) from e
        new_payload = tuple(zip(fn_args, values))
        return self.with_args(self.args + new_payload)


@dataclasses.dataclass(
    frozen=True,
)
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
                event_actions=default_event_spec.event_actions,
                client_handler_name=default_event_spec.client_handler_name,
                args=default_event_spec.args,
                handler=default_event_spec.handler,
                **kwargs,
            )
            object.__setattr__(self, "fn", fn)
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


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class EventChain(EventActionsMixin):
    """Container for a chain of events that will be executed in order."""

    events: List[Union[EventSpec, EventVar]] = dataclasses.field(default_factory=list)

    args_spec: Optional[Callable] = dataclasses.field(default=None)

    invocation: Optional[Var] = dataclasses.field(default=None)


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class JavascriptHTMLInputElement:
    """Interface for a Javascript HTMLInputElement https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement."""

    value: str = ""


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class JavascriptInputEvent:
    """Interface for a Javascript InputEvent https://developer.mozilla.org/en-US/docs/Web/API/InputEvent."""

    target: JavascriptHTMLInputElement = JavascriptHTMLInputElement()


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class JavasciptKeyboardEvent:
    """Interface for a Javascript KeyboardEvent https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent."""

    key: str = ""


def input_event(e: Var[JavascriptInputEvent]) -> Tuple[Var[str]]:
    """Get the value from an input event.

    Args:
        e: The input event.

    Returns:
        The value from the input event.
    """
    return (e.target.value,)


def key_event(e: Var[JavasciptKeyboardEvent]) -> Tuple[Var[str]]:
    """Get the key from a keyboard event.

    Args:
        e: The keyboard event.

    Returns:
        The key from the keyboard event.
    """
    return (e.key,)


def empty_event() -> Tuple[()]:
    """Empty event handler.

    Returns:
        An empty tuple.
    """
    return tuple()  # type: ignore


# These chains can be used for their side effects when no other events are desired.
stop_propagation = EventChain(events=[], args_spec=empty_event).stop_propagation
prevent_default = EventChain(events=[], args_spec=empty_event).prevent_default


T = TypeVar("T")


def identity_event(event_type: Type[T]) -> Callable[[Var[T]], Tuple[Var[T]]]:
    """A helper function that returns the input event as output.

    Args:
        event_type: The type of the event.

    Returns:
        A function that returns the input event as output.
    """

    def inner(ev: Var[T]) -> Tuple[Var[T]]:
        return (ev,)

    inner.__signature__ = inspect.signature(inner).replace(  # type: ignore
        parameters=[
            inspect.Parameter(
                "ev",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Var[event_type],
            )
        ],
        return_annotation=Tuple[Var[event_type]],
    )
    inner.__annotations__["ev"] = Var[event_type]
    inner.__annotations__["return"] = Tuple[Var[event_type]]

    return inner


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class FileUpload:
    """Class to represent a file upload."""

    upload_id: Optional[str] = None
    on_upload_progress: Optional[Union[EventHandler, Callable]] = None

    @staticmethod
    def on_upload_progress_args_spec(_prog: Var[Dict[str, Union[int, float, bool]]]):
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
                Var(_js_expr="files"),
                Var(
                    _js_expr="filesById",
                    _var_type=Dict[str, Any],
                    _var_data=VarData.merge(upload_files_context_var_data),
                ).to(ObjectVar)[LiteralVar.create(upload_id)],
            ),
            (
                Var(_js_expr="upload_id"),
                LiteralVar.create(upload_id),
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
                events=[*events],
                args_spec=self.on_upload_progress_args_spec,
            )
            formatted_chain = str(format.format_prop(on_upload_progress_chain))
            spec_args.append(
                (
                    Var(_js_expr="on_upload_progress"),
                    FunctionStringVar(
                        formatted_chain.strip("{}"),
                    ).to(FunctionVar, EventChain),
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
                Var(_js_expr=k),
                LiteralVar.create(v),
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
        ref=LiteralVar.create(format.format_ref(ref)),
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
        ref=LiteralVar.create(format.format_ref(ref)),
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

            is_data_url = (data.js_type() == "string") & (
                data.to(str).startswith("data:")
            )  # type: ignore

            # If it's a data: URI, use it as is, otherwise convert the Var to JSON in a data: URI.
            url = cond(  # type: ignore
                is_data_url,
                data.to(str),
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
    callback: (
        EventSpec
        | EventHandler
        | Callable
        | List[EventSpec | EventHandler | Callable]
        | None
    ) = None,
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
    if isinstance(javascript_code, str):
        # When there is VarData, include it and eval the JS code inline on the client.
        javascript_code, original_code = (
            LiteralVar.create(javascript_code),
            javascript_code,
        )
        if not javascript_code._get_all_var_data():
            # Without VarData, cast to string and eval the code in the event loop.
            javascript_code = str(Var(_js_expr=original_code))

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
        EventHandlerArgMismatch: if number of arguments expected by event_handler doesn't match the spec.

    Returns:
        The event spec from calling the event handler.
    """
    parsed_args = parse_args_spec(arg_spec)  # type: ignore

    if isinstance(event_handler, EventSpec):
        # Handle partial application of EventSpec args
        return event_handler.add_args(*parsed_args)

    args = inspect.getfullargspec(event_handler.fn).args
    n_args = len(args) - 1  # subtract 1 for bound self arg
    if n_args == len(parsed_args):
        return event_handler(*parsed_args)  # type: ignore
    else:
        raise EventHandlerArgMismatch(
            "The number of arguments accepted by "
            f"{event_handler.fn.__qualname__} ({n_args}) "
            "does not match the arguments passed by the event trigger: "
            f"{[str(v) for v in parsed_args]}\n"
            "See https://reflex.dev/docs/events/event-arguments/"
        )


def unwrap_var_annotation(annotation: GenericType):
    """Unwrap a Var annotation or return it as is if it's not Var[X].

    Args:
        annotation: The annotation to unwrap.

    Returns:
        The unwrapped annotation.
    """
    if get_origin(annotation) is Var and (args := get_args(annotation)):
        return args[0]
    return annotation


def resolve_annotation(annotations: dict[str, Any], arg_name: str):
    """Resolve the annotation for the given argument name.

    Args:
        annotations: The annotations.
        arg_name: The argument name.

    Returns:
        The resolved annotation.
    """
    annotation = annotations.get(arg_name)
    if annotation is None:
        console.deprecate(
            feature_name="Unannotated event handler arguments",
            reason="Provide type annotations for event handler arguments.",
            deprecation_version="0.6.3",
            removal_version="0.7.0",
        )
        # Allow arbitrary attribute access two levels deep until removed.
        return Dict[str, dict]
    return annotation


def parse_args_spec(arg_spec: ArgsSpec):
    """Parse the args provided in the ArgsSpec of an event trigger.

    Args:
        arg_spec: The spec of the args.

    Returns:
        The parsed args.
    """
    spec = inspect.getfullargspec(arg_spec)
    annotations = get_type_hints(arg_spec)

    return list(
        arg_spec(
            *[
                Var(f"_{l_arg}").to(
                    unwrap_var_annotation(resolve_annotation(annotations, l_arg))
                )
                for l_arg in spec.args
            ]
        )
    )


def check_fn_match_arg_spec(fn: Callable, arg_spec: ArgsSpec) -> List[Var]:
    """Ensures that the function signature matches the passed argument specification
    or raises an EventFnArgMismatch if they do not.

    Args:
        fn: The function to be validated.
        arg_spec: The argument specification for the event trigger.

    Returns:
        The parsed arguments from the argument specification.

    Raises:
        EventFnArgMismatch: Raised if the number of mandatory arguments do not match
    """
    fn_args = inspect.getfullargspec(fn).args
    fn_defaults_args = inspect.getfullargspec(fn).defaults
    n_fn_args = len(fn_args)
    n_fn_defaults_args = len(fn_defaults_args) if fn_defaults_args else 0
    if isinstance(fn, types.MethodType):
        n_fn_args -= 1  # subtract 1 for bound self arg
    parsed_args = parse_args_spec(arg_spec)
    if not (n_fn_args - n_fn_defaults_args <= len(parsed_args) <= n_fn_args):
        raise EventFnArgMismatch(
            "The number of mandatory arguments accepted by "
            f"{fn} ({n_fn_args - n_fn_defaults_args}) "
            "does not match the arguments passed by the event trigger: "
            f"{[str(v) for v in parsed_args]}\n"
            "See https://reflex.dev/docs/events/event-arguments/"
        )
    return parsed_args


def call_event_fn(fn: Callable, arg_spec: ArgsSpec) -> list[EventSpec] | Var:
    """Call a function to a list of event specs.

    The function should return a single EventSpec, a list of EventSpecs, or a
    single Var.

    Args:
        fn: The function to call.
        arg_spec: The argument spec for the event trigger.

    Returns:
        The event specs from calling the function or a Var.

    Raises:
        EventHandlerValueError: If the lambda returns an unusable value.
    """
    # Import here to avoid circular imports.
    from reflex.event import EventHandler, EventSpec
    from reflex.utils.exceptions import EventHandlerValueError

    # Check that fn signature matches arg_spec
    parsed_args = check_fn_match_arg_spec(fn, arg_spec)

    # Call the function with the parsed args.
    out = fn(*parsed_args)

    # If the function returns a Var, assume it's an EventChain and render it directly.
    if isinstance(out, Var):
        return out

    # Convert the output to a list.
    if not isinstance(out, list):
        out = [out]

    # Convert any event specs to event specs.
    events = []
    for e in out:
        if isinstance(e, EventHandler):
            # An un-called EventHandler gets all of the args of the event trigger.
            e = call_event_handler(e, arg_spec)

        # Make sure the event spec is valid.
        if not isinstance(e, EventSpec):
            raise EventHandlerValueError(
                f"Lambda {fn} returned an invalid event spec: {e}."
            )

        # Add the event spec to the chain.
        events.append(e)

    # Return the events.
    return events


def get_handler_args(
    event_spec: EventSpec,
) -> tuple[tuple[Var, Var], ...]:
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

    Raises:
        ValueError: If the event type is not what was expected.

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
        if not isinstance(e, EventSpec):
            raise ValueError(f"Unexpected event type, {type(e)}.")
        name = format.format_event_handler(e.handler)
        payload = {k._js_expr: v._decode() for k, v in e.args}  # type: ignore

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


class EventVar(ObjectVar):
    """Base class for event vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralEventVar(VarOperationCall, LiteralVar, EventVar):
    """A literal event var."""

    _var_value: EventSpec = dataclasses.field(default=None)  # type: ignore

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((self.__class__.__name__, self._js_expr))

    @classmethod
    def create(
        cls,
        value: EventSpec,
        _var_data: VarData | None = None,
    ) -> LiteralEventVar:
        """Create a new LiteralEventVar instance.

        Args:
            value: The value of the var.
            _var_data: The data of the var.

        Returns:
            The created LiteralEventVar instance.
        """
        return cls(
            _js_expr="",
            _var_type=EventSpec,
            _var_data=_var_data,
            _var_value=value,
            _func=FunctionStringVar("Event"),
            _args=(
                # event handler name
                ".".join(
                    filter(
                        None,
                        format.get_event_handler_parts(value.handler),
                    )
                ),
                # event handler args
                {str(name): value for name, value in value.args},
                # event actions
                value.event_actions,
                # client handler name
                *([value.client_handler_name] if value.client_handler_name else []),
            ),
        )


class EventChainVar(FunctionVar):
    """Base class for event chain vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
# Note: LiteralVar is second in the inheritance list allowing it act like a
# CachedVarOperation (ArgsFunctionOperation) and get the _js_expr from the
# _cached_var_name property.
class LiteralEventChainVar(ArgsFunctionOperation, LiteralVar, EventChainVar):
    """A literal event chain var."""

    _var_value: EventChain = dataclasses.field(default=None)  # type: ignore

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((self.__class__.__name__, self._js_expr))

    @classmethod
    def create(
        cls,
        value: EventChain,
        _var_data: VarData | None = None,
    ) -> LiteralEventChainVar:
        """Create a new LiteralEventChainVar instance.

        Args:
            value: The value of the var.
            _var_data: The data of the var.

        Returns:
            The created LiteralEventChainVar instance.
        """
        sig = inspect.signature(value.args_spec)  # type: ignore
        if sig.parameters:
            arg_def = tuple((f"_{p}" for p in sig.parameters))
            arg_def_expr = LiteralVar.create([Var(_js_expr=arg) for arg in arg_def])
        else:
            # add a default argument for addEvents if none were specified in value.args_spec
            # used to trigger the preventDefault() on the event.
            arg_def = ("...args",)
            arg_def_expr = Var(_js_expr="args")

        if value.invocation is None:
            invocation = FunctionStringVar.create("addEvents")
        else:
            invocation = value.invocation

        return cls(
            _js_expr="",
            _var_type=EventChain,
            _var_data=_var_data,
            _args_names=arg_def,
            _return_expr=invocation.call(
                LiteralVar.create([LiteralVar.create(event) for event in value.events]),
                arg_def_expr,
                value.event_actions,
            ),
            _var_value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToEventVarOperation(ToOperation, EventVar):
    """Result of a cast to an event var."""

    _original: Var = dataclasses.field(default_factory=lambda: LiteralNoneVar.create())

    _default_var_type: ClassVar[Type] = EventSpec


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToEventChainVarOperation(ToOperation, EventChainVar):
    """Result of a cast to an event chain var."""

    _original: Var = dataclasses.field(default_factory=lambda: LiteralNoneVar.create())

    _default_var_type: ClassVar[Type] = EventChain


G = ParamSpec("G")

IndividualEventType = Union[EventSpec, EventHandler, Callable[G, Any], Var[Any]]

EventType = Union[IndividualEventType[G], List[IndividualEventType[G]]]

P = ParamSpec("P")
T = TypeVar("T")
V = TypeVar("V")
V2 = TypeVar("V2")
V3 = TypeVar("V3")
V4 = TypeVar("V4")
V5 = TypeVar("V5")

if sys.version_info >= (3, 10):
    from typing import Concatenate

    class EventCallback(Generic[P, T]):
        """A descriptor that wraps a function to be used as an event."""

        def __init__(self, func: Callable[Concatenate[Any, P], T]):
            """Initialize the descriptor with the function to be wrapped.

            Args:
                func: The function to be wrapped.
            """
            self.func = func

        @overload
        def __get__(
            self: EventCallback[[V], T], instance: None, owner
        ) -> Callable[[Union[Var[V], V]], EventSpec]: ...

        @overload
        def __get__(
            self: EventCallback[[V, V2], T], instance: None, owner
        ) -> Callable[[Union[Var[V], V], Union[Var[V2], V2]], EventSpec]: ...

        @overload
        def __get__(
            self: EventCallback[[V, V2, V3], T], instance: None, owner
        ) -> Callable[
            [Union[Var[V], V], Union[Var[V2], V2], Union[Var[V3], V3]],
            EventSpec,
        ]: ...

        @overload
        def __get__(
            self: EventCallback[[V, V2, V3, V4], T], instance: None, owner
        ) -> Callable[
            [
                Union[Var[V], V],
                Union[Var[V2], V2],
                Union[Var[V3], V3],
                Union[Var[V4], V4],
            ],
            EventSpec,
        ]: ...

        @overload
        def __get__(
            self: EventCallback[[V, V2, V3, V4, V5], T], instance: None, owner
        ) -> Callable[
            [
                Union[Var[V], V],
                Union[Var[V2], V2],
                Union[Var[V3], V3],
                Union[Var[V4], V4],
                Union[Var[V5], V5],
            ],
            EventSpec,
        ]: ...

        @overload
        def __get__(self, instance, owner) -> Callable[P, T]: ...

        def __get__(self, instance, owner) -> Callable:
            """Get the function with the instance bound to it.

            Args:
                instance: The instance to bind to the function.
                owner: The owner of the function.

            Returns:
                The function with the instance bound to it
            """
            if instance is None:
                return self.func  # type: ignore

            return partial(self.func, instance)  # type: ignore

    def event_handler(func: Callable[Concatenate[Any, P], T]) -> EventCallback[P, T]:
        """Wrap a function to be used as an event.

        Args:
            func: The function to wrap.

        Returns:
            The wrapped function.
        """
        return func  # type: ignore
else:

    def event_handler(func: Callable[P, T]) -> Callable[P, T]:
        """Wrap a function to be used as an event.

        Args:
            func: The function to wrap.

        Returns:
            The wrapped function.
        """
        return func


class EventNamespace(types.SimpleNamespace):
    """A namespace for event related classes."""

    Event = Event
    EventHandler = EventHandler
    EventSpec = EventSpec
    CallableEventSpec = CallableEventSpec
    EventChain = EventChain
    EventVar = EventVar
    LiteralEventVar = LiteralEventVar
    EventChainVar = EventChainVar
    LiteralEventChainVar = LiteralEventChainVar
    ToEventVarOperation = ToEventVarOperation
    ToEventChainVarOperation = ToEventChainVarOperation
    EventType = EventType

    __call__ = staticmethod(event_handler)
    get_event = staticmethod(get_event)
    get_hydrate_event = staticmethod(get_hydrate_event)
    fix_events = staticmethod(fix_events)
    call_event_handler = staticmethod(call_event_handler)
    call_event_fn = staticmethod(call_event_fn)
    get_handler_args = staticmethod(get_handler_args)
    check_fn_match_arg_spec = staticmethod(check_fn_match_arg_spec)
    resolve_annotation = staticmethod(resolve_annotation)
    parse_args_spec = staticmethod(parse_args_spec)
    identity_event = staticmethod(identity_event)
    input_event = staticmethod(input_event)
    key_event = staticmethod(key_event)
    empty_event = staticmethod(empty_event)
    server_side = staticmethod(server_side)
    redirect = staticmethod(redirect)
    console_log = staticmethod(console_log)
    back = staticmethod(back)
    window_alert = staticmethod(window_alert)
    set_focus = staticmethod(set_focus)
    scroll_to = staticmethod(scroll_to)
    set_value = staticmethod(set_value)
    remove_cookie = staticmethod(remove_cookie)
    clear_local_storage = staticmethod(clear_local_storage)
    remove_local_storage = staticmethod(remove_local_storage)
    clear_session_storage = staticmethod(clear_session_storage)
    remove_session_storage = staticmethod(remove_session_storage)
    set_clipboard = staticmethod(set_clipboard)
    download = staticmethod(download)
    call_script = staticmethod(call_script)


event = EventNamespace()
