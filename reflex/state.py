"""Define the reflex state specification."""

from __future__ import annotations

import builtins
import contextlib
import copy
import dataclasses
import functools
import inspect
import logging
import pickle
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import timedelta
from hashlib import md5
from types import FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    ClassVar,
    ParamSpec,
    TypeVar,
    cast,
    get_type_hints,
    overload,
)

from reflex_base import constants
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.environment import PerformanceMode, auto_reload_cooldown, environment
from reflex_base.event import (
    EVENT_ACTIONS_MARKER,
    Event,
    EventHandler,
    EventSpec,
    call_script,
)
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import (
    DynamicComponentInvalidSignatureError,
    DynamicRouteArgShadowsStateVarError,
    ReflexRuntimeError,
    SetUndefinedStateVarError,
    StateMismatchError,
    StateSchemaMismatchError,
    StateSerializationError,
    StateTooLargeError,
    UnretrievableVarValueError,
)
from reflex_base.utils.exceptions import ImmutableStateError as ImmutableStateError
from reflex_base.utils.serializers import serializer
from reflex_base.utils.types import _isinstance
from reflex_base.vars import Field, VarData, field
from reflex_base.vars.base import (
    ComputedVar,
    DynamicRouteVar,
    EvenMoreBasicBaseState,
    ToOperation,
    Var,
    _inherited_value,
    _is_descriptor,
    _validate_state_name,
    computed_var,
    dispatch,
    is_computed_var,
)
from rich.markup import escape
from typing_extensions import Self

import reflex.istate.dynamic
from reflex import event
from reflex.istate import HANDLED_PICKLE_ERRORS, debug_failed_pickles
from reflex.istate.data import (
    HeaderData,
    PageData,
    ReflexURL,
    RouterData,
    RouterDataVar,
    SessionData,
    URLData,
)
from reflex.istate.delta import (
    Delta,
    DeltaMapping,
    _resolve_delta,
    build_delta,
    clean_state,
    resolve_delta,
)
from reflex.istate.proxy import ImmutableMutableProxy as ImmutableMutableProxy
from reflex.istate.proxy import MutableProxy
from reflex.istate.storage import ClientStorageBase
from reflex.utils import console, format, types
from reflex.utils.exec import is_testing_env

# Keys of older pickles that are no longer stored in the instance dict: the
# RouterData from before the router split (not `constants.ROUTER`: the name is
# frozen into payloads already on disk), and the dirty tracking now in slots.
_LEGACY_PICKLE_KEYS = ("router", "dirty_vars", "dirty_substates")

# Shared empty router defaults. Each is a frozen dataclass whose members are
# themselves immutable, so one instance can back every state's field instead
# of being rebuilt per state.
_DEFAULT_SESSION_DATA = SessionData()
_DEFAULT_HEADER_DATA = HeaderData()
_DEFAULT_URL_DATA = URLData()

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from reflex_base.components.component import Component


var = computed_var


if environment.REFLEX_PERF_MODE.get() != PerformanceMode.OFF:
    # If the state is this large, it's considered a performance issue.
    TOO_LARGE_SERIALIZED_STATE = environment.REFLEX_STATE_SIZE_LIMIT.get() * 1024
    # Only warn about each state class size once.
    _WARNED_ABOUT_STATE_SIZE: set[str] = set()


# For BaseState.get_var_value
VAR_TYPE = TypeVar("VAR_TYPE")


def _substate_key(
    token: str,
    state_cls_or_name: BaseState | type[BaseState] | str | Sequence[str],
) -> str:
    """Get the substate key.

    Args:
        token: The token of the state.
        state_cls_or_name: The state class/instance or name or sequence of name parts.

    Returns:
        The substate key.
    """
    if isinstance(state_cls_or_name, BaseState) or (
        isinstance(state_cls_or_name, type) and issubclass(state_cls_or_name, BaseState)
    ):
        state_cls_or_name = state_cls_or_name.get_full_name()
    elif isinstance(state_cls_or_name, (list, tuple)):
        state_cls_or_name = ".".join(state_cls_or_name)
    return f"{token}_{state_cls_or_name}"


def _split_substate_key(substate_key: str) -> tuple[str, str]:
    """Split the substate key into token and state name.

    Args:
        substate_key: The substate key.

    Returns:
        Tuple of token and state name.
    """
    token, _, state_name = substate_key.partition("_")
    return token, state_name


@dataclasses.dataclass(frozen=True, init=False)
class EventHandlerSetVar(EventHandler):
    """A special event handler to wrap setvar functionality."""

    def __init__(self, state_cls: type[BaseState]):
        """Initialize the EventHandlerSetVar.

        Args:
            state_cls: The state class that vars will be set on.
        """
        super().__init__(
            fn=type(self).setvar,
            state=state_cls,
        )

    def __hash__(self):
        """Get the hash of the event handler.

        Returns:
            The hash of the event handler.
        """
        return hash((
            tuple(self.event_actions.items()),
            self.fn,
            self.state_full_name,
            self.state,
        ))

    def setvar(self, var_name: str, value: Any):
        """Set the state variable to the value of the event.

        Note: `self` here will be an instance of the state, not EventHandlerSetVar.

        Args:
            var_name: The name of the variable to set.
            value: The value to set the variable to.
        """
        getattr(self, constants.SETTER_PREFIX + var_name)(value)

    def __call__(self, *args: Any) -> EventSpec:
        """Performs pre-checks and munging on the provided args that will become an EventSpec.

        Args:
            *args: The event args.

        Returns:
            The (partial) EventSpec that will be used to create the event to setvar.

        Raises:
            AttributeError: If the given Var name does not exist on the state.
            EventHandlerValueError: If the given Var name is not a str
            NotImplementedError: If the setter for the given Var is async
        """
        from reflex_base.utils.exceptions import EventHandlerValueError

        if args:
            if not isinstance(args[0], str):
                msg = f"Var name must be passed as a string, got {args[0]!r}"
                raise EventHandlerValueError(msg)

            handler = getattr(self.state, constants.SETTER_PREFIX + args[0], None)

            # Check that the requested Var setter exists on the State at compile time.
            if handler is None:
                msg = f"Variable `{args[0]}` cannot be set on `{self.state_full_name}`"
                raise AttributeError(msg)

            if inspect.iscoroutinefunction(handler.fn):
                msg = f"Setter for {args[0]} is async, which is not supported."
                raise NotImplementedError(msg)

        return super().__call__(*args)


def get_var_for_field(cls: type[BaseState], name: str, f: Field) -> Var:
    """Get a Var instance for a state field.

    Args:
        cls: The state class.
        name: The name of the field.
        f: The Field instance.

    Returns:
        The Var instance.
    """
    field_name = (
        format.format_state_name(cls.get_full_name()) + "." + name + FIELD_MARKER
    )

    return dispatch(
        field_name=field_name,
        var_data=VarData.from_state(cls, name),
        result_var_type=f.outer_type_,
    )


RETURN = TypeVar("RETURN")
PARAMS = ParamSpec("PARAMS")


def _override_base_method(fn: Callable[PARAMS, RETURN]) -> Callable[PARAMS, RETURN]:
    """Mark a method as overriding a base method.

    Args:
        fn: The function to mark.

    Returns:
        The marked function.
    """
    fn.__override_base_method__ = True  # pyright: ignore[reportFunctionMemberAccess]
    return fn


def _has_data_descriptor(cls: type, name: str) -> bool:
    """Whether the class provides a descriptor that handles assignment for `name`.

    Reads the class dicts directly; `getattr` would run the descriptor.

    Args:
        cls: The class to look the name up on.
        name: The attribute name.

    Returns:
        True if the first class defining the name binds it to a data descriptor.
    """
    for klass in cls.__mro__:
        if name in klass.__dict__:
            return hasattr(type(klass.__dict__[name]), "__set__")
    return False


def _bind_attr(cls: type, name: str, value: Any) -> None:
    """Set a descriptor on a class, binding it to the class as class creation does.

    Args:
        cls: The class.
        name: The attribute name.
        value: The descriptor.
    """
    setattr(cls, name, value)
    value.__set_name__(cls, name)


def _router_fget(self: BaseState) -> RouterData:
    """Assemble the RouterData view over the per-field router vars.

    Args:
        self: The state instance.

    Returns:
        The RouterData for the current connection and page.
    """
    return RouterData(
        session=self.rx_router_session,
        headers=self.rx_router_headers,
        _page=self.rx_router_page,
        # URLData.href always holds a ReflexURL at runtime (see URLData).
        url=cast("ReflexURL", self.rx_router_url.href),
        route_id=self.rx_router_route_id,
    )


def _router_fset(self: BaseState, value: RouterData) -> None:
    """Decompose a RouterData assignment into the per-field router vars.

    Args:
        self: The state instance.
        value: The RouterData to store.
    """
    self.rx_router_session = value.session
    self.rx_router_headers = value.headers
    self.rx_router_page = value._page
    self.rx_router_url = URLData.from_url(value.url)
    self.rx_router_route_id = value.route_id


def _get_router_var(cls: type[BaseState]) -> RouterDataVar:
    """Get (or build and cache) the router switchboard var for a state class.

    Args:
        cls: The state class the ``router`` attribute was accessed on.

    Returns:
        The RouterDataVar over the root state's per-field router vars.
    """
    root_cls = cls.get_root_state()
    router_var = root_cls.__dict__.get("_reflex_router_var")
    if router_var is None:
        base_vars = root_cls.base_vars
        if constants.ROUTER_SESSION not in base_vars:
            # BaseState itself and mixins never initialize base vars; give
            # introspection-style access an unbound switchboard.
            return RouterDataVar(_js_expr="", _var_type=RouterData)
        router_var = RouterDataVar.create(
            session=base_vars[constants.ROUTER_SESSION],
            headers=base_vars[constants.ROUTER_HEADERS],
            page=base_vars[constants.ROUTER_PAGE],
            url=base_vars[constants.ROUTER_URL],
            route_id=base_vars[constants.ROUTER_ROUTE_ID],
            # Name the `router` attribute the switchboard stands for, so
            # `get_var_value(State.router)` resolves it through the property
            # and hands back the composed RouterData, as it does on a state
            # with a single `router` base var.
            _var_data=VarData(
                state=root_cls.get_full_name(), field_name=constants.ROUTER
            ),
        )
        setattr(root_cls, "_reflex_router_var", router_var)  # noqa: B010
    return router_var


class _RouterDescriptor(property):
    """Property exposing the per-field router vars as a single ``router`` attribute.

    Instance access composes a ``RouterData`` view from the per-field router
    vars and assignment decomposes one into them, so existing reads and writes
    of ``state.router`` keep working unchanged. Class-level access returns the
    ``RouterDataVar`` switchboard, resolving ``State.router.<attr>`` to the
    underlying per-field base var. Subclassing ``property`` keeps the state
    field machinery from treating this as a base var and lets ComputedVar
    dependency tracking recurse into the getter, so any computed var reading
    ``self.router`` depends on the per-field vars.
    """

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: type, /) -> RouterDataVar: ...

        @overload
        def __get__(self, instance: BaseState, owner: type, /) -> RouterData: ...

        def __get__(self, instance: Any, owner: type | None = None, /) -> Any:
            """Get the switchboard var (class) or RouterData view (instance).

            Args:
                instance: The state instance, or None for class access.
                owner: The class through which the attribute was accessed.

            Returns:
                The RouterDataVar for class access, or the RouterData view.
            """

        def __set__(self, instance: Any, value: RouterData) -> None:
            """Set the router data on the instance.

            Args:
                instance: The state instance.
                value: The RouterData to store.
            """

    else:

        def __get__(self, instance: Any, owner: type | None = None, /):
            """Get the switchboard var (class) or RouterData view (instance).

            Args:
                instance: The state instance, or None for class access.
                owner: The class through which the attribute was accessed.

            Returns:
                The RouterDataVar for class access, or the RouterData view.
            """
            if instance is None:
                return _get_router_var(owner)
            return super().__get__(instance, owner)


all_base_state_classes: dict[str, None] = {}

# Per state class, the names its dev-mode __setattr__ has found declared.
_SETTABLE_NAMES: dict[type, set[str]] = {}

# The fields holding router data, which reset() leaves alone.
_ROUTER_FIELD_NAMES = frozenset((*constants.ROUTER_VARS, constants.ROUTER_DATA))


class BaseState(EvenMoreBasicBaseState, state_root=True):
    """The state of the app."""

    # A map from the var name to the var.
    vars: ClassVar[builtins.dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[builtins.dict[str, Var]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[builtins.dict[str, ComputedVar]] = {}

    # The event handlers.
    event_handlers: ClassVar[builtins.dict[str, EventHandler]] = {}

    # Mapping of var name to set of (state_full_name, var_name) that depend on it.
    _var_dependencies: ClassVar[builtins.dict[str, set[tuple[str, str]]]] = {}

    # Set of vars which always need to be recomputed
    _always_dirty_computed_vars: ClassVar[set[str]] = set()

    # Set of substates which always need to be recomputed
    _always_dirty_substates: ClassVar[set[str]] = set()

    # Set of states which might need to be recomputed if vars in this state change.
    _potentially_dirty_states: ClassVar[set[str]] = set()

    # Vars on this class sent to the client, and computed vars that expire on
    # an interval; recomputed with the dependency dicts, i.e. at class creation
    # and after any var is added.
    _frontend_var_names: ClassVar[frozenset[str]] = frozenset()
    _interval_computed_var_names: ClassVar[frozenset[str]] = frozenset()

    # Instance bookkeeping, kept out of `__dict__`: never a field, never pickled.
    __slots__ = (
        "_was_touched",
        "dirty_substates",
        "dirty_vars",
        "parent_state",
        "substates",
    )
    if TYPE_CHECKING:
        # The parent state.
        parent_state: BaseState | None = field(default=None, is_var=False)
        # The substates of the state.
        substates: builtins.dict[str, BaseState] = field(
            default_factory=builtins.dict, is_var=False
        )
        # The set of dirty vars.
        dirty_vars: set[str] = field(default_factory=set, is_var=False)
        # The set of dirty substates.
        dirty_substates: set[str] = field(default_factory=set, is_var=False)
        # Whether the state was modified since it was last persisted.
        _was_touched: bool = field(default=False, is_var=False)

    # The routing path that triggered the state
    router_data: builtins.dict[str, Any] = field(
        default_factory=builtins.dict, is_var=False
    )

    # The per-connection session data (constant for the socket lifetime).
    # These three defaults are frozen dataclasses holding only immutable
    # members, so every state can share one instance instead of building a
    # fresh one per field per state. `field()` cannot be used for that: it
    # only shares a `default` whose type is in `IMMUTABLE_TYPES`, and
    # otherwise deep-copies it per instance.
    rx_router_session: Field[SessionData] = Field(default=_DEFAULT_SESSION_DATA)

    # The headers of the connection request (constant for the socket lifetime).
    rx_router_headers: Field[HeaderData] = Field(default=_DEFAULT_HEADER_DATA)

    # The page data for the current page (deprecated; params feeds dynamic route vars).
    rx_router_page: Field[PageData] = field(default_factory=PageData)

    # The parsed URL of the current page.
    rx_router_url: Field[URLData] = Field(default=_DEFAULT_URL_DATA)

    # The route pattern that matched the current page.
    rx_router_route_id: Field[str] = field(default="")

    # Switchboard for the router vars above: instance reads compose a
    # RouterData view, writes decompose into the per-field vars, and class
    # access returns the RouterDataVar. Deliberately not a Field: storing each
    # kind of router data in its own base var means a navigation delta only
    # re-sends the navigation-scoped vars, not session/headers.
    router = _RouterDescriptor(_router_fget, _router_fset)

    # A special event handler for setting base vars.
    setvar: ClassVar[EventHandler]

    def __init__(
        self,
        parent_state: BaseState | None = None,
        init_substates: bool = True,
        _reflex_internal_init: bool = False,
        **kwargs,
    ):
        """Initialize the state.

        DO NOT INSTANTIATE STATE CLASSES DIRECTLY! Use StateManager.get_state() instead.

        Args:
            parent_state: The parent state.
            init_substates: Whether to initialize the substates in this instance.
            _reflex_internal_init: A flag to indicate that the state is being initialized by the framework.
            **kwargs: The kwargs to set as attributes on the state.

        Raises:
            ReflexRuntimeError: If the state is instantiated directly by end user.
        """
        from reflex_base.utils.exceptions import ReflexRuntimeError

        if not _reflex_internal_init and not is_testing_env():
            msg = (
                "State classes should not be instantiated directly in a Reflex app. "
                "See https://reflex.dev/docs/state/ for further information."
            )
            raise ReflexRuntimeError(msg)
        if self._mixin:
            msg = f"{type(self).__name__} is a state mixin and cannot be instantiated directly."
            raise ReflexRuntimeError(msg)
        self._init_bookkeeping(parent_state)
        # Field values are set on first access; only the given ones are stored now.
        super().__init__(**kwargs)

        # Setup the substates (for memory state manager only).
        if init_substates:
            for substate in self.get_substates():
                self.substates[substate.get_name()] = substate(
                    parent_state=self,
                    _reflex_internal_init=True,
                )

    def _init_bookkeeping(self, parent_state: BaseState | None = None) -> None:
        """Initialize the instance bookkeeping slots.

        Args:
            parent_state: The parent state.
        """
        setattr_ = object.__setattr__
        setattr_(self, "parent_state", parent_state)
        setattr_(self, "substates", {})
        setattr_(self, "dirty_vars", set())
        setattr_(self, "dirty_substates", set())
        setattr_(self, "_was_touched", False)

    def __repr__(self) -> str:
        """Get the string representation of the state.

        Returns:
            The string representation of the state.
        """
        return f"{type(self).__name__}({self.dict()})"

    @classmethod
    def _validate_module_name(cls) -> None:
        """Check if the module name is valid.

        Reflex uses ___ as state name module separator.

        Raises:
            NameError: If the module name is invalid.
        """
        if "___" in cls.__module__:
            msg = (
                "The module name of a State class cannot contain '___'. "
                "Please rename the module."
            )
            raise NameError(msg)

    @classmethod
    def __init_subclass__(cls, mixin: bool = False, **kwargs):
        """Do some magic for the subclass initialization.

        Args:
            mixin: Whether the subclass is a mixin and should not be initialized.
            **kwargs: The kwargs to pass to the init_subclass method.

        Raises:
            StateValueError: If a substate shadows another.
        """
        from reflex_base.utils.exceptions import StateValueError

        super().__init_subclass__(**kwargs)

        if cls._mixin:
            return

        # Handle locally-defined states for pickling.
        if "<locals>" in cls.__qualname__:
            cls._handle_local_def()

        # Validate the module name.
        cls._validate_module_name()

        # Reset dirty substate tracking for this class.
        cls._always_dirty_substates = set()
        cls._potentially_dirty_states = set()

        parent_state = cls.get_parent_state()
        # Check if another substate class with the same name has already been defined.
        if parent_state is not None and cls.get_name() in {
            c.get_name() for c in parent_state.get_substates()
        }:
            # This should not happen, since we have added module prefix to state names in #3214
            msg = (
                f"The substate class '{cls.get_name()}' has been defined multiple times. "
                "Shadowing substate classes is not allowed."
            )
            raise StateValueError(msg)

        cls._bind_fields()
        cls._bind_mixin_members()

        # Set the base and computed vars.
        cls.base_vars = {
            name: get_var_for_field(cls, name, f)
            for name, f in cls.__fields__.items()
            if f._owner is cls and not f._backend
        }
        cls.computed_vars = {
            name: v._replace(merge_var_data=VarData.from_state(cls))
            for name, v in cls.__dict__.items()
            if is_computed_var(v)
        }
        cls.vars = {
            **(parent_state.vars if parent_state is not None else {}),
            **cls.base_vars,
            **cls.computed_vars,
            # `router` is a switchboard over the per-field router vars rather
            # than a field of its own, but it is usable as a Var everywhere one
            # is accepted, so it is listed here (and thus inherited by
            # substates). It has no backing field, so it never reaches a delta.
            constants.ROUTER: _get_router_var(cls),
        }
        cls.event_handlers = {}

        # Setup the base vars at the class level.
        for name, prop in cls.base_vars.items():
            cls._init_var(name, prop)

        # Create the setvar event handler for this state
        cls._create_setvar()

        # Set up the event handlers.
        for name, fn in list(cls.__dict__.items()):
            if cls._item_is_event_handler(name, fn):
                handler = cls._create_event_handler(fn)
                cls.event_handlers[name] = handler
                setattr(cls, name, handler)

        RegistrationContext.register_base_state(cls)

        # Initialize per-class var dependency tracking.
        cls._var_dependencies = {}
        cls._init_var_dependency_dicts()

        all_base_state_classes[cls.get_full_name()] = None

    @classmethod
    def _bind_fields(cls) -> None:
        """Bind the fields this class gets from mixins or plain bases to it.

        A field declared on this class or a parent state stays bound where it
        is declared: its value lives on that state's instance. One declared on
        a mixin or non-state base gets a copy bound to this class.
        """
        tree_states = set()
        state_cls: type[BaseState] | None = cls
        while state_cls is not None:
            tree_states.add(state_cls)
            state_cls = state_cls.get_parent_state()
        fields = cls.__fields__
        for name, declared in list(fields.items()):
            f = _inherited_value(cls.__mro__, name)
            if not isinstance(f, Field):
                if callable(f) or _is_descriptor(f):
                    # Overridden by something else, like a property.
                    del fields[name]
                    continue
                # Declared by a plain base, which holds no field of its own.
                f = declared
            if f._owner not in tree_states:
                f = f._copy()
                _bind_attr(cls, name, f)
            fields[name] = f

    @classmethod
    def _bind_mixin_members(cls) -> None:
        """Copy the computed vars and event handler functions of mixins onto this class.

        A member is copied only where this class resolves the name to the mixin's
        member, so this class or an earlier base overrides it as usual.
        """
        for mixin_cls in cls._mixins():
            for name, value in mixin_cls.__dict__.items():
                if _inherited_value(cls.__mro__, name) is not value:
                    continue
                if is_computed_var(value):
                    _bind_attr(
                        cls,
                        name,
                        value._replace(
                            fget=cls._copy_fn(value.fget),
                            _var_data=VarData.from_state(cls),
                        ),
                    )
                elif cls._item_is_event_handler(name, value):
                    fn = cls._copy_fn(value)
                    fn.__qualname__ = f"{cls.__name__}.{name}"
                    setattr(cls, name, fn)

    @classmethod
    def _add_event_handler(
        cls,
        name: str,
        fn: Callable,
    ):
        """Add an event handler dynamically to the state.

        Args:
            name: The name of the event handler.
            fn: The function to call when the event is triggered.
        """
        _validate_state_name(cls._reflex_state_root, name)
        handler = cls._create_event_handler(fn)
        cls.event_handlers[name] = handler
        setattr(cls, name, handler)

    @staticmethod
    def _copy_fn(fn: Callable) -> Callable:
        """Copy a function. Used to copy ComputedVars and EventHandlers from mixins.

        Args:
            fn: The function to copy.

        Returns:
            The copied function.
        """
        newfn = FunctionType(
            fn.__code__,
            fn.__globals__,
            name=fn.__name__,
            argdefs=fn.__defaults__,
            closure=fn.__closure__,
        )
        newfn.__annotations__ = fn.__annotations__
        newfn.__kwdefaults__ = fn.__kwdefaults__
        newfn.__dict__.update(fn.__dict__)
        return newfn

    @staticmethod
    def _item_is_event_handler(name: str, value: Any) -> bool:
        """Check if the item is an event handler.

        Args:
            name: The name of the item.
            value: The value of the item.

        Returns:
            Whether the item is an event handler.
        """
        return (
            not name.startswith("_")
            and isinstance(value, Callable)
            and not isinstance(value, EventHandler)
            and not getattr(value, "__override_base_method__", False)
            and hasattr(value, "__code__")
        )

    @classmethod
    def _evaluate(cls, f: Callable[[Self], Any], of_type: type | None = None) -> Var:
        """Evaluate a function to a ComputedVar. Experimental.

        Args:
            f: The function to evaluate.
            of_type: The type of the ComputedVar. Defaults to Component.

        Returns:
            The ComputedVar.
        """
        logger.warning(
            "The _evaluate method is experimental and may be removed in future versions."
        )
        from reflex_base.components.component import Component

        of_type = of_type or Component

        unique_var_name = (
            ("dynamic_" + f.__module__ + "_" + f.__qualname__)
            .replace("<", "")
            .replace(">", "")
            .replace(".", "_")
        )

        while unique_var_name in cls.vars:
            unique_var_name += "_"

        def computed_var_func(state: Self):
            result = f(state)

            if not _isinstance(result, of_type, nested=1, treat_var_as_type=False):
                logger.warning(
                    f"Inline ComputedVar {f} expected type {of_type}, got {type(result)}. "
                    "You can specify expected type with `of_type` argument."
                )

            return result

        computed_var_func.__name__ = unique_var_name

        computed_var_func_arg = computed_var(return_type=of_type, cache=False)(
            computed_var_func
        )

        _bind_attr(cls, unique_var_name, computed_var_func_arg)
        cls.computed_vars[unique_var_name] = computed_var_func_arg
        cls.vars[unique_var_name] = computed_var_func_arg
        cls._update_substate_vars({unique_var_name: computed_var_func_arg})
        cls._always_dirty_computed_vars.add(unique_var_name)

        return getattr(cls, unique_var_name)

    @classmethod
    def _mixins(cls) -> tuple[type[BaseState], ...]:
        """Get the mixin classes of the state.

        Returns:
            The mixin classes of the state.
        """
        return tuple(
            mixin
            for mixin in cls.__mro__
            if (
                mixin is not cls
                and issubclass(mixin, BaseState)
                and mixin._mixin is True
            )
        )

    @classmethod
    def _handle_local_def(cls):
        """Handle locally-defined states for pickling."""
        known_names = dir(reflex.istate.dynamic)
        proposed_name = cls.__name__
        for ix in range(len(known_names)):
            if proposed_name not in known_names:
                break
            proposed_name = f"{cls.__name__}_{ix}"
        setattr(reflex.istate.dynamic, proposed_name, cls)
        cls.__original_name__ = cls.__name__
        cls.__original_module__ = cls.__module__
        cls.__name__ = cls.__qualname__ = proposed_name
        cls.__module__ = reflex.istate.dynamic.__name__

    @classmethod
    @functools.cache
    def _get_type_hints(cls) -> builtins.dict[str, Any]:
        """Get the type hints for this class.

        If the class is dynamic, evaluate the type hints with the original
        module in the local namespace.

        Returns:
            The type hints dict.
        """
        original_module = getattr(cls, "__original_module__", None)
        if original_module is not None:
            localns = sys.modules[original_module].__dict__
        else:
            localns = None

        return get_type_hints(cls, localns=localns)

    @classmethod
    def _init_var_dependency_dicts(cls):
        """Initialize the var dependency tracking dicts.

        Allows the state to know which vars each ComputedVar depends on and
        whether a ComputedVar depends on a var in its parent state.

        Additional updates tracking dicts for vars and substates that always
        need to be recomputed.
        """
        cls._frontend_var_names = frozenset(cls.base_vars).union(
            name for name, cvar in cls.computed_vars.items() if not cvar._backend
        )
        cls._interval_computed_var_names = frozenset(
            name
            for name, cvar in cls.computed_vars.items()
            if cvar._update_interval is not None
        )
        for cvar_name, cvar in cls.computed_vars.items():
            if not cvar._cache:
                # Do not perform dep calculation when cache=False (these are always dirty).
                continue
            for state_name, dvar_set in cvar._deps(objclass=cls).items():
                if constants.ROUTER in dvar_set:
                    # `router` names the switchboard, which has no field of its
                    # own: depend on the per-field router vars instead. The Var
                    # form already carries them, so only the legacy string form
                    # arrives here without them, and only it is deprecated.
                    if dvar_set.isdisjoint(constants.ROUTER_VARS):
                        console.deprecate(
                            feature_name=f'ComputedVar deps=["router"] on {cls.__name__}.{cvar_name}',
                            reason="the router var was split; depend on the router"
                            " Var instead (e.g. deps=[State.router.url] for one"
                            " field, or deps=[State.router] for all of them).",
                            deprecation_version="0.9.12",
                            removal_version="1.0",
                        )
                    dvar_set = (dvar_set - {constants.ROUTER}) | set(
                        constants.ROUTER_VARS
                    )
                state_cls = cls.get_root_state().get_class_substate(state_name)
                for dvar in dvar_set:
                    # The var is tracked on the state its descriptor is bound to.
                    desc = _inherited_value(state_cls.__mro__, dvar)
                    owner = (
                        desc._owner
                        if isinstance(desc, Field) or is_computed_var(desc)
                        else None
                    )
                    defining_state_cls = owner or state_cls
                    defining_state_cls._var_dependencies.setdefault(dvar, set()).add((
                        cls.get_full_name(),
                        cvar_name,
                    ))
                    defining_state_cls._potentially_dirty_states.add(
                        cls.get_full_name()
                    )

        # ComputedVar with cache=False always need to be recomputed
        cls._always_dirty_computed_vars = {
            cvar_name
            for cvar_name, cvar in cls.computed_vars.items()
            if not cvar._cache
        }

        # Any substate containing a ComputedVar with cache=False always needs to be recomputed
        if cls._always_dirty_computed_vars:
            # Tell parent classes that this substate has always dirty computed vars
            state_name = cls.get_name()
            parent_state = cls.get_parent_state()
            while parent_state is not None:
                parent_state._always_dirty_substates.add(state_name)
                state_name, parent_state = (
                    parent_state.get_name(),
                    parent_state.get_parent_state(),
                )

        # Reset cached schema value
        cls._to_schema.cache_clear()

    @classmethod
    def _iter_functions(cls) -> Iterator[tuple[str, FunctionType]]:
        """Iterate over the functions defined on the class and its bases.

        Equivalent to `inspect.getmembers(cls, inspect.isfunction)`, except that
        the class dicts are read directly instead of going through `getattr`, so
        descriptors are not evaluated. Evaluating them here would run user code
        (e.g. a hybrid property building its frontend var) while the class is
        still being constructed.

        Yields:
            The name and function of each function defined on the class or its bases.
        """
        seen: set[str] = set()
        for klass in cls.__mro__:
            for name, value in klass.__dict__.items():
                if name in seen:
                    continue
                seen.add(name)
                if isinstance(value, staticmethod):
                    value = value.__func__
                if isinstance(value, FunctionType):
                    yield name, value

    @classmethod
    @functools.lru_cache
    def get_parent_state(cls) -> type[BaseState] | None:
        """Get the parent state.

        Returns:
            The parent state.

        Raises:
            ValueError: If more than one parent state is found.
        """
        parent_states = [
            base
            for base in cls.__bases__
            if issubclass(base, BaseState) and base is not BaseState and not base._mixin
        ]
        if len(parent_states) >= 2:
            msg = f"Only one parent state of is allowed. Found {parent_states} parents of {cls}."
            raise ValueError(msg)
        # The first non-mixin state in the mro is our parent.
        for base in cls.mro()[1:]:
            if not issubclass(base, BaseState) or base._mixin:
                continue
            if base is BaseState:
                break
            return base
        return None  # No known parent

    @classmethod
    @functools.lru_cache
    def get_root_state(cls) -> type[BaseState]:
        """Get the root state.

        Returns:
            The root state.
        """
        parent_state = cls.get_parent_state()
        return cls if parent_state is None else parent_state.get_root_state()

    @classmethod
    def get_substates(cls) -> set[type[BaseState]]:
        """Get the substates of the state.

        Returns:
            The substates of the state.
        """
        return RegistrationContext.get().get_substates(cls)

    @classmethod
    @functools.lru_cache
    def get_name(cls) -> str:
        """Get the name of the state.

        Returns:
            The name of the state.
        """
        module = cls.__module__.replace(".", "___")
        return format.to_snake_case(f"{module}___{cls.__name__}")

    @classmethod
    @functools.lru_cache
    def get_full_name(cls) -> str:
        """Get the full name of the state.

        Returns:
            The full name of the state.
        """
        name = cls.get_name()
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            name = parent_state.get_full_name() + "." + name
        return name

    @classmethod
    @functools.lru_cache
    def get_class_substate(cls, path: Sequence[str] | str) -> type[BaseState]:
        """Get the class substate.

        Args:
            path: The path to the substate.

        Returns:
            The class substate.

        Raises:
            ValueError: If the substate is not found.
        """
        if isinstance(path, str):
            path = tuple(path.split("."))

        if len(path) == 0:
            return cls
        if path[0] == cls.get_name():
            if len(path) == 1:
                return cls
            path = path[1:]
        for substate in cls.get_substates():
            if path[0] == substate.get_name():
                return substate.get_class_substate(path[1:])
        msg = f"Invalid path: {path}"
        raise ValueError(msg)

    @classmethod
    def get_class_var(cls, path: Sequence[str]) -> Any:
        """Get the class var.

        Args:
            path: The path to the var.

        Returns:
            The class var.

        Raises:
            ValueError: If the path is invalid.
        """
        path, name = path[:-1], path[-1]
        substate = cls.get_class_substate(tuple(path))
        if not hasattr(substate, name):
            msg = f"Invalid path: {path}"
            raise ValueError(msg)
        return getattr(substate, name)

    @classmethod
    def is_user_defined(cls) -> bool:
        """Check if the state is user-defined.

        Returns:
            True if the state is user-defined, False otherwise.
        """
        return (
            not cls.__module__.startswith("reflex.")
            or cls.__module__ == "reflex.istate.dynamic"
        )

    @classmethod
    def _init_var(cls, name: str, prop: Var):
        """Initialize a variable.

        Args:
            name: The name of the variable
            prop: The variable to initialize

        Raises:
            VarTypeError: if the variable has an incorrect type
        """
        from reflex_base.config import get_state_auto_setters
        from reflex_base.utils.exceptions import VarTypeError

        if not types.is_valid_var_type(prop._var_type):
            msg = (
                "State vars must be of a serializable type. "
                "Valid types include strings, numbers, booleans, lists, "
                "dictionaries, dataclasses, datetime objects, and pydantic models. "
                f'Found var "{prop._js_expr}" with type {prop._var_type}.'
            )
            raise VarTypeError(msg)
        cls.__fields__[name]._var = prop
        if cls.is_user_defined() and get_state_auto_setters() is True:
            cls._create_setter(name, prop)
        cls._set_default_value(name, prop)

    @classmethod
    def add_field(cls, name: str, var: Var, default_value: Any):
        """Validate a dynamically added field before updating the field map.

        Args:
            name: The name of the field to add.
            var: The variable to add a field for.
            default_value: The default value of the field.
        """
        _validate_state_name(cls._reflex_state_root, name)
        super().add_field(name, var, default_value)

    @classmethod
    def add_var(cls, name: str, type_: Any, default_value: Any = None):
        """Add dynamically a variable to the State.

        The variable added this way can be used in the same way as a variable
        defined statically in the model.

        Args:
            name: The name of the variable
            type_: The type of the variable
            default_value: The default value of the variable

        Raises:
            NameError: if a variable of this name already exists
        """
        if name in cls.__fields__:
            msg = f"The variable '{name}' already exist. Use a different name"
            raise NameError(msg)

        # create the variable based on name and type
        var = Var(
            _js_expr=format.format_state_name(cls.get_full_name())
            + "."
            + name
            + FIELD_MARKER,
            _var_type=type_,
            _var_data=VarData.from_state(cls, name),
        ).guess_type()

        # add the field dynamically (must be done before _init_var)
        cls.add_field(name, var, default_value)

        cls._init_var(name, var)

        cls.base_vars[name] = var
        cls.vars[name] = var
        cls._update_substate_vars({name: var})

    @classmethod
    def _create_event_handler(
        cls, fn: Any, event_handler_cls: type[EventHandler] = EventHandler
    ):
        """Create an event handler for the given function.

        Args:
            fn: The function to create an event handler for.
            event_handler_cls: The event handler class to use.

        Returns:
            The event handler.
        """
        # Check if function has stored event_actions from decorator
        event_actions = getattr(fn, EVENT_ACTIONS_MARKER, {})

        handler = event_handler_cls(fn=fn, state=cls, event_actions=event_actions)
        if cls.get_full_name() in all_base_state_classes:
            # Register handlers created after the class was registered.
            reg_ctx = RegistrationContext.get()
            reg_ctx.register_event_handler(handler, states=(cls,))
        return handler

    @classmethod
    def _create_setvar(cls):
        """Create the setvar method for the state."""
        cls.setvar = cls.event_handlers["setvar"] = EventHandlerSetVar(state_cls=cls)

    @classmethod
    def _create_setter(cls, name: str, prop: Var):
        """Create a setter for the var.

        Args:
            name: The name of the var.
            prop: The var to create a setter for.
        """
        create_event_handler_kwargs = {}

        setter_name = Var._get_setter_name_for_name(name)
        if setter_name not in cls.__dict__:
            event_handler = cls._create_event_handler(
                prop._get_setter(name), **create_event_handler_kwargs
            )
            cls.event_handlers[setter_name] = event_handler
            setattr(cls, setter_name, event_handler)

    @classmethod
    def _set_default_value(cls, name: str, prop: Var):
        """Set the default value for the var.

        Args:
            name: The name of the var.
            prop: The var to set the default value for.
        """
        # Get the field for the var.
        field = cls.get_fields()[name]

        if field.default is None and not types.is_optional(prop._var_type):
            # Ensure frontend uses null coalescing when accessing.
            object.__setattr__(prop, "_var_type", prop._var_type | None)

    @classmethod
    def _update_substate_vars(cls, vars_to_add: builtins.dict[str, Var]):
        """Update the inherited vars of substates recursively when new vars are added.

        Also updates the var dependency tracking dicts after adding vars.

        Args:
            vars_to_add: names to Var instances to add to substates
        """
        for substate_class in cls.get_substates():
            for name, var in vars_to_add.items():
                substate_class.vars.setdefault(name, var)
            substate_class._update_substate_vars(vars_to_add)
        # Reinitialize dependency tracking dicts.
        cls._init_var_dependency_dicts()

    @classmethod
    def _dynamic_route_arg_types(cls) -> builtins.dict[str, str]:
        """Map installed dynamic route argument names to their route arg type.

        Returns:
            A mapping of dynamic route argument name to ``RouteArgType`` value.
        """
        return {
            name: (
                constants.RouteArgType.LIST
                if computed_var._var_type == list[str]
                else constants.RouteArgType.SINGLE
            )
            for name, computed_var in cls.computed_vars.items()
            if isinstance(computed_var, DynamicRouteVar)
        }

    @classmethod
    def setup_dynamic_args(cls, args: builtins.dict[str, str]):
        """Set up args for easy access in renderer.

        Args:
            args: a dict of args

        Raises:
            DynamicRouteArgShadowsStateVarError: If an arg would replace a var of the state.
        """
        # Skip dynamic args that have already been registered by a previous route.
        installed = cls._dynamic_route_arg_types()
        args = {k: v for k, v in args.items() if k not in installed}
        if not args:
            return

        for name in args:
            _validate_state_name(cls._reflex_state_root, name)
            if name in cls.vars or name in cls.get_fields():
                msg = f"Dynamic route arg '{name}' is shadowing an existing var in {cls.__module__}.{cls.__name__}"
                raise DynamicRouteArgShadowsStateVarError(msg)

        def argsingle_factory(param: str):
            def inner_func(self: BaseState) -> str:
                return self.rx_router_page.params.get(param, "")

            inner_func.__name__ = param

            return inner_func

        def arglist_factory(param: str):
            def inner_func(self: BaseState) -> list[str]:
                return self.rx_router_page.params.get(param, [])

            inner_func.__name__ = param

            return inner_func

        dynamic_vars = {}
        for param, value in args.items():
            if value == constants.RouteArgType.SINGLE:
                func = argsingle_factory(param)
            elif value == constants.RouteArgType.LIST:
                func = arglist_factory(param)
            else:
                continue
            dynamic_vars[param] = DynamicRouteVar(
                fget=func,
                auto_deps=False,
                deps=[constants.ROUTER_PAGE],
                _var_data=VarData.from_state(cls, param),
            )
            _bind_attr(cls, param, dynamic_vars[param])

        # Update tracking dicts.
        cls.computed_vars.update(dynamic_vars)
        cls.vars.update(dynamic_vars)
        cls._update_substate_vars(dynamic_vars)

    if TYPE_CHECKING or environment.REFLEX_ENV_MODE.get() != constants.Env.PROD:

        def __setattr__(self, name: str, value: Any):
            """Set an attribute, rejecting names the state does not declare.

            Only defined outside prod mode, to catch typos early; in prod an
            undeclared name is set as a plain attribute.

            Args:
                name: The name of the attribute.
                value: The value of the attribute.

            Raises:
                SetUndefinedStateVarError: If the state declares nothing to assign.
            """
            cls = type(self)
            if name not in (settable := _SETTABLE_NAMES.setdefault(cls, set())):
                if not (
                    # Dunder names, like computed var caches, and mangled private names.
                    name.startswith((
                        "__",
                        f"_{getattr(cls, '__original_name__', cls.__name__)}__",
                    ))
                    # A field, a property, or a bookkeeping slot handles the assignment.
                    or _has_data_descriptor(cls, name)
                ):
                    msg = (
                        f"The state variable '{name}' has not been defined in '{cls.__name__}'. "
                        f"All state variables must be declared before they can be set."
                    )
                    raise SetUndefinedStateVarError(msg)
                settable.add(name)
            object.__setattr__(self, name, value)

    def reset(self):
        """Reset the fields of this state and its substates to their default values."""
        # The class of the state, also when `self` is a StateProxy.
        cls = self.__class__
        for name, f in cls.__fields__.items():
            # Never reset the router data; inherited fields reset with their state.
            if f._owner is cls and name not in _ROUTER_FIELD_NAMES:
                setattr(self, name, f.default_value())

        # Recursively reset the substates.
        for substate in self.substates.values():
            substate.reset()

    def _update_router_vars(
        self,
        router_data: builtins.dict[str, Any],
        previous_router_data: builtins.dict[str, Any],
    ) -> builtins.dict[str, Any]:
        """Update the per-field router vars from a new router_data dict.

        Each var is rebuilt only when the router_data keys it derives from
        changed, so connection-scoped data (session, headers) is not recomputed
        on every navigation, and is then assigned only when the rebuilt value
        actually differs -- different keys can still yield an equal value (an
        absent key and an empty one both produce the default), and assigning
        regardless would dirty the var, mark the state touched, and persist it.

        A key missing from ``router_data`` carries no information about the
        value it feeds, so the previous one is carried forward rather than
        letting the constructors default it away: a payload holding only the
        navigation keys must not empty the connection-scoped vars, nor rebuild
        the page and URL without the origin header that gives them their host.

        Args:
            router_data: The new router_data dict.
            previous_router_data: The router_data dict this state last saw.

        Returns:
            The router_data to store on the state: the new values over the
            previous ones, so a partial payload does not drop keys for the
            next comparison either.
        """
        # Merging also makes an absent key compare equal to what it replaced,
        # so it is not read as a change without a special case for it.
        merged = (
            {**previous_router_data, **router_data}
            if previous_router_data
            else router_data
        )
        get = merged.get
        prev_get = previous_router_data.get

        headers_changed = prev_get(constants.RouteVar.HEADERS) != get(
            constants.RouteVar.HEADERS
        )
        # Only the origin header feeds the URL/page host, so the navigation
        # vars must not be rebuilt for a change to any other header.
        origin_changed = headers_changed and (
            prev_get(constants.RouteVar.HEADERS, {}).get("origin", "")
            != get(constants.RouteVar.HEADERS, {}).get("origin", "")
        )

        if (
            any(
                prev_get(key) != get(key)
                for key in (
                    constants.RouteVar.CLIENT_TOKEN,
                    constants.RouteVar.SESSION_ID,
                    constants.RouteVar.CLIENT_IP,
                )
            )
            and (session := SessionData.from_router_data(merged))
            != self.rx_router_session
        ):
            self.rx_router_session = session
        if (
            headers_changed
            and (headers := HeaderData.from_router_data(merged))
            != self.rx_router_headers
        ):
            self.rx_router_headers = headers
        if (
            origin_changed
            or prev_get(constants.RouteVar.PATH) != get(constants.RouteVar.PATH)
            or prev_get(constants.RouteVar.ORIGIN) != get(constants.RouteVar.ORIGIN)
            or prev_get(constants.RouteVar.QUERY) != get(constants.RouteVar.QUERY)
        ):
            if (page := PageData.from_router_data(merged)) != self.rx_router_page:
                self.rx_router_page = page
            if (url := URLData.from_router_data(merged)) != self.rx_router_url:
                self.rx_router_url = url
            if (
                route_id := get(constants.RouteVar.PATH, "")
            ) != self.rx_router_route_id:
                self.rx_router_route_id = route_id
        return merged

    @classmethod
    @functools.lru_cache
    def _is_client_storage(cls, prop_name_or_field: str | Field) -> bool:
        """Check if the var is a client storage var.

        Args:
            prop_name_or_field: The name of the var or the field itself.

        Returns:
            Whether the var is a client storage var.
        """
        if isinstance(prop_name_or_field, str):
            field = cls.get_fields().get(prop_name_or_field)
        else:
            field = prop_name_or_field
        return field is not None and (
            isinstance(field.default, ClientStorageBase)
            or (
                isinstance(field.type_, type)
                and issubclass(field.type_, ClientStorageBase)
            )
        )

    def _reset_client_storage(self):
        """Reset client storage base vars to their default values."""
        # Client-side storage is reset during hydrate so that clearing cookies
        # on the browser also resets the values on the backend.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            field = fields[prop_name]
            if self._is_client_storage(field):
                setattr(self, prop_name, copy.deepcopy(field.default))

        # Recursively reset the substate client storage.
        for substate in self.substates.values():
            substate._reset_client_storage()

    def get_substate(self, path: Sequence[str]) -> BaseState:
        """Get the substate.

        Args:
            path: The path to the substate.

        Returns:
            The substate.

        Raises:
            ValueError: If the substate is not found.
        """
        if len(path) == 0:
            return self
        if path[0] == self.get_name():
            if len(path) == 1:
                return self
            path = path[1:]
        if path[0] not in self.substates:
            msg = f"Invalid path: {path}"
            raise ValueError(msg)
        return self.substates[path[0]].get_substate(path[1:])

    @classmethod
    def _get_potentially_dirty_states(cls) -> set[type[BaseState]]:
        """Get substates which may have dirty vars due to dependencies.

        Returns:
            The set of potentially dirty substate classes.
        """
        return {
            cls.get_class_substate(substate_name)
            for substate_name in cls._always_dirty_substates
        }.union({
            cls.get_root_state().get_class_substate(substate_name)
            for substate_name in cls._potentially_dirty_states
        })

    def _get_root_state(self) -> BaseState:
        """Get the root state of the state tree.

        Returns:
            The root state of the state tree.
        """
        parent_state = self
        while parent_state.parent_state is not None:
            parent_state = parent_state.parent_state
        return parent_state

    async def _get_state_from_redis(self, state_cls: type[T_STATE]) -> T_STATE:
        """Get a state instance from redis.

        Args:
            state_cls: The class of the state.

        Returns:
            The instance of state_cls associated with this state's client_token.

        Raises:
            RuntimeError: If redis is not used in this backend process.
            StateMismatchError: If the state instance is not of the expected type.
        """
        from reflex.istate.manager import get_state_manager
        from reflex.istate.manager.redis import StateManagerRedis
        from reflex.istate.manager.token import BaseStateToken

        # Then get the target state and all its substates.
        state_manager = get_state_manager()
        if not isinstance(state_manager, StateManagerRedis):
            msg = (
                f"Requested state {state_cls.get_full_name()} is not cached and cannot be accessed without redis. "
                "(All states should already be available -- this is likely a bug)."
            )
            raise RuntimeError(msg)
        state_in_redis = await state_manager.get_state(
            token=BaseStateToken(
                ident=self.rx_router_session.client_token, cls=state_cls
            ),
            top_level=False,
            for_state_instance=self,
        )

        if not isinstance(state_in_redis, state_cls):
            msg = f"Searched for state {state_cls.get_full_name()} but found {state_in_redis}."
            raise StateMismatchError(msg)

        return state_in_redis

    def _get_state_from_cache(self, state_cls: type[T_STATE]) -> T_STATE:
        """Get a state instance from the cache.

        Args:
            state_cls: The class of the state.

        Returns:
            The instance of state_cls associated with this state's client_token.

        Raises:
            StateMismatchError: If the state instance is not of the expected type.
        """
        root_state = self._get_root_state()
        substate = root_state.get_substate(state_cls.get_full_name().split("."))
        if not isinstance(substate, state_cls):
            msg = (
                f"Searched for state {state_cls.get_full_name()} but found {substate}."
            )
            raise StateMismatchError(msg)
        return substate

    async def get_state(self, state_cls: type[T_STATE]) -> T_STATE:
        """Get an instance of the state associated with this token.

        Allows for arbitrary access to sibling states from within an event handler.

        Args:
            state_cls: The class of the state.

        Returns:
            The instance of state_cls associated with this state's client_token.
        """
        # Fast case - if this state instance is already cached, get_substate from root state.
        try:
            return self._get_state_from_cache(state_cls)
        except ValueError:
            pass

        # Slow case - fetch missing parent states from redis.
        return await self._get_state_from_redis(state_cls)

    async def get_var_value(self, var: Var[VAR_TYPE]) -> VAR_TYPE:
        """Get the value of an rx.Var from another state.

        Args:
            var: The var to get the value for.

        Returns:
            The value of the var.

        Raises:
            UnretrievableVarValueError: If the var does not have a literal value
                or associated state.
        """
        # Oopsie case: you didn't give me a Var... so get what you give.
        if not isinstance(var, Var):
            return var

        unset = object()

        # Fast case: this is a literal var and the value is known.
        if (
            var_value := getattr(var, "_var_value", unset)
        ) is not unset and not isinstance(var_value, Var):
            return var_value  # pyright: ignore [reportReturnType]

        # Unwrap any cast wrappers and resolve via the underlying var's *own*
        # var data, not the recursive _get_all_var_data(). For an operation or
        # derived var (e.g. State.a + State.b or State.items[0]), the recursive
        # merge back-fills state/field_name from the first operand, which would
        # make us silently return that operand's value instead of the operation's
        # result. Only a plain field or computed var reference carries
        # state + field_name on its own var data.
        inner_var = var
        while isinstance(inner_var, ToOperation):
            inner_var = inner_var._original
        var_data = inner_var._var_data
        if var_data is None or not var_data.state or not var_data.field_name:
            msg = f"Unable to retrieve value for {var._js_expr}: not associated with any state."
            raise UnretrievableVarValueError(msg)
        # Fastish case: this var belongs to this state
        if var_data.state == self.get_full_name():
            value = getattr(self, var_data.field_name)
            if inspect.isawaitable(value):
                return await value
            return value

        # Slow case: this var belongs to another state
        other_state = await self.get_state(
            self._get_root_state().get_class_substate(var_data.state)
        )
        value = getattr(other_state, var_data.field_name)
        if inspect.isawaitable(value):
            return await value
        return value

    def _mark_dirty_computed_vars(self, var_names: Iterable[str] | None = None) -> None:
        """Invalidate the computed vars depending on changed vars of this state, transitively.

        Uncached and expired computed vars recompute on access, so they count as
        changed along with any var.

        Args:
            var_names: The changed vars of this state; all its dirty vars if omitted.
        """
        if self._always_dirty_computed_vars or self._interval_computed_var_names:
            recomputed = (
                self._always_dirty_computed_vars | self._expired_computed_vars()
            )
            self.dirty_vars.update(recomputed)
            if var_names is not None:
                var_names = (*var_names, *recomputed)
        pending: list[tuple[BaseState, str]] = [
            (self, name)
            for name in (self.dirty_vars if var_names is None else var_names)
        ]
        while pending:
            state, name = pending.pop()
            for state_name, cvar_name in state._var_dependencies.get(name, ()):
                if state_name == state.get_full_name():
                    target = state
                else:
                    target = state._get_root_state().get_substate(state_name.split("."))
                    target._mark_ancestors_dirty()
                target.computed_vars[cvar_name].mark_dirty(instance=target)
                target.dirty_vars.add(cvar_name)
                pending.append((target, cvar_name))

    def _expired_computed_vars(self) -> set[str]:
        """Determine ComputedVars that need to be recalculated based on the expiration time.

        Returns:
            Set of computed vars to include in the delta.
        """
        # Only computed vars declared with an interval can expire; the class
        # keeps that subset so this stays O(interval vars), not O(all vars).
        computed_vars = self.computed_vars
        # __class__, not type(): a StateProxy reports the wrapped state's class.
        return {
            cvar
            for cvar in self.__class__._interval_computed_var_names
            if computed_vars[cvar].needs_update(instance=self)
        }

    def get_delta(self) -> Delta:
        """Get the delta for this state and its dirty substates.

        Delta building calls this on each state, so an override applies to it.

        Returns:
            The delta.
        """
        return build_delta(self)

    async def _get_resolved_delta(self) -> Delta:
        """Get the delta to deliver to the client, with all coroutines resolved.

        Returns:
            The resolved delta.
        """
        return await resolve_delta(self)

    def _mark_dirty(self, var_names: Iterable[str] | None = None) -> None:
        """Mark this state and its ancestors dirty, invalidating dependent computed vars.

        Computed vars are invalidated right away, so that one read later in the
        same event handler is recomputed.

        Args:
            var_names: The vars of this state that changed; all its dirty vars if omitted.
        """
        self._mark_ancestors_dirty()
        self._mark_dirty_computed_vars(var_names)

    def _mark_ancestors_dirty(self) -> None:
        """Record this state as a dirty substate of each of its ancestors."""
        state = self
        while (parent := state.parent_state) is not None:
            name = state.get_name()
            if name in parent.dirty_substates:
                return
            parent.dirty_substates.add(name)
            state = parent

    def _clean(self):
        """Reset the dirty vars of this state and its dirty substates."""
        clean_state(self)

    def get_value(self, key: str) -> Any:
        """Get the value of a field (without proxying).

        The returned value will NOT track dirty state updates.

        Args:
            key: The key of the field.

        Returns:
            The value of the field.

        Raises:
            TypeError: If the key is not a string or MutableProxy.
        """
        if isinstance(key, str):
            if isinstance(val := getattr(self, key), MutableProxy):
                return val.__wrapped__
            return val

        msg = f"Invalid key type: {type(key)}. Expected str."
        raise TypeError(msg)

    def dict(
        self, include_computed: bool = True, initial: bool = False, **kwargs
    ) -> builtins.dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            include_computed: Whether to include computed vars.
            initial: Whether to get the initial value of computed vars.
            **kwargs: Kwargs to pass to the dict method.

        Returns:
            The object as a dictionary.
        """
        if include_computed:
            self._mark_dirty_computed_vars()
        base_vars = {
            prop_name: self.get_value(prop_name) for prop_name in self.base_vars
        }
        if initial and include_computed:
            computed_vars = {
                # Include initial computed vars.
                prop_name: (
                    cv._initial_value
                    if is_computed_var(cv)
                    and not isinstance(cv._initial_value, types.Unset)
                    else self.get_value(prop_name)
                )
                for prop_name, cv in self.computed_vars.items()
                if not cv._backend
            }
        elif include_computed:
            computed_vars = {
                # Include the computed vars.
                prop_name: self.get_value(prop_name)
                for prop_name, cv in self.computed_vars.items()
                if not cv._backend
            }
        else:
            computed_vars = {}
        variables = {**base_vars, **computed_vars}
        d = {
            self.get_full_name(): {
                k + FIELD_MARKER: variables[k] for k in sorted(variables)
            },
        }
        for substate_d in [
            v.dict(include_computed=include_computed, initial=initial, **kwargs)
            for v in self.substates.values()
        ]:
            d.update(substate_d)

        return d

    async def __aenter__(self) -> Self:
        """Enter the async context manager protocol.

        This is a no-op for the State class and mainly used in background-tasks/StateProxy.

        Returns:
            The unmodified state (self)
        """
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Exit the async context manager protocol.

        This should not be used for the State class, but exists for
        type-compatibility with StateProxy.

        Args:
            exc_info: The exception info tuple.
        """

    def __getstate__(self):
        """Get the state for redis serialization.

        This method is called by pickle to serialize the object.

        The parent state and substates are not part of it: they are serialized
        separately by the StateManagerRedis to allow for better horizontal
        scaling as state size increases. Only fields bound to this state's class
        are stored on it, so inherited ones are not included either.

        Returns:
            The state dict for serialization.
        """
        return self.__dict__.copy()

    def __setstate__(self, state: builtins.dict[str, Any]):
        """Set the state from redis deserialization.

        This method is called by pickle to deserialize the object.

        Args:
            state: The state dict for deserialization.
        """
        self._init_bookkeeping()
        for key in _LEGACY_PICKLE_KEYS:
            state.pop(key, None)
        # Older pickles kept the backend vars in a dict of their own.
        state.update(state.pop("_backend_vars", {}))
        vars(self).update(state)

    def _check_state_size(
        self,
        pickle_state_size: int,
    ):
        """Print a warning when the state is too large.

        Args:
            pickle_state_size: The size of the pickled state.

        Raises:
            StateTooLargeError: If the state is too large.
        """
        state_full_name = self.get_full_name()
        if (
            state_full_name not in _WARNED_ABOUT_STATE_SIZE
            and pickle_state_size > TOO_LARGE_SERIALIZED_STATE
            and self.substates
        ):
            msg = (
                f"State {state_full_name} serializes to {pickle_state_size} bytes "
                + "which may present performance issues. Consider reducing the size of this state."
            )
            if environment.REFLEX_PERF_MODE.get() == PerformanceMode.WARN:
                logger.warning(msg)
            elif environment.REFLEX_PERF_MODE.get() == PerformanceMode.RAISE:
                raise StateTooLargeError(msg)
            _WARNED_ABOUT_STATE_SIZE.add(state_full_name)

    @classmethod
    @functools.lru_cache
    def _to_schema(cls) -> str:
        """Convert a state to a schema.

        Returns:
            The hash of the schema.
        """

        def _field_tuple(
            field_name: str,
        ) -> tuple[str, Any, Any]:
            model_field = cls.__fields__[field_name]
            return (
                field_name,
                _serialize_type(model_field.type_),
                (model_field.default if is_serializable(model_field.default) else None),
            )

        return md5(
            pickle.dumps(
                sorted(_field_tuple(field_name) for field_name in cls.base_vars)
            )
        ).hexdigest()

    def _serialize(self) -> bytes:
        """Serialize the state for redis.

        Returns:
            The serialized state.

        Raises:
            StateSerializationError: If the state cannot be serialized.

        # noqa: DAR401: e
        # noqa: DAR402: StateSerializationError
        """
        payload = b""
        error = ""
        self_schema = self._to_schema()
        pickle_function = pickle.dumps
        try:
            payload = pickle.dumps((self_schema, self))
        except HANDLED_PICKLE_ERRORS as og_pickle_error:
            error = (
                f"Failed to serialize state {self.get_full_name()} due to unpicklable object. "
                "This state will not be persisted. "
            )
            try:
                import dill

                pickle_function = dill.dumps
                payload = dill.dumps((self_schema, self))
            except ImportError:
                error += (
                    f"Pickle error: {og_pickle_error}. "
                    "Consider `pip install 'dill>=0.3.8'` for more exotic serialization support."
                )
            except HANDLED_PICKLE_ERRORS as ex:
                error += f"Dill was also unable to pickle the state: {ex}"

        if environment.REFLEX_PERF_MODE.get() != PerformanceMode.OFF:
            self._check_state_size(len(payload))

        if not payload:
            e = StateSerializationError(error)
            if sys.version_info >= (3, 11):
                try:
                    debug_failed_pickles(self, pickle_function)
                except HANDLED_PICKLE_ERRORS as ex:
                    for note in ex.__notes__:
                        e.add_note(note)
            raise e

        return payload

    @classmethod
    def _deserialize(
        cls, data: bytes | None = None, fp: BinaryIO | None = None
    ) -> BaseState:
        """Deserialize the state from redis/disk.

        data and fp are mutually exclusive, but one must be provided.

        Args:
            data: The serialized state data.
            fp: The file pointer to the serialized state data.

        Returns:
            The deserialized state.

        Raises:
            ValueError: If both data and fp are provided, or neither are provided.
            StateSchemaMismatchError: If the state schema does not match the expected schema.
        """
        if data is not None and fp is None:
            (substate_schema, state) = pickle.loads(data)
        elif fp is not None and data is None:
            (substate_schema, state) = pickle.load(fp)
        else:
            msg = "Only one of `data` or `fp` must be provided"
            raise ValueError(msg)
        if substate_schema != state._to_schema():
            raise StateSchemaMismatchError
        return state


def _serialize_type(type_: Any) -> str:
    """Serialize a type.

    Args:
        type_: The type to serialize.

    Returns:
        The serialized type.
    """
    if not isinstance(type_, type):
        return f"{type_}"
    return f"{type_.__module__}.{type_.__qualname__}"


def is_serializable(value: Any) -> bool:
    """Check if a value is serializable.

    Args:
        value: The value to check.

    Returns:
        Whether the value is serializable.
    """
    try:
        return bool(pickle.dumps(value))
    except Exception:
        return False


T_STATE = TypeVar("T_STATE", bound=BaseState)


class State(BaseState):
    """The app Base State."""

    # The hydrated bool.
    is_hydrated: bool = False
    # Maps the state full_name to an arbitrary token it is linked to for shared state.
    _reflex_internal_links: dict[str, str] | None = None

    @_override_base_method
    async def _get_state_from_redis(self, state_cls: type[T_STATE]) -> T_STATE:
        """Get a state instance from redis with linking support.

        Args:
            state_cls: The class of the state.

        Returns:
            The instance of state_cls associated with this state's client_token.
        """
        if (
            self._reflex_internal_links
            and (
                linked_token := self._reflex_internal_links.get(
                    state_cls.get_full_name()
                )
            )
            is not None
        ):
            from reflex.istate.shared import SharedStateBaseInternal

            shared_base = await self.get_state(SharedStateBaseInternal)
            return await shared_base._resolve_linked_state(state_cls, linked_token)  # type: ignore[return-value]
        return await super()._get_state_from_redis(state_cls)

    @event
    async def hydrate(self) -> None:
        """Send the full state to the frontend to synchronize it with the backend."""
        from reflex_base.event.context import EventContext

        # Clear client storage, to respect clearing cookies
        self._reset_client_storage()

        # Mark state as not hydrated (until on_loads are complete)
        self.is_hydrated = False

        # Get the initial state if needed.
        ctx = EventContext.get()
        if ctx.emit_delta_impl is not None:
            await ctx.emit_delta(delta=await _resolve_delta(self.dict()))

        # since a full dict was captured, clean any dirtiness
        self._clean()

    @event
    def set_is_hydrated(self, value: bool) -> None:
        """Set the hydrated state.

        Args:
            value: The hydrated state.
        """
        self.is_hydrated = value


T = TypeVar("T", bound=BaseState)


def dynamic(func: Callable[[T], Component]):
    """Create a dynamically generated components from a state class.

    Args:
        func: The function to generate the component.

    Returns:
        The dynamically generated component.

    Raises:
        DynamicComponentInvalidSignatureError: If the function does not have exactly one parameter or a type hint for the state class.
    """
    number_of_parameters = len(inspect.signature(func).parameters)

    func_signature = get_type_hints(func)

    if "return" in func_signature:
        func_signature.pop("return")

    values = list(func_signature.values())

    if number_of_parameters != 1:
        msg = "The function must have exactly one parameter, which is the state class."
        raise DynamicComponentInvalidSignatureError(msg)

    if len(values) != 1:
        msg = "You must provide a type hint for the state class in the function."
        raise DynamicComponentInvalidSignatureError(msg)

    state_class: type[T] = values[0]

    def wrapper() -> Component:
        from reflex_components_core.base.fragment import fragment

        return fragment(state_class._evaluate(lambda state: func(state)))

    return wrapper


# sessionStorage key holding the ms timestamp of the last reload on error
LAST_RELOADED_KEY = "reflex_last_reloaded_on_error"


class FrontendEventExceptionState(State):
    """Substate for handling frontend exceptions."""

    # If the frontend error message contains any of these strings, automatically reload the page.
    auto_reload_on_errors: ClassVar[list[re.Pattern]] = [
        re.compile(  # Chrome/Edge
            re.escape("TypeError: Cannot read properties of null")
        ),
        re.compile(re.escape("TypeError: null is not an object")),  # Safari
        re.compile(r"TypeError: can't access property \".*\" of null"),  # Firefox
        # Firefox: property access is on a function that returns null.
        re.compile(
            re.escape("TypeError: can't access property \"")
            + r".*"
            + re.escape('", ')
            + r".*"
            + re.escape(" is null")
        ),
    ]

    @event
    def handle_frontend_exception(
        self, info: str, component_stack: str
    ) -> Iterator[EventSpec]:
        """Handle frontend exceptions.

        If a frontend exception handler is provided, it will be called.
        Otherwise, the default frontend exception handler will be called.

        Args:
            info: The exception information.
            component_stack: The stack trace of the component where the exception occurred.

        Yields:
            Optional auto-reload event for certain errors outside cooldown period.
        """
        # Handle automatic reload for certain errors.
        if type(self).auto_reload_on_errors and any(
            error.search(info) for error in type(self).auto_reload_on_errors
        ):
            yield call_script(
                f"const last_reload = parseInt(window.sessionStorage.getItem('{LAST_RELOADED_KEY}')) || 0;"
                f"if (Date.now() - last_reload > {auto_reload_cooldown() // timedelta(milliseconds=1)})"
                "{"
                f"window.sessionStorage.setItem('{LAST_RELOADED_KEY}', Date.now().toString());"
                "window.location.reload();"
                "}"
            )
        # Escape rich markup so a JS error message containing square brackets
        # (e.g. "x[/bold]y is not a function") cannot style backend logs or
        # raise MarkupError when printed through the console helpers. The text
        # is not otherwise sanitized: stack traces are multi-line by nature and
        # truncating them would lose the information this handler exists for.
        RegistrationContext.get().app.frontend_exception_handler(
            Exception(escape(info))
        )


class UpdateVarsInternalState(State):
    """Substate for handling internal state var updates."""

    async def update_vars_internal(self, vars: dict[str, Any]) -> None:
        """Apply updates to fully qualified state vars.

        The keys in `vars` should be in the form of `{state.get_full_name()}.{var_name}`,
        and each value will be set on the appropriate substate instance.

        This function is primarily used to apply cookie and local storage
        updates from the frontend to the appropriate substate.

        Args:
            vars: The fully qualified vars and values to update.
        """
        for var, value in vars.items():
            state_name, _, var_name = var.rpartition(".")
            var_name = var_name.removesuffix(FIELD_MARKER)
            var_state_cls = State.get_class_substate(state_name)
            if var_state_cls._is_client_storage(var_name):
                var_state = await self.get_state(var_state_cls)
                setattr(var_state, var_name, value)


class OnLoadInternalState(State):
    """Substate for handling on_load event enumeration.

    This is a separate substate to avoid deserializing the entire state tree for every page navigation.
    """

    # A newer navigation supersedes the previous unfinished on_load chain for
    # the same client token, cancelling its stale work (#6593).
    @event(supersedes=True)
    def on_load_internal(self) -> list[Event | EventSpec | event.EventCallback] | None:
        """Queue on_load handlers for the current page.

        Returns:
            The list of events to queue for on load handling.
        """
        load_events = RegistrationContext.get().app.get_load_events(
            self.rx_router_url.path
        )
        if not load_events:
            self.is_hydrated = True
            return None  # Fast path for navigation with no on_load events defined.
        self.is_hydrated = False
        return [
            *Event.from_event_type(
                load_events,
                router_data=self.router_data,
            ),
            State.set_is_hydrated(True),
        ]


class ComponentState(State, mixin=True):
    """Base class to allow for the creation of a state instance per component.

    This allows for the bundling of UI and state logic into a single class,
    where each instance has a separate instance of the state.

    Subclass this class and define vars and event handlers in the traditional way.
    Then define a `get_component` method that returns the UI for the component instance.

    See the full [docs](https://reflex.dev/docs/state-structure/component-state/) for more.

    Basic example:
    ```python
    # Subclass ComponentState and define vars and event handlers.
    class Counter(rx.ComponentState):
        # Define vars that change.
        count: int = 0

        # Define event handlers.
        def increment(self):
            self.count += 1

        def decrement(self):
            self.count -= 1

        @classmethod
        def get_component(cls, **props):
            # Access the state vars and event handlers using `cls`.
            return rx.hstack(
                rx.button("Decrement", on_click=cls.decrement),
                rx.text(cls.count),
                rx.button("Increment", on_click=cls.increment),
                **props,
            )

    counter = Counter.create()
    ```
    """

    # The number of components created from this class.
    _per_component_state_instance_count: ClassVar[int] = 0

    def __init__(self, *args, **kwargs):
        """Do not allow direct initialization of the ComponentState.

        Args:
            *args: The args to pass to the State init method.
            **kwargs: The kwargs to pass to the State init method.

        Raises:
            ReflexRuntimeError: If the ComponentState is initialized directly.
        """
        if self._mixin:
            raise ReflexRuntimeError(
                f"{ComponentState.__name__} {type(self).__name__} is not meant to be initialized directly. "
                + "Use the `create` method to create a new instance and access the state via the `State` attribute."
            )
        super().__init__(*args, **kwargs)

    @classmethod
    def __init_subclass__(cls, mixin: bool = True, **kwargs):
        """Overwrite mixin default to True.

        Args:
            mixin: Whether the subclass is a mixin and should not be initialized.
            **kwargs: The kwargs to pass to the init_subclass method.
        """
        super().__init_subclass__(mixin=mixin, **kwargs)

    @classmethod
    def get_component(cls, *children, **props) -> Component:
        """Get the component instance.

        Args:
            children: The children of the component.
            props: The props of the component.

        Raises:
            NotImplementedError: if the subclass does not override this method.
        """
        msg = f"{cls.__name__} must implement get_component to return the component instance."
        raise NotImplementedError(msg)

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a new instance of the Component.

        Args:
            children: The children of the component.
            props: The props of the component.

        Returns:
            A new instance of the Component with an independent copy of the State.
        """
        from reflex.compiler.compiler import into_component

        cls._per_component_state_instance_count += 1
        state_cls_name = f"{cls.__name__}_n{cls._per_component_state_instance_count}"
        component_state = type(
            state_cls_name,
            (cls, State),
            {"__module__": reflex.istate.dynamic.__name__},
            mixin=False,
        )
        # Save a reference to the dynamic state for pickle/unpickle.
        setattr(reflex.istate.dynamic, state_cls_name, component_state)
        component = component_state.get_component(*children, **props)
        component = into_component(component)
        component.State = component_state
        return component


@dataclasses.dataclass(
    frozen=True,
)
class StateUpdate:
    """A state update sent to the frontend.

    Each substate key in the delta must have a dispatch function registered in
    the frontend; otherwise the frontend reports a fatal ``client_error`` back
    to the backend (see ``EventNamespace.on_client_error``), since this
    indicates mismatched frontend and backend state definitions.
    """

    # The state delta.
    delta: DeltaMapping = dataclasses.field(default_factory=dict)

    # Events to be added to the event queue.
    events: list[Event] = dataclasses.field(default_factory=list)

    # Deprecated: previously indicated whether the event processing is complete.
    final: bool | None = dataclasses.field(default=None, repr=False)

    def __post_init__(self):
        """Warn if the deprecated `final` attribute is supplied."""
        if self.final is not None:
            console.deprecate(
                feature_name="StateUpdate.final",
                reason="The final attribute is no longer used.",
                deprecation_version="0.9.0",
                removal_version="1.0",
            )


@serializer(to=dict)
def serialize_state_update(update: StateUpdate) -> dict:
    """Serialize a StateUpdate to a dictionary.

    Args:
        update: The StateUpdate to serialize.

    Returns:
        The serialized StateUpdate.
    """
    return {
        k.name: v for k in dataclasses.fields(update) if (v := getattr(update, k.name))
    }


def code_uses_state_contexts(javascript_code: str) -> bool:
    """Check if the rendered Javascript uses state contexts.

    Args:
        javascript_code: The Javascript code to check.

    Returns:
        True if the code attempts to access a member of StateContexts.
    """
    return bool("useContext(StateContexts" in javascript_code)


def reload_state_module(
    module: str,
    state: type[BaseState] = State,
) -> None:
    """Reset rx.State subclasses to avoid conflict when reloading.

    Args:
        module: The module to reload.
        state: Recursive argument for the state class to reload.

    """
    # Clean out all potentially dirty states of reloaded modules.
    for pd_state in tuple(state._potentially_dirty_states):
        with contextlib.suppress(ValueError):
            if (
                state.get_root_state().get_class_substate(pd_state).__module__ == module
                and module is not None
            ):
                state._potentially_dirty_states.remove(pd_state)
    reg_ctx = RegistrationContext.get()
    substates = reg_ctx.get_substates(state)
    for subclass in tuple(substates):
        reload_state_module(module=module, state=subclass)
        if subclass.__module__ == module and module is not None:
            all_base_state_classes.pop(subclass.get_full_name(), None)
            substates.remove(subclass)
            state._always_dirty_substates.discard(subclass.get_name())
            state._var_dependencies = {}
            state._init_var_dependency_dicts()
    state.get_class_substate.cache_clear()
