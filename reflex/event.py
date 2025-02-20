"""Define event classes to connect the frontend and backend."""

from __future__ import annotations

import dataclasses
import inspect
import types
import urllib.parse
from base64 import b64encode
from functools import partial
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from typing_extensions import Self, TypeAliasType, TypeVarTuple, Unpack

from reflex import constants
from reflex.constants.compiler import CompileVars, Hooks, Imports
from reflex.constants.state import FRONTEND_EVENT_STATE
from reflex.utils import console, format
from reflex.utils.exceptions import (
    EventFnArgMismatchError,
    EventHandlerArgTypeMismatchError,
    MissingAnnotationError,
)
from reflex.utils.types import ArgsSpec, GenericType, typehint_issubclass
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import (
    ArgsFunctionOperation,
    ArgsFunctionOperationBuilder,
    BuilderFunctionVar,
    FunctionArgs,
    FunctionStringVar,
    FunctionVar,
    VarOperationCall,
)
from reflex.vars.object import ObjectVar


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


_EVENT_FIELDS: set[str] = {f.name for f in dataclasses.fields(Event)}

BACKGROUND_TASK_MARKER = "_reflex_background_task"


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class EventActionsMixin:
    """Mixin for DOM event actions."""

    # Whether to `preventDefault` or `stopPropagation` on the event.
    event_actions: Dict[str, Union[bool, int]] = dataclasses.field(default_factory=dict)

    @property
    def stop_propagation(self) -> Self:
        """Stop the event from bubbling up the DOM tree.

        Returns:
            New EventHandler-like with stopPropagation set to True.
        """
        return dataclasses.replace(
            self,
            event_actions={"stopPropagation": True, **self.event_actions},
        )

    @property
    def prevent_default(self) -> Self:
        """Prevent the default behavior of the event.

        Returns:
            New EventHandler-like with preventDefault set to True.
        """
        return dataclasses.replace(
            self,
            event_actions={"preventDefault": True, **self.event_actions},
        )

    def throttle(self, limit_ms: int) -> Self:
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

    def debounce(self, delay_ms: int) -> Self:
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

    @property
    def temporal(self) -> Self:
        """Do not queue the event if the backend is down.

        Returns:
            New EventHandler-like with temporal set to True.
        """
        return dataclasses.replace(
            self,
            event_actions={"temporal": True, **self.event_actions},
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
        payload = tuple(zip(fn_args, values, strict=False))

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
    handler: EventHandler = dataclasses.field(default=None)  # pyright: ignore [reportAssignmentType]

    # The handler on the client to process event.
    client_handler_name: str = dataclasses.field(default="")

    # The arguments to pass to the function.
    args: Tuple[Tuple[Var, Var], ...] = dataclasses.field(default_factory=tuple)

    def __init__(
        self,
        handler: EventHandler,
        event_actions: Dict[str, Union[bool, int]] | None = None,
        client_handler_name: str = "",
        args: Tuple[Tuple[Var, Var], ...] = (),
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
        object.__setattr__(self, "args", args or ())

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
        arg = None
        try:
            for arg in args:
                values.append(LiteralVar.create(value=arg))  # noqa: PERF401, RUF100
        except TypeError as e:
            raise EventHandlerTypeError(
                f"Arguments to event handlers must be Vars or JSON-serializable. Got {arg} of type {type(arg)}."
            ) from e
        new_payload = tuple(zip(fn_args, values, strict=False))
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

    events: Sequence[Union[EventSpec, EventVar, EventCallback]] = dataclasses.field(
        default_factory=list
    )

    args_spec: Optional[Union[Callable, Sequence[Callable]]] = dataclasses.field(
        default=None
    )

    invocation: Optional[Var] = dataclasses.field(default=None)

    @classmethod
    def create(
        cls,
        value: EventType,
        args_spec: ArgsSpec | Sequence[ArgsSpec],
        key: Optional[str] = None,
        **event_chain_kwargs,
    ) -> Union[EventChain, Var]:
        """Create an event chain from a variety of input types.

        Args:
            value: The value to create the event chain from.
            args_spec: The args_spec of the event trigger being bound.
            key: The key of the event trigger being bound.
            **event_chain_kwargs: Additional kwargs to pass to the EventChain constructor.

        Returns:
            The event chain.

        Raises:
            ValueError: If the value is not a valid event chain.
        """
        # If it's an event chain var, return it.
        if isinstance(value, Var):
            if isinstance(value, EventChainVar):
                return value
            elif isinstance(value, EventVar):
                value = [value]
            elif issubclass(value._var_type, (EventChain, EventSpec)):
                return cls.create(
                    value=value.guess_type(),
                    args_spec=args_spec,
                    key=key,
                    **event_chain_kwargs,
                )
            else:
                raise ValueError(
                    f"Invalid event chain: {value!s} of type {value._var_type}"
                )
        elif isinstance(value, EventChain):
            # Trust that the caller knows what they're doing passing an EventChain directly
            return value

        # If the input is a single event handler, wrap it in a list.
        if isinstance(value, (EventHandler, EventSpec)):
            value = [value]

        # If the input is a list of event handlers, create an event chain.
        if isinstance(value, List):
            events: List[Union[EventSpec, EventVar]] = []
            for v in value:
                if isinstance(v, (EventHandler, EventSpec)):
                    # Call the event handler to get the event.
                    events.append(call_event_handler(v, args_spec, key=key))
                elif isinstance(v, Callable):
                    # Call the lambda to get the event chain.
                    result = call_event_fn(v, args_spec, key=key)
                    if isinstance(result, Var):
                        raise ValueError(
                            f"Invalid event chain: {v}. Cannot use a Var-returning "
                            "lambda inside an EventChain list."
                        )
                    events.extend(result)
                elif isinstance(v, EventVar):
                    events.append(v)
                else:
                    raise ValueError(f"Invalid event: {v}")

        # If the input is a callable, create an event chain.
        elif isinstance(value, Callable):
            result = call_event_fn(value, args_spec, key=key)
            if isinstance(result, Var):
                # Recursively call this function if the lambda returned an EventChain Var.
                return cls.create(
                    value=result, args_spec=args_spec, key=key, **event_chain_kwargs
                )
            events = [*result]

        # Otherwise, raise an error.
        else:
            raise ValueError(f"Invalid event chain: {value}")

        # Add args to the event specs if necessary.
        events = [
            (e.with_args(get_handler_args(e)) if isinstance(e, EventSpec) else e)
            for e in events
        ]

        # Return the event chain.
        return cls(
            events=events,
            args_spec=args_spec,
            **event_chain_kwargs,
        )


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

    target: JavascriptHTMLInputElement = JavascriptHTMLInputElement()  # noqa: RUF009


@dataclasses.dataclass(
    init=True,
    frozen=True,
)
class JavasciptKeyboardEvent:
    """Interface for a Javascript KeyboardEvent https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent."""

    key: str = ""
    altKey: bool = False  # noqa: N815
    ctrlKey: bool = False  # noqa: N815
    metaKey: bool = False  # noqa: N815
    shiftKey: bool = False  # noqa: N815


def input_event(e: ObjectVar[JavascriptInputEvent]) -> Tuple[Var[str]]:
    """Get the value from an input event.

    Args:
        e: The input event.

    Returns:
        The value from the input event.
    """
    return (e.target.value,)


class KeyInputInfo(TypedDict):
    """Information about a key input event."""

    alt_key: bool
    ctrl_key: bool
    meta_key: bool
    shift_key: bool


def key_event(
    e: ObjectVar[JavasciptKeyboardEvent],
) -> Tuple[Var[str], Var[KeyInputInfo]]:
    """Get the key from a keyboard event.

    Args:
        e: The keyboard event.

    Returns:
        The key from the keyboard event.
    """
    return (
        e.key.to(str),
        Var.create(
            {
                "alt_key": e.altKey,
                "ctrl_key": e.ctrlKey,
                "meta_key": e.metaKey,
                "shift_key": e.shiftKey,
            },
        ).to(KeyInputInfo),
    )


def no_args_event_spec() -> Tuple[()]:
    """Empty event handler.

    Returns:
        An empty tuple.
    """
    return ()


# These chains can be used for their side effects when no other events are desired.
stop_propagation = EventChain(events=[], args_spec=no_args_event_spec).stop_propagation
prevent_default = EventChain(events=[], args_spec=no_args_event_spec).prevent_default


T = TypeVar("T")
U = TypeVar("U")


class IdentityEventReturn(Generic[T], Protocol):
    """Protocol for an identity event return."""

    def __call__(self, *values: Var[T]) -> Tuple[Var[T], ...]:
        """Return the input values.

        Args:
            *values: The values to return.

        Returns:
            The input values.
        """
        return values


@overload
def passthrough_event_spec(  # pyright: ignore [reportOverlappingOverload]
    event_type: Type[T], /
) -> Callable[[Var[T]], Tuple[Var[T]]]: ...


@overload
def passthrough_event_spec(
    event_type_1: Type[T], event_type2: Type[U], /
) -> Callable[[Var[T], Var[U]], Tuple[Var[T], Var[U]]]: ...


@overload
def passthrough_event_spec(*event_types: Type[T]) -> IdentityEventReturn[T]: ...


def passthrough_event_spec(*event_types: Type[T]) -> IdentityEventReturn[T]:  # pyright: ignore [reportInconsistentOverload]
    """A helper function that returns the input event as output.

    Args:
        *event_types: The types of the events.

    Returns:
        A function that returns the input event as output.
    """

    def inner(*values: Var[T]) -> Tuple[Var[T], ...]:
        return values

    inner_type = tuple(Var[event_type] for event_type in event_types)
    return_annotation = Tuple[inner_type]

    inner.__signature__ = inspect.signature(inner).replace(  # pyright: ignore [reportFunctionMemberAccess]
        parameters=[
            inspect.Parameter(
                f"ev_{i}",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Var[event_type],
            )
            for i, event_type in enumerate(event_types)
        ],
        return_annotation=return_annotation,
    )
    for i, event_type in enumerate(event_types):
        inner.__annotations__[f"ev_{i}"] = Var[event_type]
    inner.__annotations__["return"] = return_annotation

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
                )
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
    fn.__signature__ = sig  # pyright: ignore [reportFunctionMemberAccess]
    return EventSpec(
        handler=EventHandler(fn=fn, state_full_name=FRONTEND_EVENT_STATE),
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
    is_external: bool = False,
    replace: bool = False,
) -> EventSpec:
    """Redirect to a new path.

    Args:
        path: The path to redirect to.
        is_external: Whether to open in new tab or not.
        replace: If True, the current page will not create a new history entry.

    Returns:
        An event to redirect to the path.
    """
    return server_side(
        "_redirect",
        get_fn_signature(redirect),
        path=path,
        external=is_external,
        replace=replace,
    )


def console_log(message: str | Var[str]) -> EventSpec:
    """Do a console.log on the browser.

    Args:
        message: The message to log.

    Returns:
        An event to log the message.
    """
    return run_script(Var("console").to(dict).log.to(FunctionVar).call(message))


def noop() -> EventSpec:
    """Do nothing.

    Returns:
        An event to do nothing.
    """
    return run_script(Var.create(None))


def back() -> EventSpec:
    """Do a history.back on the browser.

    Returns:
        An event to go back one page.
    """
    return run_script(
        Var("window").to(dict).history.to(dict).back.to(FunctionVar).call()
    )


def window_alert(message: str | Var[str]) -> EventSpec:
    """Create a window alert on the browser.

    Args:
        message: The message to alert.

    Returns:
        An event to alert the message.
    """
    return run_script(Var("window").to(dict).alert.to(FunctionVar).call(message))


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


def scroll_to(elem_id: str, align_to_top: bool | Var[bool] = True) -> EventSpec:
    """Select the id of a html element for scrolling into view.

    Args:
        elem_id: The id of the element to scroll to.
        align_to_top: Whether to scroll to the top (True) or bottom (False) of the element.

    Returns:
        An EventSpec to scroll the page to the selected element.
    """
    get_element_by_id = FunctionStringVar.create("document.getElementById")

    return run_script(
        get_element_by_id.call(elem_id)
        .to(ObjectVar)
        .scrollIntoView.to(FunctionVar)
        .call(align_to_top),
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


def set_clipboard(content: Union[str, Var[str]]) -> EventSpec:
    """Set the text in content in the clipboard.

    Args:
        content: The text to add to clipboard.

    Returns:
        EventSpec: An event to set some content in the clipboard.
    """
    return run_script(
        Var("navigator")
        .to(dict)
        .clipboard.to(dict)
        .writeText.to(FunctionVar)
        .call(content)
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
            )

            # If it's a data: URI, use it as is, otherwise convert the Var to JSON in a data: URI.
            url = cond(
                is_data_url,
                data.to(str),
                "data:text/plain," + data.to_string(),
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


# This function seems unused. Check if we still need it. If not, remove in 0.7.0
def _callback_arg_spec(eval_result: Any):
    """ArgSpec for call_script callback function.

    Args:
        eval_result: The result of the javascript execution.

    Returns:
        Args for the callback function
    """
    return [eval_result]


def call_script(
    javascript_code: str | Var[str],
    callback: EventType[Any] | None = None,
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
            "callback": format.format_queue_events(
                callback,
                args_spec=lambda result: [result],
            )._js_expr,
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


def call_function(
    javascript_code: str | Var,
    callback: EventType[Any] | None = None,
) -> EventSpec:
    """Create an event handler that executes arbitrary javascript code.

    Args:
        javascript_code: The code to execute.
        callback: EventHandler that will receive the result of evaluating the javascript code.

    Returns:
        EventSpec: An event that will execute the client side javascript.
    """
    callback_kwargs = {"callback": None}
    if callback is not None:
        callback_kwargs = {
            "callback": format.format_queue_events(
                callback,
                args_spec=lambda result: [result],
            ),
        }

    javascript_code = (
        Var(javascript_code) if isinstance(javascript_code, str) else javascript_code
    )

    return server_side(
        "_call_function",
        get_fn_signature(call_function),
        function=javascript_code,
        **callback_kwargs,
    )


def run_script(
    javascript_code: str | Var,
    callback: EventType[Any] | None = None,
) -> EventSpec:
    """Create an event handler that executes arbitrary javascript code.

    Args:
        javascript_code: The code to execute.
        callback: EventHandler that will receive the result of evaluating the javascript code.

    Returns:
        EventSpec: An event that will execute the client side javascript.
    """
    javascript_code = (
        Var(javascript_code) if isinstance(javascript_code, str) else javascript_code
    )

    return call_function(ArgsFunctionOperation.create((), javascript_code), callback)


def get_event(state: BaseState, event: str):
    """Get the event from the given state.

    Args:
        state: The state.
        event: The event.

    Returns:
        The event.
    """
    return f"{state.get_name()}.{event}"


def get_hydrate_event(state: BaseState) -> str:
    """Get the name of the hydrate event for the state.

    Args:
        state: The state.

    Returns:
        The name of the hydrate event.
    """
    return get_event(state, constants.CompileVars.HYDRATE)


def call_event_handler(
    event_callback: EventHandler | EventSpec,
    event_spec: ArgsSpec | Sequence[ArgsSpec],
    key: Optional[str] = None,
) -> EventSpec:
    """Call an event handler to get the event spec.

    This function will inspect the function signature of the event handler.
    If it takes in an arg, the arg will be passed to the event handler.
    Otherwise, the event handler will be called with no args.

    Args:
        event_callback: The event handler.
        event_spec: The lambda that define the argument(s) to pass to the event handler.
        key: The key to pass to the event handler.

    Raises:
        EventHandlerArgTypeMismatchError: If the event handler arguments do not match the event spec. #noqa: DAR402
        TypeError: If the event handler arguments are invalid.

    Returns:
        The event spec from calling the event handler.

    #noqa: DAR401
    """
    event_spec_args = parse_args_spec(event_spec)

    if isinstance(event_callback, EventSpec):
        check_fn_match_arg_spec(
            event_callback.handler.fn,
            event_spec,
            key,
            bool(event_callback.handler.state_full_name) + len(event_callback.args),
            event_callback.handler.fn.__qualname__,
        )
        # Handle partial application of EventSpec args
        return event_callback.add_args(*event_spec_args)

    check_fn_match_arg_spec(
        event_callback.fn,
        event_spec,
        key,
        bool(event_callback.state_full_name),
        event_callback.fn.__qualname__,
    )

    all_acceptable_specs = (
        [event_spec] if not isinstance(event_spec, Sequence) else event_spec
    )

    event_spec_return_types = list(
        filter(
            lambda event_spec_return_type: event_spec_return_type is not None
            and get_origin(event_spec_return_type) is tuple,
            (
                get_type_hints(arg_spec).get("return", None)
                for arg_spec in all_acceptable_specs
            ),
        )
    )
    type_match_found: dict[str, bool] = {}
    delayed_exceptions: list[EventHandlerArgTypeMismatchError] = []

    try:
        type_hints_of_provided_callback = get_type_hints(event_callback.fn)
    except NameError:
        type_hints_of_provided_callback = {}

    if event_spec_return_types:
        event_callback_spec = inspect.getfullargspec(event_callback.fn)

        for event_spec_index, event_spec_return_type in enumerate(
            event_spec_return_types
        ):
            args = get_args(event_spec_return_type)

            args_types_without_vars = [
                arg if get_origin(arg) is not Var else get_args(arg)[0] for arg in args
            ]

            # check that args of event handler are matching the spec if type hints are provided
            for i, arg in enumerate(event_callback_spec.args[1:]):
                if arg not in type_hints_of_provided_callback:
                    continue

                type_match_found.setdefault(arg, False)

                try:
                    compare_result = typehint_issubclass(
                        args_types_without_vars[i], type_hints_of_provided_callback[arg]
                    )
                except TypeError as te:
                    raise TypeError(
                        f"Could not compare types {args_types_without_vars[i]} and {type_hints_of_provided_callback[arg]} for argument {arg} of {event_callback.fn.__qualname__} provided for {key}."
                    ) from te

                if compare_result:
                    type_match_found[arg] = True
                    continue
                else:
                    type_match_found[arg] = False
                    delayed_exceptions.append(
                        EventHandlerArgTypeMismatchError(
                            f"Event handler {key} expects {args_types_without_vars[i]} for argument {arg} but got {type_hints_of_provided_callback[arg]} as annotated in {event_callback.fn.__qualname__} instead."
                        )
                    )

            if all(type_match_found.values()):
                delayed_exceptions.clear()
                if event_spec_index:
                    args = get_args(event_spec_return_types[0])

                    args_types_without_vars = [
                        arg if get_origin(arg) is not Var else get_args(arg)[0]
                        for arg in args
                    ]

                    expect_string = ", ".join(
                        repr(arg) for arg in args_types_without_vars
                    ).replace("[", "\\[")

                    given_string = ", ".join(
                        repr(type_hints_of_provided_callback.get(arg, Any))
                        for arg in event_callback_spec.args[1:]
                    ).replace("[", "\\[")

                    console.warn(
                        f"Event handler {key} expects ({expect_string}) -> () but got ({given_string}) -> () as annotated in {event_callback.fn.__qualname__} instead. "
                        f"This may lead to unexpected behavior but is intentionally ignored for {key}."
                    )
                break

    if delayed_exceptions:
        raise delayed_exceptions[0]

    return event_callback(*event_spec_args)


def unwrap_var_annotation(annotation: GenericType):
    """Unwrap a Var annotation or return it as is if it's not Var[X].

    Args:
        annotation: The annotation to unwrap.

    Returns:
        The unwrapped annotation.
    """
    if get_origin(annotation) in (Var, ObjectVar) and (args := get_args(annotation)):
        return args[0]
    return annotation


def resolve_annotation(annotations: dict[str, Any], arg_name: str, spec: ArgsSpec):
    """Resolve the annotation for the given argument name.

    Args:
        annotations: The annotations.
        arg_name: The argument name.
        spec: The specs which the annotations come from.

    Raises:
        MissingAnnotationError: If the annotation is missing for non-lambda methods.

    Returns:
        The resolved annotation.
    """
    annotation = annotations.get(arg_name)
    if annotation is None:
        if not isinstance(spec, types.LambdaType):
            raise MissingAnnotationError(var_name=arg_name)
        else:
            return dict[str, dict]
    return annotation


def parse_args_spec(arg_spec: ArgsSpec | Sequence[ArgsSpec]):
    """Parse the args provided in the ArgsSpec of an event trigger.

    Args:
        arg_spec: The spec of the args.

    Returns:
        The parsed args.
    """
    # if there's multiple, the first is the default
    arg_spec = arg_spec[0] if isinstance(arg_spec, Sequence) else arg_spec
    spec = inspect.getfullargspec(arg_spec)
    annotations = get_type_hints(arg_spec)

    return list(
        arg_spec(
            *[
                Var(f"_{l_arg}").to(
                    unwrap_var_annotation(
                        resolve_annotation(
                            annotations,
                            l_arg,
                            spec=arg_spec,
                        )
                    )
                )
                for l_arg in spec.args
            ]
        )
    )


def check_fn_match_arg_spec(
    user_func: Callable,
    arg_spec: ArgsSpec | Sequence[ArgsSpec],
    key: str | None = None,
    number_of_bound_args: int = 0,
    func_name: str | None = None,
):
    """Ensures that the function signature matches the passed argument specification
    or raises an EventFnArgMismatchError if they do not.

    Args:
        user_func: The function to be validated.
        arg_spec: The argument specification for the event trigger.
        key: The key of the event trigger.
        number_of_bound_args: The number of bound arguments to the function.
        func_name: The name of the function to be validated.

    Raises:
        EventFnArgMismatchError: Raised if the number of mandatory arguments do not match
    """
    user_args = inspect.getfullargspec(user_func).args
    # Drop the first argument if it's a bound method
    if inspect.ismethod(user_func) and user_func.__self__ is not None:
        user_args = user_args[1:]

    user_default_args = inspect.getfullargspec(user_func).defaults
    number_of_user_args = len(user_args) - number_of_bound_args
    number_of_user_default_args = len(user_default_args) if user_default_args else 0

    parsed_event_args = parse_args_spec(arg_spec)

    number_of_event_args = len(parsed_event_args)

    if number_of_user_args - number_of_user_default_args > number_of_event_args:
        raise EventFnArgMismatchError(
            f"Event {key} only provides {number_of_event_args} arguments, but "
            f"{func_name or user_func} requires at least {number_of_user_args - number_of_user_default_args} "
            "arguments to be passed to the event handler.\n"
            "See https://reflex.dev/docs/events/event-arguments/"
        )


def call_event_fn(
    fn: Callable,
    arg_spec: ArgsSpec | Sequence[ArgsSpec],
    key: Optional[str] = None,
) -> list[EventSpec] | Var:
    """Call a function to a list of event specs.

    The function should return a single EventSpec, a list of EventSpecs, or a
    single Var.

    Args:
        fn: The function to call.
        arg_spec: The argument spec for the event trigger.
        key: The key to pass to the event handler.

    Returns:
        The event specs from calling the function or a Var.

    Raises:
        EventHandlerValueError: If the lambda returns an unusable value.
    """
    # Import here to avoid circular imports.
    from reflex.event import EventHandler, EventSpec
    from reflex.utils.exceptions import EventHandlerValueError

    # Check that fn signature matches arg_spec
    check_fn_match_arg_spec(fn, arg_spec, key=key)

    parsed_args = parse_args_spec(arg_spec)

    number_of_fn_args = len(inspect.getfullargspec(fn).args)

    # Call the function with the parsed args.
    out = fn(*[*parsed_args][:number_of_fn_args])

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
            e = call_event_handler(e, arg_spec, key=key)

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

    return event_spec.args if len(args) > 1 else ()


def fix_events(
    events: list[EventSpec | EventHandler] | None,
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
        payload = {k._js_expr: v._decode() for k, v in e.args}

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
        FRONTEND_EVENT_STATE, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Any
    )
    return signature.replace(parameters=(new_param, *signature.parameters.values()))


class EventVar(ObjectVar, python_types=EventSpec):
    """Base class for event vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralEventVar(VarOperationCall, LiteralVar, EventVar):
    """A literal event var."""

    _var_value: EventSpec = dataclasses.field(default=None)  # pyright: ignore [reportAssignmentType]

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((type(self).__name__, self._js_expr))

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


class EventChainVar(BuilderFunctionVar, python_types=EventChain):
    """Base class for event chain vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
# Note: LiteralVar is second in the inheritance list allowing it act like a
# CachedVarOperation (ArgsFunctionOperation) and get the _js_expr from the
# _cached_var_name property.
class LiteralEventChainVar(ArgsFunctionOperationBuilder, LiteralVar, EventChainVar):
    """A literal event chain var."""

    _var_value: EventChain = dataclasses.field(default=None)  # pyright: ignore [reportAssignmentType]

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((type(self).__name__, self._js_expr))

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

        Raises:
            ValueError: If the invocation is not a FunctionVar.
        """
        arg_spec = (
            value.args_spec[0]
            if isinstance(value.args_spec, Sequence)
            else value.args_spec
        )
        sig = inspect.signature(arg_spec)  # pyright: ignore [reportArgumentType]
        if sig.parameters:
            arg_def = tuple((f"_{p}" for p in sig.parameters))
            arg_def_expr = LiteralVar.create([Var(_js_expr=arg) for arg in arg_def])
        else:
            # add a default argument for addEvents if none were specified in value.args_spec
            # used to trigger the preventDefault() on the event.
            arg_def = ("...args",)
            arg_def_expr = Var(_js_expr="args")

        if value.invocation is None:
            invocation = FunctionStringVar.create(
                CompileVars.ADD_EVENTS,
                _var_data=VarData(
                    imports=Imports.EVENTS,
                    hooks={Hooks.EVENTS: None},
                ),
            )
        else:
            invocation = value.invocation

        if invocation is not None and not isinstance(invocation, FunctionVar):
            raise ValueError(
                f"EventChain invocation must be a FunctionVar, got {invocation!s} of type {invocation._var_type!s}."
            )

        return cls(
            _js_expr="",
            _var_type=EventChain,
            _var_data=_var_data,
            _args=FunctionArgs(arg_def),
            _return_expr=invocation.call(
                LiteralVar.create([LiteralVar.create(event) for event in value.events]),
                arg_def_expr,
                value.event_actions,
            ),
            _var_value=value,
        )


P = TypeVarTuple("P")
Q = TypeVarTuple("Q")
T = TypeVar("T")
V = TypeVar("V")
V2 = TypeVar("V2")
V3 = TypeVar("V3")
V4 = TypeVar("V4")
V5 = TypeVar("V5")


class EventCallback(Generic[Unpack[P]], EventActionsMixin):
    """A descriptor that wraps a function to be used as an event."""

    def __init__(self, func: Callable[[Any, Unpack[P]], Any]):
        """Initialize the descriptor with the function to be wrapped.

        Args:
            func: The function to be wrapped.
        """
        self.func = func

    @overload
    def __call__(
        self: EventCallback[Unpack[Q]],
    ) -> EventCallback[Unpack[Q]]: ...

    @overload
    def __call__(
        self: EventCallback[V, Unpack[Q]], value: V | Var[V]
    ) -> EventCallback[Unpack[Q]]: ...

    @overload
    def __call__(
        self: EventCallback[V, V2, Unpack[Q]],
        value: V | Var[V],
        value2: V2 | Var[V2],
    ) -> EventCallback[Unpack[Q]]: ...

    @overload
    def __call__(
        self: EventCallback[V, V2, V3, Unpack[Q]],
        value: V | Var[V],
        value2: V2 | Var[V2],
        value3: V3 | Var[V3],
    ) -> EventCallback[Unpack[Q]]: ...

    @overload
    def __call__(
        self: EventCallback[V, V2, V3, V4, Unpack[Q]],
        value: V | Var[V],
        value2: V2 | Var[V2],
        value3: V3 | Var[V3],
        value4: V4 | Var[V4],
    ) -> EventCallback[Unpack[Q]]: ...

    def __call__(self, *values) -> EventCallback:  # pyright: ignore [reportInconsistentOverload]
        """Call the function with the values.

        Args:
            *values: The values to call the function with.

        Returns:
            The function with the values.
        """
        return self.func(*values)  # pyright: ignore [reportArgumentType]

    @overload
    def __get__(
        self: EventCallback[Unpack[P]], instance: None, owner: Any
    ) -> EventCallback[Unpack[P]]: ...

    @overload
    def __get__(self, instance: Any, owner: Any) -> Callable[[Unpack[P]]]: ...

    def __get__(self, instance: Any, owner: Any) -> Callable:
        """Get the function with the instance bound to it.

        Args:
            instance: The instance to bind to the function.
            owner: The owner of the function.

        Returns:
            The function with the instance bound to it
        """
        if instance is None:
            return self.func

        return partial(self.func, instance)


class LambdaEventCallback(Protocol[Unpack[P]]):
    """A protocol for a lambda event callback."""

    @overload
    def __call__(self: LambdaEventCallback[()]) -> Any: ...

    @overload
    def __call__(self: LambdaEventCallback[V], value: Var[V], /) -> Any: ...

    @overload
    def __call__(
        self: LambdaEventCallback[V, V2], value: Var[V], value2: Var[V2], /
    ) -> Any: ...

    @overload
    def __call__(
        self: LambdaEventCallback[V, V2, V3],
        value: Var[V],
        value2: Var[V2],
        value3: Var[V3],
        /,
    ) -> Any: ...

    def __call__(self, *args: Var) -> Any:
        """Call the lambda with the args.

        Args:
            *args: The args to call the lambda with.
        """


ARGS = TypeVarTuple("ARGS")


LAMBDA_OR_STATE = TypeAliasType(
    "LAMBDA_OR_STATE",
    LambdaEventCallback[Unpack[ARGS]] | EventCallback[Unpack[ARGS]],
    type_params=(ARGS,),
)

ItemOrList = V | List[V]

BASIC_EVENT_TYPES = TypeAliasType(
    "BASIC_EVENT_TYPES", EventSpec | EventHandler | Var[Any], type_params=()
)

IndividualEventType = TypeAliasType(
    "IndividualEventType",
    LAMBDA_OR_STATE[Unpack[ARGS]] | BASIC_EVENT_TYPES,
    type_params=(ARGS,),
)

EventType = TypeAliasType(
    "EventType", ItemOrList[IndividualEventType[Unpack[ARGS]]], type_params=(ARGS,)
)


if TYPE_CHECKING:
    from reflex.state import BaseState

    BASE_STATE = TypeVar("BASE_STATE", bound=BaseState)
else:
    BASE_STATE = TypeVar("BASE_STATE")


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
    EventType = EventType
    EventCallback = EventCallback

    @overload
    @staticmethod
    def __call__(
        func: None = None, *, background: bool | None = None
    ) -> Callable[
        [Callable[[BASE_STATE, Unpack[P]], Any]], EventCallback[Unpack[P]]  # pyright: ignore [reportInvalidTypeVarUse]
    ]: ...

    @overload
    @staticmethod
    def __call__(
        func: Callable[[BASE_STATE, Unpack[P]], Any],
        *,
        background: bool | None = None,
    ) -> EventCallback[Unpack[P]]: ...

    @staticmethod
    def __call__(
        func: Callable[[BASE_STATE, Unpack[P]], Any] | None = None,
        *,
        background: bool | None = None,
    ) -> Union[
        EventCallback[Unpack[P]],
        Callable[[Callable[[BASE_STATE, Unpack[P]], Any]], EventCallback[Unpack[P]]],
    ]:
        """Wrap a function to be used as an event.

        Args:
            func: The function to wrap.
            background: Whether the event should be run in the background. Defaults to False.

        Raises:
            TypeError: If background is True and the function is not a coroutine or async generator. # noqa: DAR402

        Returns:
            The wrapped function.
        """

        def wrapper(
            func: Callable[[BASE_STATE, Unpack[P]], T],
        ) -> EventCallback[Unpack[P]]:
            if background is True:
                if not inspect.iscoroutinefunction(
                    func
                ) and not inspect.isasyncgenfunction(func):
                    raise TypeError(
                        "Background task must be async function or generator."
                    )
                setattr(func, BACKGROUND_TASK_MARKER, True)
            return func  # pyright: ignore [reportReturnType]

        if func is not None:
            return wrapper(func)
        return wrapper

    get_event = staticmethod(get_event)
    get_hydrate_event = staticmethod(get_hydrate_event)
    fix_events = staticmethod(fix_events)
    call_event_handler = staticmethod(call_event_handler)
    call_event_fn = staticmethod(call_event_fn)
    get_handler_args = staticmethod(get_handler_args)
    check_fn_match_arg_spec = staticmethod(check_fn_match_arg_spec)
    resolve_annotation = staticmethod(resolve_annotation)
    parse_args_spec = staticmethod(parse_args_spec)
    passthrough_event_spec = staticmethod(passthrough_event_spec)
    input_event = staticmethod(input_event)
    key_event = staticmethod(key_event)
    no_args_event_spec = staticmethod(no_args_event_spec)
    server_side = staticmethod(server_side)
    redirect = staticmethod(redirect)
    console_log = staticmethod(console_log)
    noop = staticmethod(noop)
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
    call_function = staticmethod(call_function)
    run_script = staticmethod(run_script)


event = EventNamespace()
