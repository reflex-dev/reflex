"""Define the reflex state specification."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import dataclasses
import functools
import inspect
import json
import pickle
import sys
import time
import typing
import uuid
import warnings
from abc import ABC, abstractmethod
from hashlib import md5
from pathlib import Path
from types import FunctionType, MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    BinaryIO,
    Callable,
    ClassVar,
    Dict,
    Optional,
    Sequence,
    Set,
    SupportsIndex,
    Tuple,
    Type,
    TypeVar,
    cast,
    get_args,
    get_type_hints,
)

import pydantic.v1 as pydantic
import wrapt
from pydantic import BaseModel as BaseModelV2
from pydantic.v1 import BaseModel as BaseModelV1
from pydantic.v1 import validator
from pydantic.v1.fields import ModelField
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ResponseError
from sqlalchemy.orm import DeclarativeBase
from typing_extensions import Self

import reflex.istate.dynamic
from reflex import constants, event
from reflex.base import Base
from reflex.config import PerformanceMode, environment, get_config
from reflex.event import (
    BACKGROUND_TASK_MARKER,
    Event,
    EventHandler,
    EventSpec,
    fix_events,
)
from reflex.istate.data import RouterData
from reflex.istate.storage import ClientStorageBase
from reflex.model import Model
from reflex.utils import console, format, path_ops, prerequisites, types
from reflex.utils.exceptions import (
    ComputedVarShadowsBaseVarsError,
    ComputedVarShadowsStateVarError,
    DynamicComponentInvalidSignatureError,
    DynamicRouteArgShadowsStateVarError,
    EventHandlerShadowsBuiltInStateMethodError,
    ImmutableStateError,
    InvalidLockWarningThresholdError,
    InvalidStateManagerModeError,
    LockExpiredError,
    ReflexRuntimeError,
    SetUndefinedStateVarError,
    StateMismatchError,
    StateSchemaMismatchError,
    StateSerializationError,
    StateTooLargeError,
    UnretrievableVarValueError,
)
from reflex.utils.exec import is_testing_env
from reflex.utils.serializers import serializer
from reflex.utils.types import (
    _isinstance,
    get_origin,
    is_union,
    override,
    true_type_for_pydantic_field,
    value_inside_optional,
)
from reflex.vars import VarData
from reflex.vars.base import (
    ComputedVar,
    DynamicRouteVar,
    Var,
    computed_var,
    dispatch,
    get_unique_variable_name,
    is_computed_var,
)

if TYPE_CHECKING:
    from reflex.components.component import Component


Delta = dict[str, Any]
var = computed_var


if environment.REFLEX_PERF_MODE.get() != PerformanceMode.OFF:
    # If the state is this large, it's considered a performance issue.
    TOO_LARGE_SERIALIZED_STATE = environment.REFLEX_STATE_SIZE_LIMIT.get() * 1024
    # Only warn about each state class size once.
    _WARNED_ABOUT_STATE_SIZE: set[str] = set()

# Errors caught during pickling of state
HANDLED_PICKLE_ERRORS = (
    pickle.PicklingError,
    AttributeError,
    IndexError,
    TypeError,
    ValueError,
)

# For BaseState.get_var_value
VAR_TYPE = TypeVar("VAR_TYPE")


def _no_chain_background_task(
    state_cls: Type["BaseState"], name: str, fn: Callable
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


def _substate_key(
    token: str,
    state_cls_or_name: BaseState | Type[BaseState] | str | Sequence[str],
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

    state_cls: Type[BaseState] = dataclasses.field(init=False)

    def __init__(self, state_cls: Type[BaseState]):
        """Initialize the EventHandlerSetVar.

        Args:
            state_cls: The state class that vars will be set on.
        """
        super().__init__(
            fn=type(self).setvar,
            state_full_name=state_cls.get_full_name(),
        )
        object.__setattr__(self, "state_cls", state_cls)

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
        from reflex.utils.exceptions import EventHandlerValueError

        if args:
            if not isinstance(args[0], str):
                raise EventHandlerValueError(
                    f"Var name must be passed as a string, got {args[0]!r}"
                )

            handler = getattr(self.state_cls, constants.SETTER_PREFIX + args[0], None)

            # Check that the requested Var setter exists on the State at compile time.
            if handler is None:
                raise AttributeError(
                    f"Variable `{args[0]}` cannot be set on `{self.state_cls.get_full_name()}`"
                )

            if asyncio.iscoroutinefunction(handler.fn):
                raise NotImplementedError(
                    f"Setter for {args[0]} is async, which is not supported."
                )

        return super().__call__(*args)


if TYPE_CHECKING:
    from pydantic.v1.fields import ModelField


def _unwrap_field_type(type_: types.GenericType) -> Type:
    """Unwrap rx.Field type annotations.

    Args:
        type_: The type to unwrap.

    Returns:
        The unwrapped type.
    """
    from reflex.vars import Field

    if get_origin(type_) is Field:
        return get_args(type_)[0]
    return type_


def get_var_for_field(cls: Type[BaseState], f: ModelField):
    """Get a Var instance for a Pydantic field.

    Args:
        cls: The state class.
        f: The Pydantic field.

    Returns:
        The Var instance.
    """
    field_name = format.format_state_name(cls.get_full_name()) + "." + f.name

    return dispatch(
        field_name=field_name,
        var_data=VarData.from_state(cls, f.name),
        result_var_type=_unwrap_field_type(true_type_for_pydantic_field(f)),
    )


async def _resolve_delta(delta: Delta) -> Delta:
    """Await all coroutines in the delta.

    Args:
        delta: The delta to process.

    Returns:
        The same delta dict with all coroutines resolved to their return value.
    """
    tasks = {}
    for state_name, state_delta in delta.items():
        for var_name, value in state_delta.items():
            if asyncio.iscoroutine(value):
                tasks[state_name, var_name] = asyncio.create_task(value)
    for (state_name, var_name), task in tasks.items():
        delta[state_name][var_name] = await task
    return delta


all_base_state_classes: dict[str, None] = {}


class BaseState(Base, ABC, extra=pydantic.Extra.allow):
    """The state of the app."""

    # A map from the var name to the var.
    vars: ClassVar[Dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[Dict[str, Var]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[Dict[str, ComputedVar]] = {}

    # Vars inherited by the parent state.
    inherited_vars: ClassVar[Dict[str, Var]] = {}

    # Backend base vars that are never sent to the client.
    backend_vars: ClassVar[Dict[str, Any]] = {}

    # Backend base vars inherited
    inherited_backend_vars: ClassVar[Dict[str, Any]] = {}

    # The event handlers.
    event_handlers: ClassVar[Dict[str, EventHandler]] = {}

    # A set of subclassses of this class.
    class_subclasses: ClassVar[set[Type[BaseState]]] = set()

    # Mapping of var name to set of (state_full_name, var_name) that depend on it.
    _var_dependencies: ClassVar[Dict[str, set[tuple[str, str]]]] = {}

    # Set of vars which always need to be recomputed
    _always_dirty_computed_vars: ClassVar[set[str]] = set()

    # Set of substates which always need to be recomputed
    _always_dirty_substates: ClassVar[set[str]] = set()

    # Set of states which might need to be recomputed if vars in this state change.
    _potentially_dirty_states: ClassVar[set[str]] = set()

    # The parent state.
    parent_state: BaseState | None = None

    # The substates of the state.
    substates: Dict[str, BaseState] = {}

    # The set of dirty vars.
    dirty_vars: set[str] = set()

    # The set of dirty substates.
    dirty_substates: set[str] = set()

    # The routing path that triggered the state
    router_data: Dict[str, Any] = {}

    # Per-instance copy of backend base variable values
    _backend_vars: Dict[str, Any] = {}

    # The router data for the current page
    router: RouterData = RouterData()

    # Whether the state has ever been touched since instantiation.
    _was_touched: bool = False

    # Whether this state class is a mixin and should not be instantiated.
    _mixin: ClassVar[bool] = False

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
        from reflex.utils.exceptions import ReflexRuntimeError

        if not _reflex_internal_init and not is_testing_env():
            raise ReflexRuntimeError(
                "State classes should not be instantiated directly in a Reflex app. "
                "See https://reflex.dev/docs/state/ for further information."
            )
        if type(self)._mixin:
            raise ReflexRuntimeError(
                f"{type(self).__name__} is a state mixin and cannot be instantiated directly."
            )
        kwargs["parent_state"] = parent_state
        super().__init__()
        for name, value in kwargs.items():
            setattr(self, name, value)

        # Setup the substates (for memory state manager only).
        if init_substates:
            for substate in self.get_substates():
                self.substates[substate.get_name()] = substate(
                    parent_state=self,
                    _reflex_internal_init=True,
                )

        # Create a fresh copy of the backend variables for this instance
        self._backend_vars = copy.deepcopy(self.backend_vars)

    def __repr__(self) -> str:
        """Get the string representation of the state.

        Returns:
            The string representation of the state.
        """
        return f"{type(self).__name__}({self.dict()})"

    @classmethod
    def _get_computed_vars(cls) -> list[ComputedVar]:
        """Helper function to get all computed vars of a instance.

        Returns:
            A list of computed vars.
        """
        return [
            v
            for mixin in [*cls._mixins(), cls]
            for name, v in mixin.__dict__.items()
            if is_computed_var(v) and name not in cls.inherited_vars
        ]

    @classmethod
    def _validate_module_name(cls) -> None:
        """Check if the module name is valid.

        Reflex uses ___ as state name module separator.

        Raises:
            NameError: If the module name is invalid.
        """
        if "___" in cls.__module__:
            raise NameError(
                "The module name of a State class cannot contain '___'. "
                "Please rename the module."
            )

    @classmethod
    def __init_subclass__(cls, mixin: bool = False, **kwargs):
        """Do some magic for the subclass initialization.

        Args:
            mixin: Whether the subclass is a mixin and should not be initialized.
            **kwargs: The kwargs to pass to the pydantic init_subclass method.

        Raises:
            StateValueError: If a substate class shadows another.
        """
        from reflex.utils.exceptions import StateValueError

        super().__init_subclass__(**kwargs)

        cls._mixin = mixin
        if mixin:
            return

        # Handle locally-defined states for pickling.
        if "<locals>" in cls.__qualname__:
            cls._handle_local_def()

        # Validate the module name.
        cls._validate_module_name()

        # Event handlers should not shadow builtin state methods.
        cls._check_overridden_methods()

        # Computed vars should not shadow builtin state props.
        cls._check_overridden_basevars()

        # Reset subclass tracking for this class.
        cls.class_subclasses = set()

        # Reset dirty substate tracking for this class.
        cls._always_dirty_substates = set()
        cls._potentially_dirty_states = set()

        # Get the parent vars.
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            cls.inherited_vars = parent_state.vars
            cls.inherited_backend_vars = parent_state.backend_vars

            # Check if another substate class with the same name has already been defined.
            if cls.get_name() in {c.get_name() for c in parent_state.class_subclasses}:
                # This should not happen, since we have added module prefix to state names in #3214
                raise StateValueError(
                    f"The substate class '{cls.get_name()}' has been defined multiple times. "
                    "Shadowing substate classes is not allowed."
                )
            # Track this new subclass in the parent state's subclasses set.
            parent_state.class_subclasses.add(cls)

        # Get computed vars.
        computed_vars = cls._get_computed_vars()
        cls._check_overridden_computed_vars()

        new_backend_vars = {
            name: value
            for name, value in cls.__dict__.items()
            if types.is_backend_base_variable(name, cls)
        }
        # Add annotated backend vars that may not have a default value.
        new_backend_vars.update(
            {
                name: cls._get_var_default(name, annotation_value)
                for name, annotation_value in cls._get_type_hints().items()
                if name not in new_backend_vars
                and types.is_backend_base_variable(name, cls)
            }
        )

        cls.backend_vars = {
            **cls.inherited_backend_vars,
            **new_backend_vars,
        }

        # Set the base and computed vars.
        cls.base_vars = {
            f.name: get_var_for_field(cls, f)
            for f in cls.get_fields().values()
            if f.name not in cls.get_skip_vars()
        }
        cls.computed_vars = {
            v._js_expr: v._replace(merge_var_data=VarData.from_state(cls))
            for v in computed_vars
        }
        cls.vars = {
            **cls.inherited_vars,
            **cls.base_vars,
            **cls.computed_vars,
        }
        cls.event_handlers = {}

        # Setup the base vars at the class level.
        for prop in cls.base_vars.values():
            cls._init_var(prop)

        # Set up the event handlers.
        events = {
            name: fn
            for name, fn in cls.__dict__.items()
            if cls._item_is_event_handler(name, fn)
        }

        for mixin_cls in cls._mixins():
            for name, value in mixin_cls.__dict__.items():
                if name in cls.inherited_vars:
                    continue
                if is_computed_var(value):
                    fget = cls._copy_fn(value.fget)
                    newcv = value._replace(fget=fget, _var_data=VarData.from_state(cls))
                    # cleanup refs to mixin cls in var_data
                    setattr(cls, name, newcv)
                    cls.computed_vars[newcv._js_expr] = newcv
                    cls.vars[newcv._js_expr] = newcv
                    continue
                if types.is_backend_base_variable(name, mixin_cls):
                    cls.backend_vars[name] = copy.deepcopy(value)
                    continue
                if events.get(name) is not None:
                    continue
                if not cls._item_is_event_handler(name, value):
                    continue
                if parent_state is not None and parent_state.event_handlers.get(name):
                    continue
                value = cls._copy_fn(value)
                value.__qualname__ = f"{cls.__name__}.{name}"
                events[name] = value

        # Create the setvar event handler for this state
        cls._create_setvar()

        for name, fn in events.items():
            handler = cls._create_event_handler(fn)
            cls.event_handlers[name] = handler
            setattr(cls, name, handler)

        # Initialize per-class var dependency tracking.
        cls._var_dependencies = {}
        cls._init_var_dependency_dicts()

        all_base_state_classes[cls.get_full_name()] = None

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
        if mark := getattr(fn, BACKGROUND_TASK_MARKER, None):
            setattr(newfn, BACKGROUND_TASK_MARKER, mark)
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
        console.warn(
            "The _evaluate method is experimental and may be removed in future versions."
        )
        from reflex.components.component import Component

        of_type = of_type or Component

        unique_var_name = get_unique_variable_name()

        @computed_var(_js_expr=unique_var_name, return_type=of_type)
        def computed_var_func(state: Self):
            result = f(state)

            if not _isinstance(result, of_type, nested=1, treat_var_as_type=False):
                console.warn(
                    f"Inline ComputedVar {f} expected type {of_type}, got {type(result)}. "
                    "You can specify expected type with `of_type` argument."
                )

            return result

        setattr(cls, unique_var_name, computed_var_func)
        cls.computed_vars[unique_var_name] = computed_var_func
        cls.vars[unique_var_name] = computed_var_func
        cls._update_substate_inherited_vars({unique_var_name: computed_var_func})
        cls._always_dirty_computed_vars.add(unique_var_name)

        return getattr(cls, unique_var_name)

    @classmethod
    def _mixins(cls) -> list[Type]:
        """Get the mixin classes of the state.

        Returns:
            The mixin classes of the state.
        """
        return [
            mixin
            for mixin in cls.__mro__
            if (
                mixin not in [pydantic.BaseModel, Base, cls]
                and issubclass(mixin, BaseState)
                and mixin._mixin is True
            )
        ]

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
    def _get_type_hints(cls) -> dict[str, Any]:
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
        for cvar_name, cvar in cls.computed_vars.items():
            if not cvar._cache:
                # Do not perform dep calculation when cache=False (these are always dirty).
                continue
            for state_name, dvar_set in cvar._deps(objclass=cls).items():
                state_cls = cls.get_root_state().get_class_substate(state_name)
                for dvar in dvar_set:
                    defining_state_cls = state_cls
                    while dvar in {
                        *defining_state_cls.inherited_vars,
                        *defining_state_cls.inherited_backend_vars,
                    }:
                        parent_state = defining_state_cls.get_parent_state()
                        if parent_state is not None:
                            defining_state_cls = parent_state
                    defining_state_cls._var_dependencies.setdefault(dvar, set()).add(
                        (cls.get_full_name(), cvar_name)
                    )
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
    def _check_overridden_methods(cls):
        """Check for shadow methods and raise error if any.

        Raises:
            EventHandlerShadowsBuiltInStateMethodError: When an event handler shadows an inbuilt state method.
        """
        overridden_methods = set()
        state_base_functions = cls._get_base_functions()
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            # Check if the method is overridden and not a dunder method
            if (
                not name.startswith("__")
                and method.__name__ in state_base_functions
                and state_base_functions[method.__name__] != method
            ):
                overridden_methods.add(method.__name__)

        for method_name in overridden_methods:
            raise EventHandlerShadowsBuiltInStateMethodError(
                f"The event handler name `{method_name}` shadows a builtin State method; use a different name instead"
            )

    @classmethod
    def _check_overridden_basevars(cls):
        """Check for shadow base vars and raise error if any.

        Raises:
            ComputedVarShadowsBaseVarsError: When a computed var shadows a base var.
        """
        for computed_var_ in cls._get_computed_vars():
            if computed_var_._js_expr in cls.__annotations__:
                raise ComputedVarShadowsBaseVarsError(
                    f"The computed var name `{computed_var_._js_expr}` shadows a base var in {cls.__module__}.{cls.__name__}; use a different name instead"
                )

    @classmethod
    def _check_overridden_computed_vars(cls) -> None:
        """Check for shadow computed vars and raise error if any.

        Raises:
            ComputedVarShadowsStateVarError: When a computed var shadows another.
        """
        for name, cv in cls.__dict__.items():
            if not is_computed_var(cv):
                continue
            name = cv._js_expr
            if name in cls.inherited_vars or name in cls.inherited_backend_vars:
                raise ComputedVarShadowsStateVarError(
                    f"The computed var name `{cv._js_expr}` shadows a var in {cls.__module__}.{cls.__name__}; use a different name instead"
                )

    @classmethod
    def get_skip_vars(cls) -> set[str]:
        """Get the vars to skip when serializing.

        Returns:
            The vars to skip when serializing.
        """
        return (
            set(cls.inherited_vars)
            | {
                "parent_state",
                "substates",
                "dirty_vars",
                "dirty_substates",
                "router_data",
            }
            | types.RESERVED_BACKEND_VAR_NAMES
        )

    @classmethod
    @functools.lru_cache()
    def get_parent_state(cls) -> Type[BaseState] | None:
        """Get the parent state.

        Raises:
            ValueError: If more than one parent state is found.

        Returns:
            The parent state.
        """
        parent_states = [
            base
            for base in cls.__bases__
            if issubclass(base, BaseState) and base is not BaseState and not base._mixin
        ]
        if len(parent_states) >= 2:
            raise ValueError(f"Only one parent state is allowed {parent_states}.")
        # The first non-mixin state in the mro is our parent.
        for base in cls.mro()[1:]:
            if not issubclass(base, BaseState) or base._mixin:
                continue
            if base is BaseState:
                break
            return base
        return None  # No known parent

    @classmethod
    @functools.lru_cache()
    def get_root_state(cls) -> Type[BaseState]:
        """Get the root state.

        Returns:
            The root state.
        """
        parent_state = cls.get_parent_state()
        return cls if parent_state is None else parent_state.get_root_state()

    @classmethod
    def get_substates(cls) -> set[Type[BaseState]]:
        """Get the substates of the state.

        Returns:
            The substates of the state.
        """
        return cls.class_subclasses

    @classmethod
    @functools.lru_cache()
    def get_name(cls) -> str:
        """Get the name of the state.

        Returns:
            The name of the state.
        """
        module = cls.__module__.replace(".", "___")
        return format.to_snake_case(f"{module}___{cls.__name__}")

    @classmethod
    @functools.lru_cache()
    def get_full_name(cls) -> str:
        """Get the full name of the state.

        Returns:
            The full name of the state.
        """
        name = cls.get_name()
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            name = ".".join((parent_state.get_full_name(), name))
        return name

    @classmethod
    @functools.lru_cache()
    def get_class_substate(cls, path: Sequence[str] | str) -> Type[BaseState]:
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
        raise ValueError(f"Invalid path: {path}")

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
            raise ValueError(f"Invalid path: {path}")
        return getattr(substate, name)

    @classmethod
    def _init_var(cls, prop: Var):
        """Initialize a variable.

        Args:
            prop: The variable to initialize

        Raises:
            VarTypeError: if the variable has an incorrect type
        """
        from reflex.utils.exceptions import VarTypeError

        if not types.is_valid_var_type(prop._var_type):
            raise VarTypeError(
                "State vars must be of a serializable type. "
                "Valid types include strings, numbers, booleans, lists, "
                "dictionaries, dataclasses, datetime objects, and pydantic models. "
                f'Found var "{prop._js_expr}" with type {prop._var_type}.'
            )
        cls._set_var(prop)
        cls._create_setter(prop)
        cls._set_default_value(prop)

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
            raise NameError(
                f"The variable '{name}' already exist. Use a different name"
            )

        # create the variable based on name and type
        var = Var(
            _js_expr=format.format_state_name(cls.get_full_name()) + "." + name,
            _var_type=type_,
            _var_data=VarData.from_state(cls, name),
        ).guess_type()

        # add the pydantic field dynamically (must be done before _init_var)
        cls.add_field(var, default_value)

        cls._init_var(var)

        # update the internal dicts so the new variable is correctly handled
        cls.base_vars.update({name: var})
        cls.vars.update({name: var})

        # let substates know about the new variable
        for substate_class in cls.class_subclasses:
            substate_class.vars.setdefault(name, var)

        # Reinitialize dependency tracking dicts.
        cls._init_var_dependency_dicts()

    @classmethod
    def _set_var(cls, prop: Var):
        """Set the var as a class member.

        Args:
            prop: The var instance to set.
        """
        setattr(cls, prop._var_field_name, prop)

    @classmethod
    def _create_event_handler(cls, fn: Any):
        """Create an event handler for the given function.

        Args:
            fn: The function to create an event handler for.

        Returns:
            The event handler.
        """
        return EventHandler(fn=fn, state_full_name=cls.get_full_name())

    @classmethod
    def _create_setvar(cls):
        """Create the setvar method for the state."""
        cls.setvar = cls.event_handlers["setvar"] = EventHandlerSetVar(state_cls=cls)

    @classmethod
    def _create_setter(cls, prop: Var):
        """Create a setter for the var.

        Args:
            prop: The var to create a setter for.
        """
        setter_name = prop._get_setter_name(include_state=False)
        if setter_name not in cls.__dict__:
            event_handler = cls._create_event_handler(prop._get_setter())
            cls.event_handlers[setter_name] = event_handler
            setattr(cls, setter_name, event_handler)

    @classmethod
    def _set_default_value(cls, prop: Var):
        """Set the default value for the var.

        Args:
            prop: The var to set the default value for.
        """
        # Get the pydantic field for the var.
        field = cls.get_fields()[prop._var_field_name]
        if field.required:
            default_value = prop._get_default_value()
            if default_value is not None:
                field.required = False
                field.default = default_value
        if (
            not field.required
            and field.default is None
            and field.default_factory is None
            and not types.is_optional(prop._var_type)
        ):
            # Ensure frontend uses null coalescing when accessing.
            object.__setattr__(prop, "_var_type", Optional[prop._var_type])

    @classmethod
    def _get_var_default(cls, name: str, annotation_value: Any) -> Any:
        """Get the default value of a (backend) var.

        Args:
            name: The name of the var.
            annotation_value: The annotation value of the var.

        Returns:
            The default value of the var or None.
        """
        try:
            return getattr(cls, name)
        except AttributeError:
            try:
                return Var("", _var_type=annotation_value)._get_default_value()
            except TypeError:
                pass
        return None

    @staticmethod
    def _get_base_functions() -> dict[str, FunctionType]:
        """Get all functions of the state class excluding dunder methods.

        Returns:
            The functions of rx.State class as a dict.
        """
        return {
            func[0]: func[1]
            for func in inspect.getmembers(BaseState, predicate=inspect.isfunction)
            if not func[0].startswith("__")
        }

    @classmethod
    def _update_substate_inherited_vars(cls, vars_to_add: dict[str, Var]):
        """Update the inherited vars of substates recursively when new vars are added.

        Also updates the var dependency tracking dicts after adding vars.

        Args:
            vars_to_add: names to Var instances to add to substates
        """
        for substate_class in cls.class_subclasses:
            for name, var in vars_to_add.items():
                if types.is_backend_base_variable(name, cls):
                    substate_class.backend_vars.setdefault(name, var)
                    substate_class.inherited_backend_vars.setdefault(name, var)
                else:
                    substate_class.vars.setdefault(name, var)
                    substate_class.inherited_vars.setdefault(name, var)
                substate_class._update_substate_inherited_vars(vars_to_add)
        # Reinitialize dependency tracking dicts.
        cls._init_var_dependency_dicts()

    @classmethod
    def setup_dynamic_args(cls, args: dict[str, str]):
        """Set up args for easy access in renderer.

        Args:
            args: a dict of args
        """
        if not args:
            return

        cls._check_overwritten_dynamic_args(list(args.keys()))

        def argsingle_factory(param: str):
            def inner_func(self: BaseState) -> str:
                return self.router.page.params.get(param, "")

            return inner_func

        def arglist_factory(param: str):
            def inner_func(self: BaseState) -> list[str]:
                return self.router.page.params.get(param, [])

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
                deps=["router"],
                _js_expr=param,
                _var_data=VarData.from_state(cls),
            )
            setattr(cls, param, dynamic_vars[param])

        # Update tracking dicts.
        cls.computed_vars.update(dynamic_vars)
        cls.vars.update(dynamic_vars)
        cls._update_substate_inherited_vars(dynamic_vars)

    @classmethod
    def _check_overwritten_dynamic_args(cls, args: list[str]):
        """Check if dynamic args are shadowing existing vars. Recursively checks all child states.

        Args:
            args: a dict of args

        Raises:
            DynamicRouteArgShadowsStateVarError: If a dynamic arg is shadowing an existing var.
        """
        for arg in args:
            if (
                arg in cls.computed_vars
                and not isinstance(cls.computed_vars[arg], DynamicRouteVar)
            ) or arg in cls.base_vars:
                raise DynamicRouteArgShadowsStateVarError(
                    f"Dynamic route arg '{arg}' is shadowing an existing var in {cls.__module__}.{cls.__name__}"
                )
        for substate in cls.get_substates():
            substate._check_overwritten_dynamic_args(args)

    def __getattribute__(self, name: str) -> Any:
        """Get the state var.

        If the var is inherited, get the var from the parent state.

        Args:
            name: The name of the var.

        Returns:
            The value of the var.
        """
        # If the state hasn't been initialized yet, return the default value.
        if not super().__getattribute__("__dict__"):
            return super().__getattribute__(name)

        # Fast path for dunder
        if name.startswith("__"):
            return super().__getattribute__(name)

        # For now, handle router_data updates as a special case.
        if (
            name == constants.ROUTER_DATA
            or name in super().__getattribute__("inherited_vars")
            or name in super().__getattribute__("inherited_backend_vars")
        ):
            parent_state = super().__getattribute__("parent_state")
            if parent_state is not None:
                return getattr(parent_state, name)

        # Allow event handlers to be called on the instance directly.
        event_handlers = super().__getattribute__("event_handlers")
        if name in event_handlers:
            handler = event_handlers[name]
            if handler.is_background:
                fn = _no_chain_background_task(type(self), name, handler.fn)
            else:
                fn = functools.partial(handler.fn, self)
            fn.__module__ = handler.fn.__module__
            fn.__qualname__ = handler.fn.__qualname__
            return fn

        backend_vars = super().__getattribute__("_backend_vars")
        if name in backend_vars:
            value = backend_vars[name]
        else:
            value = super().__getattribute__(name)

        if isinstance(value, EventHandler):
            # The event handler is inherited from a parent, so let the parent convert
            # it to a callable function.
            parent_state = super().__getattribute__("parent_state")
            if parent_state is not None:
                return getattr(parent_state, name)

        if MutableProxy._is_mutable_type(value) and (
            name in super().__getattribute__("base_vars") or name in backend_vars
        ):
            # track changes in mutable containers (list, dict, set, etc)
            return MutableProxy(wrapped=value, state=self, field_name=name)

        return value

    def __setattr__(self, name: str, value: Any):
        """Set the attribute.

        If the attribute is inherited, set the attribute on the parent state.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.

        Raises:
            SetUndefinedStateVarError: If a value of a var is set without first defining it.
        """
        if isinstance(value, MutableProxy):
            # unwrap proxy objects when assigning back to the state
            value = value.__wrapped__

        # Set the var on the parent state.
        if name in self.inherited_vars or name in self.inherited_backend_vars:
            setattr(self.parent_state, name, value)
            return

        if name in self.backend_vars:
            self._backend_vars.__setitem__(name, value)
            self.dirty_vars.add(name)
            self._mark_dirty()
            return

        if (
            name not in self.vars
            and name not in self.get_skip_vars()
            and not name.startswith("__")
            and not name.startswith(
                f"_{getattr(type(self), '__original_name__', type(self).__name__)}__"
            )
        ):
            raise SetUndefinedStateVarError(
                f"The state variable '{name}' has not been defined in '{type(self).__name__}'. "
                f"All state variables must be declared before they can be set."
            )

        fields = self.get_fields()

        if name in fields:
            field = fields[name]
            field_type = _unwrap_field_type(true_type_for_pydantic_field(field))
            if not _isinstance(value, field_type, nested=1, treat_var_as_type=False):
                console.error(
                    f"Expected field '{type(self).__name__}.{name}' to receive type '{field_type}',"
                    f" but got '{value}' of type '{type(value)}'."
                )

        # Set the attribute.
        super().__setattr__(name, value)

        # Add the var to the dirty list.
        if name in self.base_vars:
            self.dirty_vars.add(name)
            self._mark_dirty()

        # For now, handle router_data updates as a special case
        if name == constants.ROUTER_DATA:
            self.dirty_vars.add(name)
            self._mark_dirty()

    def reset(self):
        """Reset all the base vars to their default values."""
        # Reset the base vars.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            if prop_name == constants.ROUTER:
                continue  # never reset the router data
            field = fields[prop_name]
            if default_factory := field.default_factory:
                default = default_factory()
            else:
                default = copy.deepcopy(field.default)
            setattr(self, prop_name, default)

        # Reset the backend vars.
        for prop_name, value in self.backend_vars.items():
            setattr(self, prop_name, copy.deepcopy(value))

        # Recursively reset the substates.
        for substate in self.substates.values():
            substate.reset()

    def _reset_client_storage(self):
        """Reset client storage base vars to their default values."""
        # Client-side storage is reset during hydrate so that clearing cookies
        # on the browser also resets the values on the backend.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            field = fields[prop_name]
            if isinstance(field.default, ClientStorageBase) or (
                isinstance(field.type_, type)
                and issubclass(field.type_, ClientStorageBase)
            ):
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
            raise ValueError(f"Invalid path: {path}")
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
        }.union(
            {
                cls.get_root_state().get_class_substate(substate_name)
                for substate_name in cls._potentially_dirty_states
            }
        )

    def _get_root_state(self) -> BaseState:
        """Get the root state of the state tree.

        Returns:
            The root state of the state tree.
        """
        parent_state = self
        while parent_state.parent_state is not None:
            parent_state = parent_state.parent_state
        return parent_state

    async def _get_state_from_redis(self, state_cls: Type[T_STATE]) -> T_STATE:
        """Get a state instance from redis.

        Args:
            state_cls: The class of the state.

        Returns:
            The instance of state_cls associated with this state's client_token.

        Raises:
            RuntimeError: If redis is not used in this backend process.
            StateMismatchError: If the state instance is not of the expected type.
        """
        # Then get the target state and all its substates.
        state_manager = get_state_manager()
        if not isinstance(state_manager, StateManagerRedis):
            raise RuntimeError(
                f"Requested state {state_cls.get_full_name()} is not cached and cannot be accessed without redis. "
                "(All states should already be available -- this is likely a bug).",
            )
        state_in_redis = await state_manager.get_state(
            token=_substate_key(self.router.session.client_token, state_cls),
            top_level=False,
            for_state_instance=self,
        )

        if not isinstance(state_in_redis, state_cls):
            raise StateMismatchError(
                f"Searched for state {state_cls.get_full_name()} but found {state_in_redis}."
            )

        return state_in_redis

    def _get_state_from_cache(self, state_cls: Type[T_STATE]) -> T_STATE:
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
            raise StateMismatchError(
                f"Searched for state {state_cls.get_full_name()} but found {substate}."
            )
        return substate

    async def get_state(self, state_cls: Type[T_STATE]) -> T_STATE:
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
        if (var_value := getattr(var, "_var_value", unset)) is not unset:
            return var_value  # pyright: ignore [reportReturnType]

        var_data = var._get_all_var_data()
        if var_data is None or not var_data.state:
            raise UnretrievableVarValueError(
                f"Unable to retrieve value for {var._js_expr}: not associated with any state."
            )
        # Fastish case: this var belongs to this state
        if var_data.state == self.get_full_name():
            return getattr(self, var_data.field_name)

        # Slow case: this var belongs to another state
        other_state = await self.get_state(
            self._get_root_state().get_class_substate(var_data.state)
        )
        return getattr(other_state, var_data.field_name)

    def _get_event_handler(
        self, event: Event
    ) -> tuple[BaseState | StateProxy, EventHandler]:
        """Get the event handler for the given event.

        Args:
            event: The event to get the handler for.


        Returns:
            The event handler.

        Raises:
            ValueError: If the event handler or substate is not found.
        """
        # Get the event handler.
        path = event.name.split(".")
        path, name = path[:-1], path[-1]
        substate = self.get_substate(path)
        if not substate:
            raise ValueError(
                "The value of state cannot be None when processing an event."
            )
        handler = substate.event_handlers[name]

        # For background tasks, proxy the state
        if handler.is_background:
            substate = StateProxy(substate)

        return substate, handler

    async def _process(self, event: Event) -> AsyncIterator[StateUpdate]:
        """Obtain event info and process event.

        Args:
            event: The event to process.

        Yields:
            The state update after processing the event.
        """
        # Get the event handler.
        substate, handler = self._get_event_handler(event)

        # Run the event generator and yield state updates.
        async for update in self._process_event(
            handler=handler,
            state=substate,
            payload=event.payload,
        ):
            yield update

    def _check_valid(self, handler: EventHandler, events: Any) -> Any:
        """Check if the events yielded are valid. They must be EventHandlers or EventSpecs.

        Args:
            handler: EventHandler.
            events: The events to be checked.

        Raises:
            TypeError: If any of the events are not valid.

        Returns:
            The events as they are if valid.
        """

        def _is_valid_type(events: Any) -> bool:
            return isinstance(events, (Event, EventHandler, EventSpec))

        if events is None or _is_valid_type(events):
            return events

        if not isinstance(events, Sequence):
            events = [events]

        try:
            if all(_is_valid_type(e) for e in events):
                return events
        except TypeError:
            pass

        coroutines = [e for e in events if asyncio.iscoroutine(e)]

        for coroutine in coroutines:
            coroutine_name = coroutine.__qualname__
            warnings.filterwarnings(
                "ignore", message=f"coroutine '{coroutine_name}' was never awaited"
            )

        raise TypeError(
            f"Your handler {handler.fn.__qualname__} must only return/yield: None, Events or other EventHandlers referenced by their class (i.e. using `type(self)` or other class references)."
            f" Returned events of types {', '.join(map(str, map(type, events)))!s}."
        )

    async def _as_state_update(
        self,
        handler: EventHandler,
        events: EventSpec | list[EventSpec] | None,
        final: bool,
    ) -> StateUpdate:
        """Convert the events to a StateUpdate.

        Fixes the events and checks for validity before converting.

        Args:
            handler: The handler where the events originated from.
            events: The events to queue with the update.
            final: Whether the handler is done processing.

        Returns:
            The valid StateUpdate containing the events and final flag.
        """
        # get the delta from the root of the state tree
        state = self._get_root_state()

        token = self.router.session.client_token

        # Convert valid EventHandler and EventSpec into Event
        fixed_events = fix_events(self._check_valid(handler, events), token)

        try:
            # Get the delta after processing the event.
            delta = await _resolve_delta(state.get_delta())
            state._clean()

            return StateUpdate(
                delta=delta,
                events=fixed_events,
                final=final if not handler.is_background else True,
            )
        except Exception as ex:
            state._clean()

            event_specs = (
                prerequisites.get_and_validate_app().app.backend_exception_handler(ex)
            )

            if event_specs is None:
                return StateUpdate()

            event_specs_correct_type = cast(
                list[EventSpec | EventHandler] | None,
                [event_specs] if isinstance(event_specs, EventSpec) else event_specs,
            )
            fixed_events = fix_events(
                event_specs_correct_type,
                token,
                router_data=state.router_data,
            )
            return StateUpdate(
                events=fixed_events,
                final=True,
            )

    async def _process_event(
        self, handler: EventHandler, state: BaseState | StateProxy, payload: Dict
    ) -> AsyncIterator[StateUpdate]:
        """Process event.

        Args:
            handler: EventHandler to process.
            state: State to process the handler.
            payload: The event payload.

        Yields:
            StateUpdate object

        Raises:
            ValueError: If a string value is received for an int or float type and cannot be converted.
        """
        from reflex.utils import telemetry

        # Get the function to process the event.
        fn = functools.partial(handler.fn, state)

        try:
            type_hints = typing.get_type_hints(handler.fn)
        except Exception:
            type_hints = {}

        for arg, value in list(payload.items()):
            hinted_args = type_hints.get(arg, Any)
            if hinted_args is Any:
                continue
            if is_union(hinted_args):
                if value is None:
                    continue
                hinted_args = value_inside_optional(hinted_args)
            if (
                isinstance(value, dict)
                and inspect.isclass(hinted_args)
                and not types.is_generic_alias(hinted_args)  # py3.10
            ):
                if issubclass(hinted_args, Model):
                    # Remove non-fields from the payload
                    payload[arg] = hinted_args(
                        **{
                            key: value
                            for key, value in value.items()
                            if key in hinted_args.__fields__
                        }
                    )
                elif dataclasses.is_dataclass(hinted_args) or issubclass(
                    hinted_args, (Base, BaseModelV1, BaseModelV2)
                ):
                    payload[arg] = hinted_args(**value)
            elif isinstance(value, list) and (hinted_args is set or hinted_args is Set):
                payload[arg] = set(value)
            elif isinstance(value, list) and (
                hinted_args is tuple or hinted_args is Tuple
            ):
                payload[arg] = tuple(value)
            elif isinstance(value, str) and (
                hinted_args is int or hinted_args is float
            ):
                try:
                    payload[arg] = hinted_args(value)
                except ValueError:
                    raise ValueError(
                        f"Received a string value ({value}) for {arg} but expected a {hinted_args}"
                    ) from None
                else:
                    console.warn(
                        f"Received a string value ({value}) for {arg} but expected a {hinted_args}. A simple conversion was successful."
                    )

        # Wrap the function in a try/except block.
        try:
            # Handle async functions.
            if asyncio.iscoroutinefunction(fn.func):
                events = await fn(**payload)

            # Handle regular functions.
            else:
                events = fn(**payload)
            # Handle async generators.
            if inspect.isasyncgen(events):
                async for event in events:
                    yield await state._as_state_update(handler, event, final=False)
                yield await state._as_state_update(handler, events=None, final=True)

            # Handle regular generators.
            elif inspect.isgenerator(events):
                try:
                    while True:
                        yield await state._as_state_update(
                            handler, next(events), final=False
                        )
                except StopIteration as si:
                    # the "return" value of the generator is not available
                    # in the loop, we must catch StopIteration to access it
                    if si.value is not None:
                        yield await state._as_state_update(
                            handler, si.value, final=False
                        )
                yield await state._as_state_update(handler, events=None, final=True)

            # Handle regular event chains.
            else:
                yield await state._as_state_update(handler, events, final=True)

        # If an error occurs, throw a window alert.
        except Exception as ex:
            telemetry.send_error(ex, context="backend")

            event_specs = (
                prerequisites.get_and_validate_app().app.backend_exception_handler(ex)
            )

            yield await state._as_state_update(
                handler,
                event_specs,
                final=True,
            )

    def _mark_dirty_computed_vars(self) -> None:
        """Mark ComputedVars that need to be recalculated based on dirty_vars."""
        # Append expired computed vars to dirty_vars to trigger recalculation
        self.dirty_vars.update(self._expired_computed_vars())
        # Append always dirty computed vars to dirty_vars to trigger recalculation
        self.dirty_vars.update(self._always_dirty_computed_vars)

        dirty_vars = self.dirty_vars
        while dirty_vars:
            calc_vars, dirty_vars = dirty_vars, set()
            for state_name, cvar in self._dirty_computed_vars(from_vars=calc_vars):
                if state_name == self.get_full_name():
                    defining_state = self
                else:
                    defining_state = self._get_root_state().get_substate(
                        tuple(state_name.split("."))
                    )
                defining_state.dirty_vars.add(cvar)
                dirty_vars.add(cvar)
                actual_var = defining_state.computed_vars.get(cvar)
                if actual_var is not None:
                    actual_var.mark_dirty(instance=defining_state)
                if defining_state is not self:
                    defining_state._mark_dirty()

    def _expired_computed_vars(self) -> set[str]:
        """Determine ComputedVars that need to be recalculated based on the expiration time.

        Returns:
            Set of computed vars to include in the delta.
        """
        return {
            cvar
            for cvar in self.computed_vars
            if self.computed_vars[cvar].needs_update(instance=self)
        }

    def _dirty_computed_vars(
        self, from_vars: set[str] | None = None, include_backend: bool = True
    ) -> set[tuple[str, str]]:
        """Determine ComputedVars that need to be recalculated based on the given vars.

        Args:
            from_vars: find ComputedVar that depend on this set of vars. If unspecified, will use the dirty_vars.
            include_backend: whether to include backend vars in the calculation.

        Returns:
            Set of computed vars to include in the delta.
        """
        return {
            (state_name, cvar)
            for dirty_var in from_vars or self.dirty_vars
            for state_name, cvar in self._var_dependencies.get(dirty_var, set())
            if include_backend or not self.computed_vars[cvar]._backend
        }

    def get_delta(self) -> Delta:
        """Get the delta for the state.

        Returns:
            The delta for the state.
        """
        delta = {}

        self._mark_dirty_computed_vars()
        frontend_computed_vars: set[str] = {
            name for name, cv in self.computed_vars.items() if not cv._backend
        }

        # Return the dirty vars for this instance, any cached/dependent computed vars,
        # and always dirty computed vars (cache=False)
        delta_vars = self.dirty_vars.intersection(self.base_vars).union(
            self.dirty_vars.intersection(frontend_computed_vars)
        )

        subdelta: dict[str, Any] = {
            prop: self.get_value(prop)
            for prop in delta_vars
            if not types.is_backend_base_variable(prop, type(self))
        }

        if len(subdelta) > 0:
            delta[self.get_full_name()] = subdelta

        # Recursively find the substate deltas.
        substates = self.substates
        for substate in self.dirty_substates.union(self._always_dirty_substates):
            delta.update(substates[substate].get_delta())

        # Return the delta.
        return delta

    def _mark_dirty(self):
        """Mark the substate and all parent states as dirty."""
        state_name = self.get_name()
        if (
            self.parent_state is not None
            and state_name not in self.parent_state.dirty_substates
        ):
            self.parent_state.dirty_substates.add(self.get_name())
            self.parent_state._mark_dirty()

        # have to mark computed vars dirty to allow access to newly computed
        # values within the same ComputedVar function
        self._mark_dirty_computed_vars()

    def _update_was_touched(self):
        """Update the _was_touched flag based on dirty_vars."""
        if self.dirty_vars and not self._was_touched:
            for var in self.dirty_vars:
                if var in self.base_vars or var in self._backend_vars:
                    self._was_touched = True
                    break
                if var == constants.ROUTER_DATA and self.parent_state is None:
                    self._was_touched = True
                    break

    def _get_was_touched(self) -> bool:
        """Check current dirty_vars and flag to determine if state instance was modified.

        If any dirty vars belong to this state, mark _was_touched.

        This flag determines whether this state instance should be persisted to redis.

        Returns:
            Whether this state instance was ever modified.
        """
        # Ensure the flag is up to date based on the current dirty_vars
        self._update_was_touched()
        return self._was_touched

    def _clean(self):
        """Reset the dirty vars."""
        # Update touched status before cleaning dirty_vars.
        self._update_was_touched()

        # Recursively clean the substates.
        for substate in self.dirty_substates:
            if substate not in self.substates:
                continue
            self.substates[substate]._clean()

        # Clean this state.
        self.dirty_vars = set()
        self.dirty_substates = set()

    def get_value(self, key: str) -> Any:
        """Get the value of a field (without proxying).

        The returned value will NOT track dirty state updates.

        Args:
            key: The key of the field.

        Returns:
            The value of the field.
        """
        value = super().get_value(key)
        if isinstance(value, MutableProxy):
            return value.__wrapped__
        return value

    def dict(
        self, include_computed: bool = True, initial: bool = False, **kwargs
    ) -> dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            include_computed: Whether to include computed vars.
            initial: Whether to get the initial value of computed vars.
            **kwargs: Kwargs to pass to the pydantic dict method.

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
            self.get_full_name(): {k: variables[k] for k in sorted(variables)},
        }
        for substate_d in [
            v.dict(include_computed=include_computed, initial=initial, **kwargs)
            for v in self.substates.values()
        ]:
            d.update(substate_d)

        return d

    async def __aenter__(self) -> BaseState:
        """Enter the async context manager protocol.

        This should not be used for the State class, but exists for
        type-compatibility with StateProxy.

        Raises:
            TypeError: always, because async contextmanager protocol is only supported for background task.
        """
        raise TypeError(
            "Only background task should use `async with self` to modify state."
        )

    async def __aexit__(self, *exc_info: Any) -> None:
        """Exit the async context manager protocol.

        This should not be used for the State class, but exists for
        type-compatibility with StateProxy.

        Args:
            exc_info: The exception info tuple.
        """
        pass

    def __getstate__(self):
        """Get the state for redis serialization.

        This method is called by pickle to serialize the object.

        It explicitly removes parent_state and substates because those are serialized separately
        by the StateManagerRedis to allow for better horizontal scaling as state size increases.

        Returns:
            The state dict for serialization.
        """
        state = super().__getstate__()
        state["__dict__"] = state["__dict__"].copy()
        if state["__dict__"].get("parent_state") is not None:
            # Do not serialize router data in substates (only the root state).
            state["__dict__"].pop("router", None)
            state["__dict__"].pop("router_data", None)
        # Never serialize parent_state or substates.
        state["__dict__"].pop("parent_state", None)
        state["__dict__"].pop("substates", None)
        state["__dict__"].pop("_was_touched", None)
        # Remove all inherited vars.
        for inherited_var_name in self.inherited_vars:
            state["__dict__"].pop(inherited_var_name, None)
        return state

    def __setstate__(self, state: dict[str, Any]):
        """Set the state from redis deserialization.

        This method is called by pickle to deserialize the object.

        Args:
            state: The state dict for deserialization.
        """
        state["__dict__"]["parent_state"] = None
        state["__dict__"]["substates"] = {}
        super().__setstate__(state)

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
                console.warn(msg)
            elif environment.REFLEX_PERF_MODE.get() == PerformanceMode.RAISE:
                raise StateTooLargeError(msg)
            _WARNED_ABOUT_STATE_SIZE.add(state_full_name)

    @classmethod
    @functools.lru_cache()
    def _to_schema(cls) -> str:
        """Convert a state to a schema.

        Returns:
            The hash of the schema.
        """

        def _field_tuple(
            field_name: str,
        ) -> tuple[str, str, Any, bool | None, Any]:
            model_field = cls.__fields__[field_name]
            return (
                field_name,
                model_field.name,
                _serialize_type(model_field.type_),
                (
                    model_field.required
                    if isinstance(model_field.required, bool)
                    else None
                ),
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
        """
        payload = b""
        error = ""
        try:
            payload = pickle.dumps((self._to_schema(), self))
        except HANDLED_PICKLE_ERRORS as og_pickle_error:
            error = (
                f"Failed to serialize state {self.get_full_name()} due to unpicklable object. "
                "This state will not be persisted. "
            )
            try:
                import dill

                payload = dill.dumps((self._to_schema(), self))
            except ImportError:
                error += (
                    f"Pickle error: {og_pickle_error}. "
                    "Consider `pip install 'dill>=0.3.8'` for more exotic serialization support."
                )
            except HANDLED_PICKLE_ERRORS as ex:
                error += f"Dill was also unable to pickle the state: {ex}"
            console.warn(error)

        if environment.REFLEX_PERF_MODE.get() != PerformanceMode.OFF:
            self._check_state_size(len(payload))

        if not payload:
            raise StateSerializationError(error)

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
            raise ValueError("Only one of `data` or `fp` must be provided")
        if substate_schema != state._to_schema():
            raise StateSchemaMismatchError()
        return state


T_STATE = TypeVar("T_STATE", bound=BaseState)


class State(BaseState):
    """The app Base State."""

    # The hydrated bool.
    is_hydrated: bool = False


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
        raise DynamicComponentInvalidSignatureError(
            "The function must have exactly one parameter, which is the state class."
        )

    if len(values) != 1:
        raise DynamicComponentInvalidSignatureError(
            "You must provide a type hint for the state class in the function."
        )

    state_class: Type[T] = values[0]

    def wrapper() -> Component:
        from reflex.components.base.fragment import fragment

        return fragment(state_class._evaluate(lambda state: func(state)))

    return wrapper


class FrontendEventExceptionState(State):
    """Substate for handling frontend exceptions."""

    @event
    def handle_frontend_exception(self, stack: str, component_stack: str) -> None:
        """Handle frontend exceptions.

        If a frontend exception handler is provided, it will be called.
        Otherwise, the default frontend exception handler will be called.

        Args:
            stack: The stack trace of the exception.
            component_stack: The stack trace of the component where the exception occurred.

        """
        prerequisites.get_and_validate_app().app.frontend_exception_handler(
            Exception(stack)
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
            var_state_cls = State.get_class_substate(state_name)
            var_state = await self.get_state(var_state_cls)
            setattr(var_state, var_name, value)


class OnLoadInternalState(State):
    """Substate for handling on_load event enumeration.

    This is a separate substate to avoid deserializing the entire state tree for every page navigation.
    """

    def on_load_internal(self) -> list[Event | EventSpec] | None:
        """Queue on_load handlers for the current page.

        Returns:
            The list of events to queue for on load handling.
        """
        # Do not app._compile()!  It should be already compiled by now.
        load_events = prerequisites.get_and_validate_app().app.get_load_events(
            self.router.page.path
        )
        if not load_events:
            self.is_hydrated = True
            return  # Fast path for navigation with no on_load events defined.
        self.is_hydrated = False
        return [
            *fix_events(
                cast(list[EventSpec | EventHandler], load_events),
                self.router.session.client_token,
                router_data=self.router_data,
            ),
            State.set_is_hydrated(True),  # pyright: ignore [reportAttributeAccessIssue]
        ]


class ComponentState(State, mixin=True):
    """Base class to allow for the creation of a state instance per component.

    This allows for the bundling of UI and state logic into a single class,
    where each instance has a separate instance of the state.

    Subclass this class and define vars and event handlers in the traditional way.
    Then define a `get_component` method that returns the UI for the component instance.

    See the full [docs](https://reflex.dev/docs/substates/component-state/) for more.

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
        if type(self)._mixin:
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
            **kwargs: The kwargs to pass to the pydantic init_subclass method.
        """
        super().__init_subclass__(mixin=mixin, **kwargs)

    @classmethod
    def get_component(cls, *children, **props) -> "Component":
        """Get the component instance.

        Args:
            children: The children of the component.
            props: The props of the component.

        Raises:
            NotImplementedError: if the subclass does not override this method.
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement get_component to return the component instance."
        )

    @classmethod
    def create(cls, *children, **props) -> "Component":
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


class StateProxy(wrapt.ObjectProxy):
    """Proxy of a state instance to control mutability of vars for a background task.

    Since a background task runs against a state instance without holding the
    state_manager lock for the token, the reference may become stale if the same
    state is modified by another event handler.

    The proxy object ensures that writes to the state are blocked unless
    explicitly entering a context which refreshes the state from state_manager
    and holds the lock for the token until exiting the context. After exiting
    the context, a StateUpdate may be emitted to the frontend to notify the
    client of the state change.

    A background task will be passed the `StateProxy` as `self`, so mutability
    can be safely performed inside an `async with self` block.

        class State(rx.State):
            counter: int = 0

            @rx.event(background=True)
            async def bg_increment(self):
                await asyncio.sleep(1)
                async with self:
                    self.counter += 1
    """

    def __init__(
        self,
        state_instance: BaseState,
        parent_state_proxy: Optional["StateProxy"] = None,
    ):
        """Create a proxy for a state instance.

        If `get_state` is used on a StateProxy, the resulting state will be
        linked to the given state via parent_state_proxy. The first state in the
        chain is the state that initiated the background task.

        Args:
            state_instance: The state instance to proxy.
            parent_state_proxy: The parent state proxy, for linked mutability and context tracking.
        """
        super().__init__(state_instance)
        # compile is not relevant to backend logic
        self._self_app = prerequisites.get_and_validate_app().app
        self._self_substate_path = tuple(state_instance.get_full_name().split("."))
        self._self_actx = None
        self._self_mutable = False
        self._self_actx_lock = asyncio.Lock()
        self._self_actx_lock_holder = None
        self._self_parent_state_proxy = parent_state_proxy

    def _is_mutable(self) -> bool:
        """Check if the state is mutable.

        Returns:
            Whether the state is mutable.
        """
        if self._self_parent_state_proxy is not None:
            return self._self_parent_state_proxy._is_mutable() or self._self_mutable
        return self._self_mutable

    async def __aenter__(self) -> StateProxy:
        """Enter the async context manager protocol.

        Sets mutability to True and enters the `App.modify_state` async context,
        which refreshes the state from state_manager and holds the lock for the
        given state token until exiting the context.

        Background tasks should avoid blocking calls while inside the context.

        Returns:
            This StateProxy instance in mutable mode.

        Raises:
            ImmutableStateError: If the state is already mutable.
        """
        if self._self_parent_state_proxy is not None:
            parent_state = (
                await self._self_parent_state_proxy.__aenter__()
            ).__wrapped__
            super().__setattr__(
                "__wrapped__",
                await parent_state.get_state(
                    State.get_class_substate(self._self_substate_path)
                ),
            )
            return self
        current_task = asyncio.current_task()
        if (
            self._self_actx_lock.locked()
            and current_task == self._self_actx_lock_holder
        ):
            raise ImmutableStateError(
                "The state is already mutable. Do not nest `async with self` blocks."
            )
        await self._self_actx_lock.acquire()
        self._self_actx_lock_holder = current_task
        self._self_actx = self._self_app.modify_state(
            token=_substate_key(
                self.__wrapped__.router.session.client_token,
                self._self_substate_path,
            )
        )
        mutable_state = await self._self_actx.__aenter__()
        super().__setattr__(
            "__wrapped__", mutable_state.get_substate(self._self_substate_path)
        )
        self._self_mutable = True
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Exit the async context manager protocol.

        Sets proxy mutability to False and persists any state changes.

        Args:
            exc_info: The exception info tuple.
        """
        if self._self_parent_state_proxy is not None:
            await self._self_parent_state_proxy.__aexit__(*exc_info)
            return
        if self._self_actx is None:
            return
        self._self_mutable = False
        try:
            await self._self_actx.__aexit__(*exc_info)
        finally:
            self._self_actx_lock_holder = None
            self._self_actx_lock.release()
        self._self_actx = None

    def __enter__(self):
        """Enter the regular context manager protocol.

        This is not supported for background tasks, and exists only to raise a more useful exception
        when the StateProxy is used incorrectly.

        Raises:
            TypeError: always, because only async contextmanager protocol is supported.
        """
        raise TypeError("Background task must use `async with self` to modify state.")

    def __exit__(self, *exc_info: Any) -> None:
        """Exit the regular context manager protocol.

        Args:
            exc_info: The exception info tuple.
        """
        pass

    def __getattr__(self, name: str) -> Any:
        """Get the attribute from the underlying state instance.

        Args:
            name: The name of the attribute.

        Returns:
            The value of the attribute.

        Raises:
            ImmutableStateError: If the state is not in mutable mode.
        """
        if name in ["substates", "parent_state"] and not self._is_mutable():
            raise ImmutableStateError(
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
        value = super().__getattr__(name)
        if not name.startswith("_self_") and isinstance(value, MutableProxy):
            # ensure mutations to these containers are blocked unless proxy is _mutable
            return ImmutableMutableProxy(
                wrapped=value.__wrapped__,
                state=self,
                field_name=value._self_field_name,
            )
        if isinstance(value, functools.partial) and value.args[0] is self.__wrapped__:
            # Rebind event handler to the proxy instance
            value = functools.partial(
                value.func,
                self,
                *value.args[1:],
                **value.keywords,
            )
        if isinstance(value, MethodType) and value.__self__ is self.__wrapped__:
            # Rebind methods to the proxy instance
            value = type(value)(value.__func__, self)
        return value

    def __setattr__(self, name: str, value: Any) -> None:
        """Set the attribute on the underlying state instance.

        If the attribute is internal, set it on the proxy instance instead.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.

        Raises:
            ImmutableStateError: If the state is not in mutable mode.
        """
        if (
            name.startswith("_self_")  # wrapper attribute
            or self._is_mutable()  # lock held
            # non-persisted state attribute
            or name in self.__wrapped__.get_skip_vars()
        ):
            super().__setattr__(name, value)
            return

        raise ImmutableStateError(
            "Background task StateProxy is immutable outside of a context "
            "manager. Use `async with self` to modify state."
        )

    def get_substate(self, path: Sequence[str]) -> BaseState:
        """Only allow substate access with lock held.

        Args:
            path: The path to the substate.

        Returns:
            The substate.

        Raises:
            ImmutableStateError: If the state is not in mutable mode.
        """
        if not self._is_mutable():
            raise ImmutableStateError(
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
        return self.__wrapped__.get_substate(path)

    async def get_state(self, state_cls: Type[BaseState]) -> BaseState:
        """Get an instance of the state associated with this token.

        Args:
            state_cls: The class of the state.

        Returns:
            The state.

        Raises:
            ImmutableStateError: If the state is not in mutable mode.
        """
        if not self._is_mutable():
            raise ImmutableStateError(
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
        return type(self)(
            await self.__wrapped__.get_state(state_cls), parent_state_proxy=self
        )

    async def _as_state_update(self, *args, **kwargs) -> StateUpdate:
        """Temporarily allow mutability to access parent_state.

        Args:
            *args: The args to pass to the underlying state instance.
            **kwargs: The kwargs to pass to the underlying state instance.

        Returns:
            The state update.
        """
        original_mutable = self._self_mutable
        self._self_mutable = True
        try:
            return await self.__wrapped__._as_state_update(*args, **kwargs)
        finally:
            self._self_mutable = original_mutable


@dataclasses.dataclass(
    frozen=True,
)
class StateUpdate:
    """A state update sent to the frontend."""

    # The state delta.
    delta: Delta = dataclasses.field(default_factory=dict)

    # Events to be added to the event queue.
    events: list[Event] = dataclasses.field(default_factory=list)

    # Whether this is the final state update for the event.
    final: bool = True

    def json(self) -> str:
        """Convert the state update to a JSON string.

        Returns:
            The state update as a JSON string.
        """
        return format.json_dumps(self)


class StateManager(Base, ABC):
    """A class to manage many client states."""

    # The state class to use.
    state: Type[BaseState]

    @classmethod
    def create(cls, state: Type[BaseState]):
        """Create a new state manager.

        Args:
            state: The state class to use.

        Raises:
            InvalidStateManagerModeError: If the state manager mode is invalid.

        Returns:
            The state manager (either disk, memory or redis).
        """
        config = get_config()
        if prerequisites.parse_redis_url() is not None:
            config.state_manager_mode = constants.StateManagerMode.REDIS
        if config.state_manager_mode == constants.StateManagerMode.MEMORY:
            return StateManagerMemory(state=state)
        if config.state_manager_mode == constants.StateManagerMode.DISK:
            return StateManagerDisk(state=state)
        if config.state_manager_mode == constants.StateManagerMode.REDIS:
            redis = prerequisites.get_redis()
            if redis is not None:
                # make sure expiration values are obtained only from the config object on creation
                return StateManagerRedis(
                    state=state,
                    redis=redis,
                    token_expiration=config.redis_token_expiration,
                    lock_expiration=config.redis_lock_expiration,
                    lock_warning_threshold=config.redis_lock_warning_threshold,
                )
        raise InvalidStateManagerModeError(
            f"Expected one of: DISK, MEMORY, REDIS, got {config.state_manager_mode}"
        )

    @abstractmethod
    async def get_state(self, token: str) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        pass

    @abstractmethod
    async def set_state(self, token: str, state: BaseState):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        pass

    @abstractmethod
    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.

        Yields:
            The state for the token.
        """
        yield self.state()


class StateManagerMemory(StateManager):
    """A state manager that stores states in memory."""

    # The mapping of client ids to states.
    states: dict[str, BaseState] = {}

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock = asyncio.Lock()

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = pydantic.PrivateAttr({})

    class Config:  # pyright: ignore [reportIncompatibleVariableOverride]
        """The Pydantic config."""

        fields = {
            "_states_locks": {"exclude": True},
        }

    @override
    async def get_state(self, token: str) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        # Memory state manager ignores the substate suffix and always returns the top-level state.
        token = _split_substate_key(token)[0]
        if token not in self.states:
            self.states[token] = self.state(_reflex_internal_init=True)
        return self.states[token]

    @override
    async def set_state(self, token: str, state: BaseState):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        pass

    @override
    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.

        Yields:
            The state for the token.
        """
        # Memory state manager ignores the substate suffix and always returns the top-level state.
        token = _split_substate_key(token)[0]
        if token not in self._states_locks:
            async with self._state_manager_lock:
                if token not in self._states_locks:
                    self._states_locks[token] = asyncio.Lock()

        async with self._states_locks[token]:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state)


def _default_token_expiration() -> int:
    """Get the default token expiration time.

    Returns:
        The default token expiration time.
    """
    return get_config().redis_token_expiration


def _serialize_type(type_: Any) -> str:
    """Serialize a type.

    Args:
        type_: The type to serialize.

    Returns:
        The serialized type.
    """
    if not inspect.isclass(type_):
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


def reset_disk_state_manager():
    """Reset the disk state manager."""
    states_directory = prerequisites.get_states_dir()
    if states_directory.exists():
        for path in states_directory.iterdir():
            path.unlink()


class StateManagerDisk(StateManager):
    """A state manager that stores states in memory."""

    # The mapping of client ids to states.
    states: dict[str, BaseState] = {}

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock = asyncio.Lock()

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = pydantic.PrivateAttr({})

    # The token expiration time (s).
    token_expiration: int = pydantic.Field(default_factory=_default_token_expiration)

    class Config:  # pyright: ignore [reportIncompatibleVariableOverride]
        """The Pydantic config."""

        fields = {
            "_states_locks": {"exclude": True},
        }
        keep_untouched = (functools.cached_property,)

    def __init__(self, state: Type[BaseState]):
        """Create a new state manager.

        Args:
            state: The state class to use.
        """
        super().__init__(state=state)

        path_ops.mkdir(self.states_directory)

        self._purge_expired_states()

    @functools.cached_property
    def states_directory(self) -> Path:
        """Get the states directory.

        Returns:
            The states directory.
        """
        return prerequisites.get_states_dir()

    def _purge_expired_states(self):
        """Purge expired states from the disk."""
        import time

        for path in path_ops.ls(self.states_directory):
            # check path is a pickle file
            if path.suffix != ".pkl":
                continue

            # load last edited field from file
            last_edited = path.stat().st_mtime

            # check if the file is older than the token expiration time
            if time.time() - last_edited > self.token_expiration:
                # remove the file
                path.unlink()

    def token_path(self, token: str) -> Path:
        """Get the path for a token.

        Args:
            token: The token to get the path for.

        Returns:
            The path for the token.
        """
        return (
            self.states_directory / f"{md5(token.encode()).hexdigest()}.pkl"
        ).absolute()

    async def load_state(self, token: str) -> BaseState | None:
        """Load a state object based on the provided token.

        Args:
            token: The token used to identify the state object.

        Returns:
            The loaded state object or None.
        """
        token_path = self.token_path(token)

        if token_path.exists():
            try:
                with token_path.open(mode="rb") as file:
                    return BaseState._deserialize(fp=file)
            except Exception:
                pass

    async def populate_substates(
        self, client_token: str, state: BaseState, root_state: BaseState
    ):
        """Populate the substates of a state object.

        Args:
            client_token: The client token.
            state: The state object to populate.
            root_state: The root state object.
        """
        for substate in state.get_substates():
            substate_token = _substate_key(client_token, substate)

            fresh_instance = await root_state.get_state(substate)
            instance = await self.load_state(substate_token)
            if instance is not None:
                # Ensure all substates exist, even if they weren't serialized previously.
                instance.substates = fresh_instance.substates
            else:
                instance = fresh_instance
            state.substates[substate.get_name()] = instance
            instance.parent_state = state

            await self.populate_substates(client_token, instance, root_state)

    @override
    async def get_state(
        self,
        token: str,
    ) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        client_token = _split_substate_key(token)[0]
        root_state = self.states.get(client_token)
        if root_state is not None:
            # Retrieved state from memory.
            return root_state

        # Deserialize root state from disk.
        root_state = await self.load_state(_substate_key(client_token, self.state))
        # Create a new root state tree with all substates instantiated.
        fresh_root_state = self.state(_reflex_internal_init=True)
        if root_state is None:
            root_state = fresh_root_state
        else:
            # Ensure all substates exist, even if they were not serialized previously.
            root_state.substates = fresh_root_state.substates
        self.states[client_token] = root_state
        await self.populate_substates(client_token, root_state, root_state)
        return root_state

    async def set_state_for_substate(self, client_token: str, substate: BaseState):
        """Set the state for a substate.

        Args:
            client_token: The client token.
            substate: The substate to set.
        """
        substate_token = _substate_key(client_token, substate)

        if substate._get_was_touched():
            substate._was_touched = False  # Reset the touched flag after serializing.
            pickle_state = substate._serialize()
            if pickle_state:
                if not self.states_directory.exists():
                    self.states_directory.mkdir(parents=True, exist_ok=True)
                self.token_path(substate_token).write_bytes(pickle_state)

        for substate_substate in substate.substates.values():
            await self.set_state_for_substate(client_token, substate_substate)

    @override
    async def set_state(self, token: str, state: BaseState):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        client_token, substate = _split_substate_key(token)
        await self.set_state_for_substate(client_token, state)

    @override
    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.

        Yields:
            The state for the token.
        """
        # Memory state manager ignores the substate suffix and always returns the top-level state.
        client_token, substate = _split_substate_key(token)
        if client_token not in self._states_locks:
            async with self._state_manager_lock:
                if client_token not in self._states_locks:
                    self._states_locks[client_token] = asyncio.Lock()

        async with self._states_locks[client_token]:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state)


def _default_lock_expiration() -> int:
    """Get the default lock expiration time.

    Returns:
        The default lock expiration time.
    """
    return get_config().redis_lock_expiration


def _default_lock_warning_threshold() -> int:
    """Get the default lock warning threshold.

    Returns:
        The default lock warning threshold.
    """
    return get_config().redis_lock_warning_threshold


class StateManagerRedis(StateManager):
    """A state manager that stores states in redis."""

    # The redis client to use.
    redis: Redis

    # The token expiration time (s).
    token_expiration: int = pydantic.Field(default_factory=_default_token_expiration)

    # The maximum time to hold a lock (ms).
    lock_expiration: int = pydantic.Field(default_factory=_default_lock_expiration)

    # The maximum time to hold a lock (ms) before warning.
    lock_warning_threshold: int = pydantic.Field(
        default_factory=_default_lock_warning_threshold
    )

    # The keyspace subscription string when redis is waiting for lock to be released.
    _redis_notify_keyspace_events: str = (
        "K"  # Enable keyspace notifications (target a particular key)
        "g"  # For generic commands (DEL, EXPIRE, etc)
        "x"  # For expired events
        "e"  # For evicted events (i.e. maxmemory exceeded)
    )

    # These events indicate that a lock is no longer held.
    _redis_keyspace_lock_release_events: set[bytes] = {
        b"del",
        b"expire",
        b"expired",
        b"evicted",
    }

    # Whether keyspace notifications have been enabled.
    _redis_notify_keyspace_events_enabled: bool = False

    # The logical database number used by the redis client.
    _redis_db: int = 0

    def _get_required_state_classes(
        self,
        target_state_cls: Type[BaseState],
        subclasses: bool = False,
        required_state_classes: set[Type[BaseState]] | None = None,
    ) -> set[Type[BaseState]]:
        """Recursively determine which states are required to fetch the target state.

        This will always include potentially dirty substates that depend on vars
        in the target_state_cls.

        Args:
            target_state_cls: The target state class being fetched.
            subclasses: Whether to include subclasses of the target state.
            required_state_classes: Recursive argument tracking state classes that have already been seen.

        Returns:
            The set of state classes required to fetch the target state.
        """
        if required_state_classes is None:
            required_state_classes = set()
        # Get the substates if requested.
        if subclasses:
            for substate in target_state_cls.get_substates():
                self._get_required_state_classes(
                    substate,
                    subclasses=True,
                    required_state_classes=required_state_classes,
                )
        if target_state_cls in required_state_classes:
            return required_state_classes
        required_state_classes.add(target_state_cls)

        # Get dependent substates.
        for pd_substates in target_state_cls._get_potentially_dirty_states():
            self._get_required_state_classes(
                pd_substates,
                subclasses=False,
                required_state_classes=required_state_classes,
            )

        # Get the parent state if it exists.
        if parent_state := target_state_cls.get_parent_state():
            self._get_required_state_classes(
                parent_state,
                subclasses=False,
                required_state_classes=required_state_classes,
            )
        return required_state_classes

    def _get_populated_states(
        self,
        target_state: BaseState,
        populated_states: dict[str, BaseState] | None = None,
    ) -> dict[str, BaseState]:
        """Recursively determine which states from target_state are already fetched.

        Args:
            target_state: The state to check for populated states.
            populated_states: Recursive argument tracking states seen in previous calls.

        Returns:
            A dictionary of state full name to state instance.
        """
        if populated_states is None:
            populated_states = {}
        if target_state.get_full_name() in populated_states:
            return populated_states
        populated_states[target_state.get_full_name()] = target_state
        for substate in target_state.substates.values():
            self._get_populated_states(substate, populated_states=populated_states)
        if target_state.parent_state is not None:
            self._get_populated_states(
                target_state.parent_state, populated_states=populated_states
            )
        return populated_states

    @override
    async def get_state(
        self,
        token: str,
        top_level: bool = True,
        for_state_instance: BaseState | None = None,
    ) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.
            top_level: If true, return an instance of the top-level state (self.state).
            for_state_instance: If provided, attach the requested states to this existing state tree.

        Returns:
            The state for the token.

        Raises:
            RuntimeError: when the state_cls is not specified in the token, or when the parent state for a
                requested state was not fetched.
        """
        # Split the actual token from the fully qualified substate name.
        token, state_path = _split_substate_key(token)
        if state_path:
            # Get the State class associated with the given path.
            state_cls = self.state.get_class_substate(state_path)
        else:
            raise RuntimeError(
                f"StateManagerRedis requires token to be specified in the form of {{token}}_{{state_full_name}}, but got {token}"
            )

        # Determine which states we already have.
        flat_state_tree: dict[str, BaseState] = (
            self._get_populated_states(for_state_instance) if for_state_instance else {}
        )

        # Determine which states from the tree need to be fetched.
        required_state_classes = sorted(
            self._get_required_state_classes(state_cls, subclasses=True)
            - {type(s) for s in flat_state_tree.values()},
            key=lambda x: x.get_full_name(),
        )

        redis_pipeline = self.redis.pipeline()
        for state_cls in required_state_classes:
            redis_pipeline.get(_substate_key(token, state_cls))

        for state_cls, redis_state in zip(
            required_state_classes,
            await redis_pipeline.execute(),
            strict=False,
        ):
            state = None

            if redis_state is not None:
                # Deserialize the substate.
                with contextlib.suppress(StateSchemaMismatchError):
                    state = BaseState._deserialize(data=redis_state)
            if state is None:
                # Key didn't exist or schema mismatch so create a new instance for this token.
                state = state_cls(
                    init_substates=False,
                    _reflex_internal_init=True,
                )
            flat_state_tree[state.get_full_name()] = state
            if state.get_parent_state() is not None:
                parent_state_name, _dot, state_name = state.get_full_name().rpartition(
                    "."
                )
                parent_state = flat_state_tree.get(parent_state_name)
                if parent_state is None:
                    raise RuntimeError(
                        f"Parent state for {state.get_full_name()} was not found "
                        "in the state tree, but should have already been fetched. "
                        "This is a bug",
                    )
                parent_state.substates[state_name] = state
                state.parent_state = parent_state

        # To retain compatibility with previous implementation, by default, we return
        # the top-level state which should always be fetched or already cached.
        if top_level:
            return flat_state_tree[self.state.get_full_name()]
        return flat_state_tree[state_cls.get_full_name()]

    @override
    async def set_state(
        self,
        token: str,
        state: BaseState,
        lock_id: bytes | None = None,
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            lock_id: If provided, the lock_key must be set to this value to set the state.

        Raises:
            LockExpiredError: If lock_id is provided and the lock for the token is not held by that ID.
            RuntimeError: If the state instance doesn't match the state name in the token.
        """
        # Check that we're holding the lock.
        if (
            lock_id is not None
            and await self.redis.get(self._lock_key(token)) != lock_id
        ):
            raise LockExpiredError(
                f"Lock expired for token {token} while processing. Consider increasing "
                f"`app.state_manager.lock_expiration` (currently {self.lock_expiration}) "
                "or use `@rx.event(background=True)` decorator for long-running tasks."
            )
        elif lock_id is not None:
            time_taken = self.lock_expiration / 1000 - (
                await self.redis.ttl(self._lock_key(token))
            )
            if time_taken > self.lock_warning_threshold / 1000:
                console.warn(
                    f"Lock for token {token} was held too long {time_taken=}s, "
                    f"use `@rx.event(background=True)` decorator for long-running tasks.",
                    dedupe=True,
                )

        client_token, substate_name = _split_substate_key(token)
        # If the substate name on the token doesn't match the instance name, it cannot have a parent.
        if state.parent_state is not None and state.get_full_name() != substate_name:
            raise RuntimeError(
                f"Cannot `set_state` with mismatching token {token} and substate {state.get_full_name()}."
            )

        # Recursively set_state on all known substates.
        tasks = [
            asyncio.create_task(
                self.set_state(
                    _substate_key(client_token, substate),
                    substate,
                    lock_id,
                )
            )
            for substate in state.substates.values()
        ]
        # Persist only the given state (parents or substates are excluded by BaseState.__getstate__).
        if state._get_was_touched():
            pickle_state = state._serialize()
            if pickle_state:
                await self.redis.set(
                    _substate_key(client_token, state),
                    pickle_state,
                    ex=self.token_expiration,
                )

        # Wait for substates to be persisted.
        for t in tasks:
            await t

    @override
    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.

        Yields:
            The state for the token.
        """
        async with self._lock(token) as lock_id:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state, lock_id)

    @validator("lock_warning_threshold")
    @classmethod
    def validate_lock_warning_threshold(
        cls, lock_warning_threshold: int, values: dict[str, int]
    ):
        """Validate the lock warning threshold.

        Args:
            lock_warning_threshold: The lock warning threshold.
            values: The validated attributes.

        Returns:
            The lock warning threshold.

        Raises:
            InvalidLockWarningThresholdError: If the lock warning threshold is invalid.
        """
        if lock_warning_threshold >= (lock_expiration := values["lock_expiration"]):
            raise InvalidLockWarningThresholdError(
                f"The lock warning threshold({lock_warning_threshold}) must be less than the lock expiration time({lock_expiration})."
            )
        return lock_warning_threshold

    @staticmethod
    def _lock_key(token: str) -> bytes:
        """Get the redis key for a token's lock.

        Args:
            token: The token to get the lock key for.

        Returns:
            The redis lock key for the token.
        """
        # All substates share the same lock domain, so ignore any substate path suffix.
        client_token = _split_substate_key(token)[0]
        return f"{client_token}_lock".encode()

    async def _try_get_lock(self, lock_key: bytes, lock_id: bytes) -> bool | None:
        """Try to get a redis lock for a token.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.

        Returns:
            True if the lock was obtained.
        """
        return await self.redis.set(
            lock_key,
            lock_id,
            px=self.lock_expiration,
            nx=True,  # only set if it doesn't exist
        )

    async def _get_pubsub_message(
        self, pubsub: PubSub, timeout: float | None = None
    ) -> None:
        """Get lock release events from the pubsub.

        Args:
            pubsub: The pubsub to get a message from.
            timeout: Remaining time to wait for a message.

        Returns:
            The message.
        """
        if timeout is None:
            timeout = self.lock_expiration / 1000.0

        started = time.time()
        message = await pubsub.get_message(
            ignore_subscribe_messages=True,
            timeout=timeout,
        )
        if (
            message is None
            or message["data"] not in self._redis_keyspace_lock_release_events
        ):
            remaining = timeout - (time.time() - started)
            if remaining <= 0:
                return
            await self._get_pubsub_message(pubsub, timeout=remaining)

    async def _enable_keyspace_notifications(self):
        """Enable keyspace notifications for the redis server.

        Raises:
            ResponseError: when the keyspace config cannot be set.
        """
        if self._redis_notify_keyspace_events_enabled:
            return
        # Find out which logical database index is being used.
        self._redis_db = self.redis.get_connection_kwargs().get("db", self._redis_db)

        try:
            await self.redis.config_set(
                "notify-keyspace-events",
                self._redis_notify_keyspace_events,
            )
        except ResponseError:
            # Some redis servers only allow out-of-band configuration, so ignore errors here.
            if not environment.REFLEX_IGNORE_REDIS_CONFIG_ERROR.get():
                raise
        self._redis_notify_keyspace_events_enabled = True

    async def _wait_lock(self, lock_key: bytes, lock_id: bytes) -> None:
        """Wait for a redis lock to be released via pubsub.

        Coroutine will not return until the lock is obtained.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.
        """
        # Enable keyspace notifications for the lock key, so we know when it is available.
        await self._enable_keyspace_notifications()
        lock_key_channel = f"__keyspace@{self._redis_db}__:{lock_key.decode()}"
        async with self.redis.pubsub() as pubsub:
            await pubsub.psubscribe(lock_key_channel)
            # wait for the lock to be released
            while True:
                # fast path
                if await self._try_get_lock(lock_key, lock_id):
                    return
                # wait for lock events
                await self._get_pubsub_message(pubsub)

    @contextlib.asynccontextmanager
    async def _lock(self, token: str):
        """Obtain a redis lock for a token.

        Args:
            token: The token to obtain a lock for.

        Yields:
            The ID of the lock (to be passed to set_state).

        Raises:
            LockExpiredError: If the lock has expired while processing the event.
        """
        lock_key = self._lock_key(token)
        lock_id = uuid.uuid4().hex.encode()

        if not await self._try_get_lock(lock_key, lock_id):
            # Missed the fast-path to get lock, subscribe for lock delete/expire events
            await self._wait_lock(lock_key, lock_id)
        state_is_locked = True

        try:
            yield lock_id
        except LockExpiredError:
            state_is_locked = False
            raise
        finally:
            if state_is_locked:
                # only delete our lock
                await self.redis.delete(lock_key)

    async def close(self):
        """Explicitly close the redis connection and connection_pool.

        It is necessary in testing scenarios to close between asyncio test cases
        to avoid having lingering redis connections associated with event loops
        that will be closed (each test case uses its own event loop).

        Note: Connections will be automatically reopened when needed.
        """
        await self.redis.aclose(close_connection_pool=True)


def get_state_manager() -> StateManager:
    """Get the state manager for the app that is currently running.

    Returns:
        The state manager.
    """
    return prerequisites.get_and_validate_app().app.state_manager


class MutableProxy(wrapt.ObjectProxy):
    """A proxy for a mutable object that tracks changes."""

    # Hint for finding the base class of the proxy.
    __base_proxy__ = "MutableProxy"

    # Methods on wrapped objects which should mark the state as dirty.
    __mark_dirty_attrs__ = {
        "add",
        "append",
        "clear",
        "difference_update",
        "discard",
        "extend",
        "insert",
        "intersection_update",
        "pop",
        "popitem",
        "remove",
        "reverse",
        "setdefault",
        "sort",
        "symmetric_difference_update",
        "update",
    }

    # Methods on wrapped objects might return mutable objects that should be tracked.
    __wrap_mutable_attrs__ = {
        "get",
        "setdefault",
    }

    # These internal attributes on rx.Base should NOT be wrapped in a MutableProxy.
    __never_wrap_base_attrs__ = set(Base.__dict__) - {"set"} | set(
        pydantic.BaseModel.__dict__
    )

    # These types will be wrapped in MutableProxy
    __mutable_types__ = (
        list,
        dict,
        set,
        Base,
        DeclarativeBase,
        BaseModelV2,
        BaseModelV1,
    )

    # Dynamically generated classes for tracking dataclass mutations.
    __dataclass_proxies__: dict[type, type] = {}

    def __new__(cls, wrapped: Any, *args, **kwargs) -> MutableProxy:
        """Create a proxy instance for a mutable object that tracks changes.

        Args:
            wrapped: The object to proxy.
            *args: Other args passed to MutableProxy (ignored).
            **kwargs: Other kwargs passed to MutableProxy (ignored).

        Returns:
            The proxy instance.
        """
        if dataclasses.is_dataclass(wrapped):
            wrapped_cls = type(wrapped)
            wrapper_cls_name = wrapped_cls.__name__ + cls.__name__
            # Find the associated class
            if wrapper_cls_name not in cls.__dataclass_proxies__:
                # Create a new class that has the __dataclass_fields__ defined
                cls.__dataclass_proxies__[wrapper_cls_name] = type(
                    wrapper_cls_name,
                    (cls,),
                    {
                        dataclasses._FIELDS: getattr(  # pyright: ignore [reportAttributeAccessIssue]
                            wrapped_cls,
                            dataclasses._FIELDS,  # pyright: ignore [reportAttributeAccessIssue]
                        ),
                    },
                )
            cls = cls.__dataclass_proxies__[wrapper_cls_name]
        return super().__new__(cls)

    def __init__(self, wrapped: Any, state: BaseState, field_name: str):
        """Create a proxy for a mutable object that tracks changes.

        Args:
            wrapped: The object to proxy.
            state: The state to mark dirty when the object is changed.
            field_name: The name of the field on the state associated with the
                wrapped object.
        """
        super().__init__(wrapped)
        self._self_state = state
        self._self_field_name = field_name

    def __repr__(self) -> str:
        """Get the representation of the wrapped object.

        Returns:
            The representation of the wrapped object.
        """
        return f"{type(self).__name__}({self.__wrapped__})"

    def _mark_dirty(
        self,
        wrapped: Callable | None = None,
        instance: BaseState | None = None,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> Any:
        """Mark the state as dirty, then call a wrapped function.

        Intended for use with `FunctionWrapper` from the `wrapt` library.

        Args:
            wrapped: The wrapped function.
            instance: The instance of the wrapped function.
            args: The args for the wrapped function.
            kwargs: The kwargs for the wrapped function.

        Returns:
            The result of the wrapped function.
        """
        self._self_state.dirty_vars.add(self._self_field_name)
        self._self_state._mark_dirty()
        if wrapped is not None:
            return wrapped(*args, **(kwargs or {}))

    @classmethod
    def _is_mutable_type(cls, value: Any) -> bool:
        """Check if a value is of a mutable type and should be wrapped.

        Args:
            value: The value to check.

        Returns:
            Whether the value is of a mutable type.
        """
        return isinstance(value, cls.__mutable_types__) or (
            dataclasses.is_dataclass(value) and not isinstance(value, Var)
        )

    @staticmethod
    def _is_called_from_dataclasses_internal() -> bool:
        """Check if the current function is called from dataclasses helper.

        Returns:
            Whether the current function is called from dataclasses internal code.
        """
        # Walk up the stack a bit to see if we are called from dataclasses
        # internal code, for example `asdict` or `astuple`.
        frame = inspect.currentframe()
        for _ in range(5):
            # Why not `inspect.stack()` -- this is much faster!
            if not (frame := frame and frame.f_back):
                break
            if inspect.getfile(frame) == dataclasses.__file__:
                return True
        return False

    def _wrap_recursive(self, value: Any) -> Any:
        """Wrap a value recursively if it is mutable.

        Args:
            value: The value to wrap.

        Returns:
            The wrapped value.
        """
        # When called from dataclasses internal code, return the unwrapped value
        if self._is_called_from_dataclasses_internal():
            return value
        # Recursively wrap mutable types, but do not re-wrap MutableProxy instances.
        if self._is_mutable_type(value) and not isinstance(value, MutableProxy):
            base_cls = globals()[self.__base_proxy__]
            return base_cls(
                wrapped=value,
                state=self._self_state,
                field_name=self._self_field_name,
            )
        return value

    def _wrap_recursive_decorator(
        self, wrapped: Callable, instance: BaseState, args: list, kwargs: dict
    ) -> Any:
        """Wrap a function that returns a possibly mutable value.

        Intended for use with `FunctionWrapper` from the `wrapt` library.

        Args:
            wrapped: The wrapped function.
            instance: The instance of the wrapped function.
            args: The args for the wrapped function.
            kwargs: The kwargs for the wrapped function.

        Returns:
            The result of the wrapped function (possibly wrapped in a MutableProxy).
        """
        return self._wrap_recursive(wrapped(*args, **kwargs))

    def __getattr__(self, __name: str) -> Any:
        """Get the attribute on the proxied object and return a proxy if mutable.

        Args:
            __name: The name of the attribute.

        Returns:
            The attribute value.
        """
        value = super().__getattr__(__name)

        if callable(value):
            if __name in self.__mark_dirty_attrs__:
                # Wrap special callables, like "append", which should mark state dirty.
                value = wrapt.FunctionWrapper(value, self._mark_dirty)

            if __name in self.__wrap_mutable_attrs__:
                # Wrap methods that may return mutable objects tied to the state.
                value = wrapt.FunctionWrapper(
                    value,
                    self._wrap_recursive_decorator,
                )

            if (
                isinstance(self.__wrapped__, Base)
                and __name not in self.__never_wrap_base_attrs__
                and hasattr(value, "__func__")
            ):
                # Wrap methods called on Base subclasses, which might do _anything_
                return wrapt.FunctionWrapper(
                    functools.partial(value.__func__, self),  # pyright: ignore [reportFunctionMemberAccess]
                    self._wrap_recursive_decorator,
                )

        if self._is_mutable_type(value) and __name not in (
            "__wrapped__",
            "_self_state",
        ):
            # Recursively wrap mutable attribute values retrieved through this proxy.
            return self._wrap_recursive(value)

        return value

    def __getitem__(self, key: Any) -> Any:
        """Get the item on the proxied object and return a proxy if mutable.

        Args:
            key: The key of the item.

        Returns:
            The item value.
        """
        value = super().__getitem__(key)
        # Recursively wrap mutable items retrieved through this proxy.
        return self._wrap_recursive(value)

    def __iter__(self) -> Any:
        """Iterate over the proxied object and return a proxy if mutable.

        Yields:
            Each item value (possibly wrapped in MutableProxy).
        """
        for value in super().__iter__():
            # Recursively wrap mutable items retrieved through this proxy.
            yield self._wrap_recursive(value)

    def __delattr__(self, name: str):
        """Delete the attribute on the proxied object and mark state dirty.

        Args:
            name: The name of the attribute.
        """
        self._mark_dirty(super().__delattr__, args=(name,))

    def __delitem__(self, key: str):
        """Delete the item on the proxied object and mark state dirty.

        Args:
            key: The key of the item.
        """
        self._mark_dirty(super().__delitem__, args=(key,))

    def __setitem__(self, key: str, value: Any):
        """Set the item on the proxied object and mark state dirty.

        Args:
            key: The key of the item.
            value: The value of the item.
        """
        self._mark_dirty(super().__setitem__, args=(key, value))

    def __setattr__(self, name: str, value: Any):
        """Set the attribute on the proxied object and mark state dirty.

        If the attribute starts with "_self_", then the state is NOT marked
        dirty as these are internal proxy attributes.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.
        """
        if name.startswith("_self_"):
            # Special case attributes of the proxy itself, not applied to the wrapped object.
            super().__setattr__(name, value)
            return
        self._mark_dirty(super().__setattr__, args=(name, value))

    def __copy__(self) -> Any:
        """Return a copy of the proxy.

        Returns:
            A copy of the wrapped object, unconnected to the proxy.
        """
        return copy.copy(self.__wrapped__)

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Any:
        """Return a deepcopy of the proxy.

        Args:
            memo: The memo dict to use for the deepcopy.

        Returns:
            A deepcopy of the wrapped object, unconnected to the proxy.
        """
        return copy.deepcopy(self.__wrapped__, memo=memo)

    def __reduce_ex__(self, protocol_version: SupportsIndex):
        """Get the state for redis serialization.

        This method is called by cloudpickle to serialize the object.

        It explicitly serializes the wrapped object, stripping off the mutable proxy.

        Args:
            protocol_version: The protocol version.

        Returns:
            Tuple of (wrapped class, empty args, class __getstate__)
        """
        return self.__wrapped__.__reduce_ex__(protocol_version)


@serializer
def serialize_mutable_proxy(mp: MutableProxy):
    """Return the wrapped value of a MutableProxy.

    Args:
        mp: The MutableProxy to serialize.

    Returns:
        The wrapped object.
    """
    return mp.__wrapped__


_orig_json_encoder_default = json.JSONEncoder.default


def _json_encoder_default_wrapper(self: json.JSONEncoder, o: Any) -> Any:
    """Wrap JSONEncoder.default to handle MutableProxy objects.

    Args:
        self: the JSONEncoder instance.
        o: the object to serialize.

    Returns:
        A JSON-able object.
    """
    try:
        return o.__wrapped__
    except AttributeError:
        pass
    return _orig_json_encoder_default(self, o)


json.JSONEncoder.default = _json_encoder_default_wrapper


class ImmutableMutableProxy(MutableProxy):
    """A proxy for a mutable object that tracks changes.

    This wrapper comes from StateProxy, and will raise an exception if an attempt is made
    to modify the wrapped object when the StateProxy is immutable.
    """

    # Ensure that recursively wrapped proxies use ImmutableMutableProxy as base.
    __base_proxy__ = "ImmutableMutableProxy"

    def _mark_dirty(
        self,
        wrapped: Callable | None = None,
        instance: BaseState | None = None,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> Any:
        """Raise an exception when an attempt is made to modify the object.

        Intended for use with `FunctionWrapper` from the `wrapt` library.

        Args:
            wrapped: The wrapped function.
            instance: The instance of the wrapped function.
            args: The args for the wrapped function.
            kwargs: The kwargs for the wrapped function.

        Returns:
            The result of the wrapped function.

        Raises:
            ImmutableStateError: if the StateProxy is not mutable.
        """
        if not self._self_state._is_mutable():
            raise ImmutableStateError(
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
        return super()._mark_dirty(
            wrapped=wrapped, instance=instance, args=args, kwargs=kwargs
        )


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
    state: Type[BaseState] = State,
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
    for subclass in tuple(state.class_subclasses):
        reload_state_module(module=module, state=subclass)
        if subclass.__module__ == module and module is not None:
            all_base_state_classes.pop(subclass.get_full_name(), None)
            state.class_subclasses.remove(subclass)
            state._always_dirty_substates.discard(subclass.get_name())
            state._var_dependencies = {}
            state._init_var_dependency_dicts()
    state.get_class_substate.cache_clear()
