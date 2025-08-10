"""Define the reflex state specification."""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import copy
import dataclasses
import functools
import inspect
import pickle
import sys
import typing
import warnings
from collections.abc import AsyncIterator, Callable, Sequence
from hashlib import md5
from types import FunctionType
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar, TypeVar, cast, get_type_hints

import pydantic.v1 as pydantic
from pydantic import BaseModel as BaseModelV2
from pydantic.v1 import BaseModel as BaseModelV1
from pydantic.v1.fields import ModelField
from rich.markup import escape
from typing_extensions import Self

import reflex.istate.dynamic
from reflex import constants, event
from reflex.base import Base
from reflex.constants.state import FIELD_MARKER
from reflex.environment import PerformanceMode, environment
from reflex.event import (
    BACKGROUND_TASK_MARKER,
    Event,
    EventHandler,
    EventSpec,
    fix_events,
)
from reflex.istate import HANDLED_PICKLE_ERRORS, debug_failed_pickles
from reflex.istate.data import RouterData
from reflex.istate.proxy import ImmutableMutableProxy as ImmutableMutableProxy
from reflex.istate.proxy import MutableProxy, StateProxy
from reflex.istate.storage import ClientStorageBase
from reflex.model import Model
from reflex.utils import console, format, prerequisites, types
from reflex.utils.exceptions import (
    ComputedVarShadowsBaseVarsError,
    ComputedVarShadowsStateVarError,
    DynamicComponentInvalidSignatureError,
    DynamicRouteArgShadowsStateVarError,
    EventHandlerShadowsBuiltInStateMethodError,
    ReflexRuntimeError,
    SetUndefinedStateVarError,
    StateMismatchError,
    StateSchemaMismatchError,
    StateSerializationError,
    StateTooLargeError,
    UnretrievableVarValueError,
)
from reflex.utils.exceptions import ImmutableStateError as ImmutableStateError
from reflex.utils.exec import is_testing_env
from reflex.utils.monitoring import is_pyleak_enabled, monitor_loopblocks
from reflex.utils.types import _isinstance, is_union, value_inside_optional
from reflex.vars import Field, VarData, field
from reflex.vars.base import (
    ComputedVar,
    DynamicRouteVar,
    EvenMoreBasicBaseState,
    Var,
    computed_var,
    dispatch,
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


# For BaseState.get_var_value
VAR_TYPE = TypeVar("VAR_TYPE")


def _no_chain_background_task(
    state_cls: type[BaseState], name: str, fn: Callable
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

    msg = f"{fn} is marked as a background task, but is not async."
    raise TypeError(msg)


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

    state_cls: type[BaseState] = dataclasses.field(init=False)

    def __init__(self, state_cls: type[BaseState]):
        """Initialize the EventHandlerSetVar.

        Args:
            state_cls: The state class that vars will be set on.
        """
        super().__init__(
            fn=type(self).setvar,
            state_full_name=state_cls.get_full_name(),
        )
        object.__setattr__(self, "state_cls", state_cls)

    def __hash__(self):
        """Get the hash of the event handler.

        Returns:
            The hash of the event handler.
        """
        return hash(
            (
                tuple(self.event_actions.items()),
                self.fn,
                self.state_full_name,
                self.state_cls,
            )
        )

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
                msg = f"Var name must be passed as a string, got {args[0]!r}"
                raise EventHandlerValueError(msg)

            handler = getattr(self.state_cls, constants.SETTER_PREFIX + args[0], None)

            # Check that the requested Var setter exists on the State at compile time.
            if handler is None:
                msg = f"Variable `{args[0]}` cannot be set on `{self.state_cls.get_full_name()}`"
                raise AttributeError(msg)

            if asyncio.iscoroutinefunction(handler.fn):
                msg = f"Setter for {args[0]} is async, which is not supported."
                raise NotImplementedError(msg)

        return super().__call__(*args)


if TYPE_CHECKING:
    from pydantic.v1.fields import ModelField


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


class BaseState(EvenMoreBasicBaseState):
    """The state of the app."""

    # A map from the var name to the var.
    vars: ClassVar[builtins.dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[builtins.dict[str, Var]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[builtins.dict[str, ComputedVar]] = {}

    # Vars inherited by the parent state.
    inherited_vars: ClassVar[builtins.dict[str, Var]] = {}

    # Backend base vars that are never sent to the client.
    backend_vars: ClassVar[builtins.dict[str, Any]] = {}

    # Backend base vars inherited
    inherited_backend_vars: ClassVar[builtins.dict[str, Any]] = {}

    # The event handlers.
    event_handlers: ClassVar[builtins.dict[str, EventHandler]] = {}

    # A set of subclassses of this class.
    class_subclasses: ClassVar[set[type[BaseState]]] = set()

    # Mapping of var name to set of (state_full_name, var_name) that depend on it.
    _var_dependencies: ClassVar[builtins.dict[str, set[tuple[str, str]]]] = {}

    # Set of vars which always need to be recomputed
    _always_dirty_computed_vars: ClassVar[set[str]] = set()

    # Set of substates which always need to be recomputed
    _always_dirty_substates: ClassVar[set[str]] = set()

    # Set of states which might need to be recomputed if vars in this state change.
    _potentially_dirty_states: ClassVar[set[str]] = set()

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

    # The routing path that triggered the state
    router_data: builtins.dict[str, Any] = field(
        default_factory=builtins.dict, is_var=False
    )

    # Per-instance copy of backend base variable values
    _backend_vars: builtins.dict[str, Any] = field(
        default_factory=builtins.dict, is_var=False
    )

    # The router data for the current page
    router: Field[RouterData] = field(default_factory=RouterData)

    # Whether the state has ever been touched since instantiation.
    _was_touched: bool = field(default=False, is_var=False)

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
            msg = (
                "State classes should not be instantiated directly in a Reflex app. "
                "See https://reflex.dev/docs/state/ for further information."
            )
            raise ReflexRuntimeError(msg)
        if self._mixin:
            msg = f"{type(self).__name__} is a state mixin and cannot be instantiated directly."
            raise ReflexRuntimeError(msg)
        kwargs["parent_state"] = parent_state
        super().__init__(**kwargs)

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
    def _get_computed_vars(cls) -> list[tuple[str, ComputedVar]]:
        """Helper function to get all computed vars of a instance.

        Returns:
            A list of computed vars.
        """
        return [
            (name, v)
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
            **kwargs: The kwargs to pass to the pydantic init_subclass method.

        Raises:
            StateValueError: If a substate class shadows another.
        """
        from reflex.utils.exceptions import StateValueError

        super().__init_subclass__(**kwargs)

        if cls._mixin:
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
                msg = (
                    f"The substate class '{cls.get_name()}' has been defined multiple times. "
                    "Shadowing substate classes is not allowed."
                )
                raise StateValueError(msg)
            # Track this new subclass in the parent state's subclasses set.
            parent_state.class_subclasses.add(cls)

        # Get computed vars.
        computed_vars = cls._get_computed_vars()
        cls._check_overridden_computed_vars()

        new_backend_vars = {
            name: value
            for name, value in list(cls.__dict__.items())
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
            name: get_var_for_field(cls, name, f)
            for name, f in cls.get_fields().items()
            if name not in cls.get_skip_vars() and f.is_var and not name.startswith("_")
        }
        cls.computed_vars = {
            name: v._replace(merge_var_data=VarData.from_state(cls))
            for name, v in computed_vars
        }
        cls.vars = {
            **cls.inherited_vars,
            **cls.base_vars,
            **cls.computed_vars,
        }
        cls.event_handlers = {}

        # Setup the base vars at the class level.
        for name, prop in cls.base_vars.items():
            cls._init_var(name, prop)

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
                    cls.computed_vars[name] = newcv
                    cls.vars[name] = newcv
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
                console.warn(
                    f"Inline ComputedVar {f} expected type {escape(str(of_type))}, got {type(result)}. "
                    "You can specify expected type with `of_type` argument."
                )

            return result

        computed_var_func.__name__ = unique_var_name

        computed_var_func_arg = computed_var(return_type=of_type, cache=False)(
            computed_var_func
        )

        setattr(cls, unique_var_name, computed_var_func_arg)
        cls.computed_vars[unique_var_name] = computed_var_func_arg
        cls.vars[unique_var_name] = computed_var_func_arg
        cls._update_substate_inherited_vars({unique_var_name: computed_var_func_arg})
        cls._always_dirty_computed_vars.add(unique_var_name)

        return getattr(cls, unique_var_name)

    @classmethod
    def _mixins(cls) -> list[type]:
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
            msg = f"The event handler name `{method_name}` shadows a builtin State method; use a different name instead"
            raise EventHandlerShadowsBuiltInStateMethodError(msg)

    @classmethod
    def _check_overridden_basevars(cls):
        """Check for shadow base vars and raise error if any.

        Raises:
            ComputedVarShadowsBaseVarsError: When a computed var shadows a base var.
        """
        for name, computed_var_ in cls._get_computed_vars():
            if name in cls.__annotations__:
                msg = f"The computed var name `{computed_var_._js_expr}` shadows a base var in {cls.__module__}.{cls.__name__}; use a different name instead"
                raise ComputedVarShadowsBaseVarsError(msg)

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
                msg = f"The computed var name `{cv._js_expr}` shadows a var in {cls.__module__}.{cls.__name__}; use a different name instead"
                raise ComputedVarShadowsStateVarError(msg)

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
    @functools.lru_cache
    def get_parent_state(cls) -> type[BaseState] | None:
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
        return cls.class_subclasses

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
        from reflex.config import get_config
        from reflex.utils.exceptions import VarTypeError

        if not types.is_valid_var_type(prop._var_type):
            msg = (
                "State vars must be of a serializable type. "
                "Valid types include strings, numbers, booleans, lists, "
                "dictionaries, dataclasses, datetime objects, and pydantic models. "
                f'Found var "{prop._js_expr}" with type {prop._var_type}.'
            )
            raise VarTypeError(msg)
        cls._set_var(name, prop)
        if cls.is_user_defined() and get_config().state_auto_setters:
            cls._create_setter(name, prop)
        cls._set_default_value(name, prop)

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

        # add the pydantic field dynamically (must be done before _init_var)
        cls.add_field(name, var, default_value)

        cls._init_var(name, var)

        # update the internal dicts so the new variable is correctly handled
        cls.base_vars.update({name: var})
        cls.vars.update({name: var})

        # let substates know about the new variable
        for substate_class in cls.class_subclasses:
            substate_class.vars.setdefault(name, var)

        # Reinitialize dependency tracking dicts.
        cls._init_var_dependency_dicts()

    @classmethod
    def _set_var(cls, name: str, prop: Var):
        """Set the var as a class member.

        Args:
            name: The name of the var.
            prop: The var instance to set.
        """
        setattr(cls, name, prop)

    @classmethod
    def _create_event_handler(cls, fn: Any):
        """Create an event handler for the given function.

        Args:
            fn: The function to create an event handler for.

        Returns:
            The event handler.
        """
        # Check if function has stored event_actions from decorator
        event_actions = getattr(fn, "_rx_event_actions", {})

        return EventHandler(
            fn=fn, state_full_name=cls.get_full_name(), event_actions=event_actions
        )

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
        setter_name = Var._get_setter_name_for_name(name)
        if setter_name not in cls.__dict__:
            event_handler = cls._create_event_handler(prop._get_setter(name))
            cls.event_handlers[setter_name] = event_handler
            setattr(cls, setter_name, event_handler)

    @classmethod
    def _set_default_value(cls, name: str, prop: Var):
        """Set the default value for the var.

        Args:
            name: The name of the var.
            prop: The var to set the default value for.
        """
        # Get the pydantic field for the var.
        field = cls.get_fields()[name]

        if field.default is None and not types.is_optional(prop._var_type):
            # Ensure frontend uses null coalescing when accessing.
            object.__setattr__(prop, "_var_type", prop._var_type | None)

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
                return types.get_default_value_for_type(annotation_value)
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
                return self.router._page.params.get(param, "")

            inner_func.__name__ = param

            return inner_func

        def arglist_factory(param: str):
            def inner_func(self: BaseState) -> list[str]:
                return self.router._page.params.get(param, [])

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
                deps=["router"],
                _var_data=VarData.from_state(cls, param),
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
                msg = f"Dynamic route arg '{arg}' is shadowing an existing var in {cls.__module__}.{cls.__name__}"
                raise DynamicRouteArgShadowsStateVarError(msg)
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

        backend_vars = super().__getattribute__("_backend_vars") or {}
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
            msg = (
                f"The state variable '{name}' has not been defined in '{type(self).__name__}'. "
                f"All state variables must be declared before they can be set."
            )
            raise SetUndefinedStateVarError(msg)

        fields = self.get_fields()

        if (field := fields.get(name)) is not None and field.is_var:
            field_type = field.outer_type_
            if not _isinstance(value, field_type, nested=1, treat_var_as_type=False):
                console.error(
                    f"Expected field '{type(self).__name__}.{name}' to receive type '{escape(str(field_type))}',"
                    f" but got '{value}' of type '{type(value)}'."
                )

        # Set the attribute.
        object.__setattr__(self, name, value)

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

    @classmethod
    @functools.lru_cache
    def _is_client_storage(cls, prop_name_or_field: str | ModelField) -> bool:
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
        # Then get the target state and all its substates.
        state_manager = get_state_manager()
        if not isinstance(state_manager, StateManagerRedis):
            msg = (
                f"Requested state {state_cls.get_full_name()} is not cached and cannot be accessed without redis. "
                "(All states should already be available -- this is likely a bug)."
            )
            raise RuntimeError(msg)
        state_in_redis = await state_manager.get_state(
            token=_substate_key(self.router.session.client_token, state_cls),
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

        var_data = var._get_all_var_data()
        if var_data is None or not var_data.state:
            msg = f"Unable to retrieve value for {var._js_expr}: not associated with any state."
            raise UnretrievableVarValueError(msg)
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
            msg = "The value of state cannot be None when processing an event."
            raise ValueError(msg)
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

        msg = (
            f"Your handler {handler.fn.__qualname__} must only return/yield: None, Events or other EventHandlers referenced by their class (i.e. using `type(self)` or other class references)."
            f" Returned events of types {', '.join(map(str, map(type, events)))!s}."
        )
        raise TypeError(msg)

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
            delta = await state._get_resolved_delta()
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
        self,
        handler: EventHandler,
        state: BaseState | StateProxy,
        payload: builtins.dict,
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
        if is_pyleak_enabled():
            console.debug(f"Monitoring leaks for handler: {handler.fn.__qualname__}")
            fn = functools.partial(monitor_loopblocks(handler.fn), state)
        else:
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
            elif isinstance(value, list) and (hinted_args is set or hinted_args is set):
                payload[arg] = set(value)
            elif isinstance(value, list) and (
                hinted_args is tuple or hinted_args is tuple
            ):
                payload[arg] = tuple(value)
            elif isinstance(value, str) and (
                hinted_args is int or hinted_args is float
            ):
                try:
                    payload[arg] = hinted_args(value)
                except ValueError:
                    msg = f"Received a string value ({value}) for {arg} but expected a {hinted_args}"
                    raise ValueError(msg) from None
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
                actual_var = defining_state.computed_vars.get(cvar)
                if actual_var is not None:
                    actual_var.mark_dirty(instance=defining_state)
                if defining_state is self:
                    dirty_vars.add(cvar)
                else:
                    # mark dirty where this var is defined
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
            prop + FIELD_MARKER: self.get_value(prop)
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

    async def _get_resolved_delta(self) -> Delta:
        """Get the delta for the state after resolving all coroutines.

        Returns:
            The resolved delta for the state.
        """
        return await _resolve_delta(self.get_delta())

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

        Raises:
            TypeError: If the key is not a string or MutableProxy.
        """
        if isinstance(key, MutableProxy):
            # Legacy behavior from v0.7.14: handle non-string keys with deprecation warning
            from reflex.utils import console

            console.deprecate(
                feature_name="Non-string keys in get_value",
                reason="Passing non-string keys to get_value is deprecated and will no longer be supported",
                deprecation_version="0.8.0",
                removal_version="0.9.0",
            )

            return key.__wrapped__

        if isinstance(key, str):
            return getattr(self, key)

        msg = f"Invalid key type: {type(key)}. Expected str."
        raise TypeError(msg)

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

    async def __aenter__(self) -> BaseState:
        """Enter the async context manager protocol.

        This should not be used for the State class, but exists for
        type-compatibility with StateProxy.

        Raises:
            TypeError: always, because async contextmanager protocol is only supported for background task.
        """
        msg = "Only background task should use `async with self` to modify state."
        raise TypeError(msg)

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

        It explicitly removes parent_state and substates because those are serialized separately
        by the StateManagerRedis to allow for better horizontal scaling as state size increases.

        Returns:
            The state dict for serialization.
        """
        state = self.__dict__
        state = state.copy()
        if state.get("parent_state") is not None:
            # Do not serialize router data in substates (only the root state).
            state.pop("router", None)
            state.pop("router_data", None)
        # Never serialize parent_state or substates.
        state.pop("parent_state", None)
        state.pop("substates", None)
        state.pop("_was_touched", None)
        # Remove all inherited vars.
        for inherited_var_name in self.inherited_vars:
            state.pop(inherited_var_name, None)
        return state

    def __setstate__(self, state: dict[str, Any]):
        """Set the state from redis deserialization.

        This method is called by pickle to deserialize the object.

        Args:
            state: The state dict for deserialization.
        """
        state["parent_state"] = None
        state["substates"] = {}
        for key, value in state.items():
            object.__setattr__(self, key, value)

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


T_STATE = TypeVar("T_STATE", bound=BaseState)


class State(BaseState):
    """The app Base State."""

    # The hydrated bool.
    is_hydrated: bool = False

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
        from reflex.components.base.fragment import fragment

        return fragment(state_class._evaluate(lambda state: func(state)))

    return wrapper


class FrontendEventExceptionState(State):
    """Substate for handling frontend exceptions."""

    @event
    def handle_frontend_exception(self, info: str, component_stack: str) -> None:
        """Handle frontend exceptions.

        If a frontend exception handler is provided, it will be called.
        Otherwise, the default frontend exception handler will be called.

        Args:
            info: The exception information.
            component_stack: The stack trace of the component where the exception occurred.

        """
        prerequisites.get_and_validate_app().app.frontend_exception_handler(
            Exception(info)
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

    # Cannot properly annotate this as `App` due to circular import issues.
    _app_ref: ClassVar[Any] = None

    def on_load_internal(self) -> list[Event | EventSpec | event.EventCallback] | None:
        """Queue on_load handlers for the current page.

        Returns:
            The list of events to queue for on load handling.

        Raises:
            TypeError: If the app reference is not of type App.
        """
        from reflex.app import App

        app = type(self)._app_ref or prerequisites.get_and_validate_app().app
        if not isinstance(app, App):
            msg = (
                f"Expected app to be of type {App.__name__}, got {type(app).__name__}."
            )
            raise TypeError(msg)
        # Cache the app reference for subsequent calls.
        if type(self)._app_ref is None:
            type(self)._app_ref = app
        load_events = app.get_load_events(self.router._page.path)
        if not load_events:
            self.is_hydrated = True
            return None  # Fast path for navigation with no on_load events defined.
        self.is_hydrated = False
        return [
            *fix_events(
                cast(list[EventSpec | EventHandler], load_events),
                self.router.session.client_token,
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
            **kwargs: The kwargs to pass to the pydantic init_subclass method.
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
    # Reset the _app_ref of OnLoadInternalState to avoid stale references.
    if state is OnLoadInternalState:
        state._app_ref = None
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


from reflex.istate.manager import LockExpiredError as LockExpiredError  # noqa: E402
from reflex.istate.manager import StateManager as StateManager  # noqa: E402
from reflex.istate.manager import StateManagerDisk as StateManagerDisk  # noqa: E402
from reflex.istate.manager import StateManagerMemory as StateManagerMemory  # noqa: E402
from reflex.istate.manager import StateManagerRedis as StateManagerRedis  # noqa: E402
from reflex.istate.manager import get_state_manager as get_state_manager  # noqa: E402
from reflex.istate.manager import (  # noqa: E402
    reset_disk_state_manager as reset_disk_state_manager,
)
