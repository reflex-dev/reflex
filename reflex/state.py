"""Define the reflex state specification."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import functools
import inspect
import json
import traceback
import urllib.parse
import uuid
from abc import ABC
from collections import defaultdict
from types import FunctionType
from typing import (
    Any,
    AsyncIterator,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    Union,
)

import cloudpickle
import pydantic
from redis.asyncio import Redis

from reflex import constants
from reflex.base import Base
from reflex.event import Event, EventHandler, EventSpec, fix_events, window_alert
from reflex.utils import format, prerequisites, types
from reflex.vars import BaseVar, ComputedVar, ReflexDict, ReflexList, ReflexSet, Var

Delta = Dict[str, Any]


class State(Base, ABC, extra=pydantic.Extra.allow):
    """The state of the app."""

    # A map from the var name to the var.
    vars: ClassVar[Dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[Dict[str, BaseVar]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[Dict[str, ComputedVar]] = {}

    # Vars inherited by the parent state.
    inherited_vars: ClassVar[Dict[str, Var]] = {}

    # Backend vars that are never sent to the client.
    backend_vars: ClassVar[Dict[str, Any]] = {}

    # Backend vars inherited
    inherited_backend_vars: ClassVar[Dict[str, Any]] = {}

    # The event handlers.
    event_handlers: ClassVar[Dict[str, EventHandler]] = {}

    # The parent state.
    parent_state: Optional[State] = None

    # The substates of the state.
    substates: Dict[str, State] = {}

    # The set of dirty vars.
    dirty_vars: Set[str] = set()

    # The set of dirty substates.
    dirty_substates: Set[str] = set()

    # The routing path that triggered the state
    router_data: Dict[str, Any] = {}

    # Mapping of var name to set of computed variables that depend on it
    computed_var_dependencies: Dict[str, Set[str]] = {}

    # Mapping of var name to set of substates that depend on it
    substate_var_dependencies: Dict[str, Set[str]] = {}

    # Per-instance copy of backend variable values
    _backend_vars: Dict[str, Any] = {}

    def __init__(self, *args, parent_state: State | None = None, **kwargs):
        """Initialize the state.

        Args:
            *args: The args to pass to the Pydantic init method.
            parent_state: The parent state.
            **kwargs: The kwargs to pass to the Pydantic init method.
        """
        kwargs["parent_state"] = parent_state
        super().__init__(*args, **kwargs)

        # initialize per-instance var dependency tracking
        self.computed_var_dependencies = defaultdict(set)
        self.substate_var_dependencies = defaultdict(set)

        # Setup the substates.
        for substate in self.get_substates():
            self.substates[substate.get_name()] = substate(parent_state=self)
        # Convert the event handlers to functions.
        self._init_event_handlers()

        # Initialize computed vars dependencies.
        inherited_vars = set(self.inherited_vars).union(
            set(self.inherited_backend_vars),
        )
        for cvar_name, cvar in self.computed_vars.items():
            # Add the dependencies.
            for var in cvar.deps(objclass=type(self)):
                self.computed_var_dependencies[var].add(cvar_name)
                if var in inherited_vars:
                    # track that this substate depends on its parent for this var
                    state_name = self.get_name()
                    parent_state = self.parent_state
                    while parent_state is not None and var in parent_state.vars:
                        parent_state.substate_var_dependencies[var].add(state_name)
                        state_name, parent_state = (
                            parent_state.get_name(),
                            parent_state.parent_state,
                        )

        # Create a fresh copy of the backend variables for this instance
        self._backend_vars = copy.deepcopy(self.backend_vars)

        # Initialize the mutable fields.
        self._init_mutable_fields()

    def _init_mutable_fields(self):
        """Initialize mutable fields.

        Allow mutation to dict, list, and set to be detected by the app.
        """
        for field in self.base_vars.values():
            value = getattr(self, field.name)

            if types._issubclass(field.type_, Union[List, Dict, Set]):
                value_in_rx_data = _convert_mutable_datatypes(
                    value, self._reassign_field, field.name
                )
                setattr(self, field.name, value_in_rx_data)

        for field_name, value in self._backend_vars.items():
            if isinstance(value, (list, dict, set)):
                value_in_rx_data = _convert_mutable_datatypes(
                    value, self._reassign_field, field_name
                )
                self._backend_vars[field_name] = value_in_rx_data

        self._clean()

    def _init_event_handlers(self, state: State | None = None):
        """Initialize event handlers.

        Allow event handlers to be called directly on the instance. This is
        called recursively for all parent states.

        Args:
            state: The state to initialize the event handlers on.
        """
        if state is None:
            state = self

        def no_chain_background_task(name, fn):
            call = f"{type(state or self).__name__}.{name}"
            if inspect.iscoroutinefunction(fn):

                async def _no_chain_background_task_co(*args, **kwargs):
                    raise RuntimeError(
                        f"Cannot directly call background task {name!r}, use `yield {call}` or `return {call}` instead."
                    )

                return _no_chain_background_task_co
            if inspect.isasyncgenfunction(fn):

                async def _no_chain_background_task_gen(*args, **kwargs):
                    yield
                    raise RuntimeError(
                        f"Cannot directly call background task {name!r}, use `yield {call}` or `return {call}` instead."
                    )

                return _no_chain_background_task_gen

            raise TypeError(f"{fn} is marked as a background task, but is not async.")

        # Convert the event handlers to functions.
        for name, event_handler in state.event_handlers.items():
            if event_handler.is_background:
                fn = no_chain_background_task(name, event_handler.fn)
            else:
                fn = functools.partial(event_handler.fn, self)
            fn.__module__ = event_handler.fn.__module__  # type: ignore
            fn.__qualname__ = event_handler.fn.__qualname__  # type: ignore
            setattr(self, name, fn)

        # Also allow direct calling of parent state event handlers
        if state.parent_state is not None:
            self._init_event_handlers(state.parent_state)

    def _reassign_field(self, field_name: str):
        """Reassign the given field.

        Primarily for mutation in fields of mutable data types.

        Args:
            field_name: The name of the field we want to reassign
        """
        setattr(
            self,
            field_name,
            getattr(self, field_name),
        )

    def __repr__(self) -> str:
        """Get the string representation of the state.

        Returns:
            The string representation of the state.
        """
        return f"{self.__class__.__name__}({self.dict()})"

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Do some magic for the subclass initialization.

        Args:
            **kwargs: The kwargs to pass to the pydantic init_subclass method.
        """
        super().__init_subclass__(**kwargs)
        # Event handlers should not shadow builtin state methods.
        cls._check_overridden_methods()

        # Get the parent vars.
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            cls.inherited_vars = parent_state.vars
            cls.inherited_backend_vars = parent_state.backend_vars

        cls.new_backend_vars = {
            name: value
            for name, value in cls.__dict__.items()
            if types.is_backend_variable(name)
            and name not in cls.inherited_backend_vars
            and not isinstance(value, FunctionType)
        }

        cls.backend_vars = {**cls.inherited_backend_vars, **cls.new_backend_vars}

        # Set the base and computed vars.
        cls.base_vars = {
            f.name: BaseVar(name=f.name, type_=f.outer_type_).set_state(cls)
            for f in cls.get_fields().values()
            if f.name not in cls.get_skip_vars()
        }
        cls.computed_vars = {
            v.name: v.set_state(cls)
            for v in cls.__dict__.values()
            if isinstance(v, ComputedVar)
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
            if not name.startswith("_")
            and isinstance(fn, Callable)
            and not isinstance(fn, EventHandler)
        }
        for name, fn in events.items():
            handler = EventHandler(fn=fn)
            cls.event_handlers[name] = handler
            setattr(cls, name, handler)

    @classmethod
    def _check_overridden_methods(cls):
        """Check for shadow methods and raise error if any.

        Raises:
            NameError: When an event handler shadows an inbuilt state method.
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
            raise NameError(
                f"The event handler name `{method_name}` shadows a builtin State method; use a different name instead"
            )

    @classmethod
    def get_skip_vars(cls) -> set[str]:
        """Get the vars to skip when serializing.

        Returns:
            The vars to skip when serializing.
        """
        return set(cls.inherited_vars) | {
            "parent_state",
            "substates",
            "dirty_vars",
            "dirty_substates",
            "router_data",
            "computed_var_dependencies",
            "substate_var_dependencies",
            "_backend_vars",
        }

    @classmethod
    @functools.lru_cache()
    def get_parent_state(cls) -> Type[State] | None:
        """Get the parent state.

        Returns:
            The parent state.
        """
        parent_states = [
            base
            for base in cls.__bases__
            if types._issubclass(base, State) and base is not State
        ]
        assert len(parent_states) < 2, "Only one parent state is allowed."
        return parent_states[0] if len(parent_states) == 1 else None  # type: ignore

    @classmethod
    @functools.lru_cache()
    def get_substates(cls) -> set[Type[State]]:
        """Get the substates of the state.

        Returns:
            The substates of the state.
        """
        return set(cls.__subclasses__())

    @classmethod
    @functools.lru_cache()
    def get_name(cls) -> str:
        """Get the name of the state.

        Returns:
            The name of the state.
        """
        return format.to_snake_case(cls.__name__)

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
    def get_class_substate(cls, path: Sequence[str]) -> Type[State]:
        """Get the class substate.

        Args:
            path: The path to the substate.

        Returns:
            The class substate.

        Raises:
            ValueError: If the substate is not found.
        """
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
    def _init_var(cls, prop: BaseVar):
        """Initialize a variable.

        Args:
            prop: The variable to initialize

        Raises:
            TypeError: if the variable has an incorrect type
        """
        if not types.is_valid_var_type(prop.type_):
            raise TypeError(
                "State vars must be primitive Python types, "
                "Plotly figures, Pandas dataframes, "
                "or subclasses of rx.Base. "
                f'Found var "{prop.name}" with type {prop.type_}.'
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
        var = BaseVar(name=name, type_=type_)
        var.set_state(cls)

        # add the pydantic field dynamically (must be done before _init_var)
        cls.add_field(var, default_value)

        cls._init_var(var)

        # update the internal dicts so the new variable is correctly handled
        cls.base_vars.update({name: var})
        cls.vars.update({name: var})

        # let substates know about the new variable
        for substate_class in cls.__subclasses__():
            substate_class.vars.setdefault(name, var)

    @classmethod
    def _set_var(cls, prop: BaseVar):
        """Set the var as a class member.

        Args:
            prop: The var instance to set.
        """
        setattr(cls, prop.name, prop)

    @classmethod
    def _create_setter(cls, prop: BaseVar):
        """Create a setter for the var.

        Args:
            prop: The var to create a setter for.
        """
        setter_name = prop.get_setter_name(include_state=False)
        if setter_name not in cls.__dict__:
            event_handler = EventHandler(fn=prop.get_setter())
            cls.event_handlers[setter_name] = event_handler
            setattr(cls, setter_name, event_handler)

    @classmethod
    def _set_default_value(cls, prop: BaseVar):
        """Set the default value for the var.

        Args:
            prop: The var to set the default value for.
        """
        # Get the pydantic field for the var.
        field = cls.get_fields()[prop.name]
        default_value = prop.get_default_value()
        if field.required and default_value is not None:
            field.required = False
            field.default = default_value

    @staticmethod
    def _get_base_functions() -> dict[str, FunctionType]:
        """Get all functions of the state class excluding dunder methods.

        Returns:
            The functions of rx.State class as a dict.
        """
        return {
            func[0]: func[1]
            for func in inspect.getmembers(State, predicate=inspect.isfunction)
            if not func[0].startswith("__")
        }

    def get_token(self) -> str:
        """Return the token of the client associated with this state.

        Returns:
            The token of the client.
        """
        return self.router_data.get(constants.RouteVar.CLIENT_TOKEN, "")

    def get_sid(self) -> str:
        """Return the session ID of the client associated with this state.

        Returns:
            The session ID of the client.
        """
        return self.router_data.get(constants.RouteVar.SESSION_ID, "")

    def get_headers(self) -> Dict:
        """Return the headers of the client associated with this state.

        Returns:
            The headers of the client.
        """
        return self.router_data.get(constants.RouteVar.HEADERS, {})

    def get_client_ip(self) -> str:
        """Return the IP of the client associated with this state.

        Returns:
            The IP of the client.
        """
        return self.router_data.get(constants.RouteVar.CLIENT_IP, "")

    def get_current_page(self, origin=False) -> str:
        """Obtain the path of current page from the router data.

        Args:
            origin: whether to return the base route as shown in browser

        Returns:
            The current page.
        """
        if origin:
            return self.router_data.get(constants.RouteVar.ORIGIN, "")
        else:
            return self.router_data.get(constants.RouteVar.PATH, "")

    def get_query_params(self) -> dict[str, str]:
        """Obtain the query parameters for the queried page.

        The query object contains both the URI parameters and the GET parameters.

        Returns:
            The dict of query parameters.
        """
        return self.router_data.get(constants.RouteVar.QUERY, {})

    def get_cookies(self) -> dict[str, str]:
        """Obtain the cookies of the client stored in the browser.

        Returns:
                The dict of cookies.
        """
        cookie_dict = {}
        cookies = self.get_headers().get(constants.RouteVar.COOKIE, "").split(";")

        cookie_pairs = [cookie.split("=") for cookie in cookies if cookie]

        for pair in cookie_pairs:
            key, value = pair[0].strip(), urllib.parse.unquote(pair[1].strip())
            try:
                # cast non-string values to the actual types.
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
            finally:
                cookie_dict[key] = value
        return cookie_dict

    @classmethod
    def setup_dynamic_args(cls, args: dict[str, str]):
        """Set up args for easy access in renderer.

        Args:
            args: a dict of args
        """

        def argsingle_factory(param):
            @ComputedVar
            def inner_func(self) -> str:
                return self.get_query_params().get(param, "")

            return inner_func

        def arglist_factory(param):
            @ComputedVar
            def inner_func(self) -> List:
                return self.get_query_params().get(param, [])

            return inner_func

        for param, value in args.items():
            if value == constants.RouteArgType.SINGLE:
                func = argsingle_factory(param)
            elif value == constants.RouteArgType.LIST:
                func = arglist_factory(param)
            else:
                continue
            func.fget.__name__ = param  # to allow passing as a prop # type: ignore
            cls.vars[param] = cls.computed_vars[param] = func.set_state(cls)  # type: ignore
            setattr(cls, param, func)

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

        inherited_vars = {
            **super().__getattribute__("inherited_vars"),
            **super().__getattribute__("inherited_backend_vars"),
        }
        if name in inherited_vars:
            return getattr(super().__getattribute__("parent_state"), name)
        elif name in super().__getattribute__("_backend_vars"):
            return super().__getattribute__("_backend_vars").__getitem__(name)
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any):
        """Set the attribute.

        If the attribute is inherited, set the attribute on the parent state.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.
        """
        # Set the var on the parent state.
        inherited_vars = {**self.inherited_vars, **self.inherited_backend_vars}
        if name in inherited_vars:
            setattr(self.parent_state, name, value)
            return

        # Make sure lists and dicts are converted to ReflexList, ReflexDict and ReflexSet.
        if name in (*self.base_vars, *self.backend_vars) and types._isinstance(
            value, Union[List, Dict, Set]
        ):
            value = _convert_mutable_datatypes(value, self._reassign_field, name)

        if types.is_backend_variable(name) and name != "_backend_vars":
            self._backend_vars.__setitem__(name, value)
            self.dirty_vars.add(name)
            self._mark_dirty()
            return

        # Set the attribute.
        super().__setattr__(name, value)

        # Add the var to the dirty list.
        if name in self.vars or name in self.computed_var_dependencies:
            self.dirty_vars.add(name)
            self._mark_dirty()

        # For now, handle router_data updates as a special case
        if name == constants.ROUTER_DATA:
            self.dirty_vars.add(name)
            self._mark_dirty()
            # propagate router_data updates down the state tree
            for substate in self.substates.values():
                setattr(substate, name, value)

    def reset(self):
        """Reset all the base vars to their default values."""
        # Reset the base vars.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            setattr(self, prop_name, fields[prop_name].default)

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
                setattr(self, prop_name, field.default)

        # Recursively reset the substate client storage.
        for substate in self.substates.values():
            substate._reset_client_storage()

    def get_substate(self, path: Sequence[str]) -> State | None:
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

    def _get_event_handler(
        self, event: Event
    ) -> tuple[State | StateProxy, EventHandler]:
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
            return isinstance(events, (EventHandler, EventSpec))

        if events is None or _is_valid_type(events):
            return events
        try:
            if all(_is_valid_type(e) for e in events):
                return events
        except TypeError:
            pass

        raise TypeError(
            f"Your handler {handler.fn.__qualname__} must only return/yield: None, Events or other EventHandlers referenced by their class (not using `self`)"
        )

    async def _process_event(
        self, handler: EventHandler, state: State | StateProxy, payload: Dict
    ) -> AsyncIterator[StateUpdate]:
        """Process event.

        Args:
            handler: EventHandler to process.
            state: State to process the handler.
            payload: The event payload.

        Yields:
            StateUpdate object
        """
        # Get the function to process the event.
        fn = functools.partial(handler.fn, state)

        token = self.get_token()

        def as_state_update(events, final) -> StateUpdate:
            # Fix the returned events.
            events = fix_events(self._check_valid(handler, events), token)  # type: ignore

            # Get the delta after processing the event.
            delta = self.get_delta()
            self._clean()

            return StateUpdate(
                delta=delta,
                events=events,
                final=final if not handler.is_background else True,
            )

        # Clean the state before processing the event.
        self._clean()

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
                    yield as_state_update(event, final=False)
                yield as_state_update(events=None, final=True)

            # Handle regular generators.
            elif inspect.isgenerator(events):
                try:
                    while True:
                        yield as_state_update(next(events), final=False)
                except StopIteration as si:
                    # the "return" value of the generator is not available
                    # in the loop, we must catch StopIteration to access it
                    if si.value is not None:
                        yield as_state_update(si.value, final=False)
                yield as_state_update(events=None, final=True)

            # Handle regular event chains.
            else:
                yield as_state_update(events, final=True)

        # If an error occurs, throw a window alert.
        except Exception:
            error = traceback.format_exc()
            print(error)
            yield as_state_update(
                window_alert("An error occurred. See logs for details."), True
            )

    def _always_dirty_computed_vars(self) -> set[str]:
        """The set of ComputedVars that always need to be recalculated.

        Returns:
            Set of all ComputedVar in this state where cache=False
        """
        return set(
            cvar_name
            for cvar_name, cvar in self.computed_vars.items()
            if not cvar.cache
        )

    def _mark_dirty_computed_vars(self) -> None:
        """Mark ComputedVars that need to be recalculated based on dirty_vars."""
        dirty_vars = self.dirty_vars
        while dirty_vars:
            calc_vars, dirty_vars = dirty_vars, set()
            for cvar in self._dirty_computed_vars(from_vars=calc_vars):
                self.dirty_vars.add(cvar)
                dirty_vars.add(cvar)
                actual_var = self.computed_vars.get(cvar)
                if actual_var:
                    actual_var.mark_dirty(instance=self)

    def _dirty_computed_vars(self, from_vars: set[str] | None = None) -> set[str]:
        """Determine ComputedVars that need to be recalculated based on the given vars.

        Args:
            from_vars: find ComputedVar that depend on this set of vars. If unspecified, will use the dirty_vars.

        Returns:
            Set of computed vars to include in the delta.
        """
        return set(
            cvar
            for dirty_var in from_vars or self.dirty_vars
            for cvar in self.computed_var_dependencies[dirty_var]
        )

    def get_delta(self) -> Delta:
        """Get the delta for the state.

        Returns:
            The delta for the state.
        """
        delta = {}

        # Apply dirty variables down into substates
        self.dirty_vars.update(self._always_dirty_computed_vars())
        self._mark_dirty()

        # Return the dirty vars for this instance, any cached/dependent computed vars,
        # and always dirty computed vars (cache=False)
        delta_vars = (
            self.dirty_vars.intersection(self.base_vars)
            .union(self._dirty_computed_vars())
            .union(self._always_dirty_computed_vars())
        )

        subdelta = {
            prop: getattr(self, prop)
            for prop in delta_vars
            if not types.is_backend_variable(prop)
        }
        if len(subdelta) > 0:
            delta[self.get_full_name()] = subdelta

        # Recursively find the substate deltas.
        substates = self.substates
        for substate in self.dirty_substates:
            delta.update(substates[substate].get_delta())

        # Format the delta.
        delta = format.format_state(delta)

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

        # Propagate dirty var / computed var status into substates
        substates = self.substates
        for var in self.dirty_vars:
            for substate_name in self.substate_var_dependencies[var]:
                self.dirty_substates.add(substate_name)
                substate = substates[substate_name]
                substate.dirty_vars.add(var)
                substate._mark_dirty()

    def _clean(self):
        """Reset the dirty vars."""
        # Recursively clean the substates.
        for substate in self.dirty_substates:
            self.substates[substate]._clean()

        # Clean this state.
        self.dirty_vars = set()
        self.dirty_substates = set()

    def dict(self, include_computed: bool = True, **kwargs) -> dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            include_computed: Whether to include computed vars.
            **kwargs: Kwargs to pass to the pydantic dict method.

        Returns:
            The object as a dictionary.
        """
        if include_computed:
            # Apply dirty variables down into substates to allow never-cached ComputedVar to
            # trigger recalculation of dependent vars
            self.dirty_vars.update(self._always_dirty_computed_vars())
            self._mark_dirty()

        base_vars = {
            prop_name: self.get_value(getattr(self, prop_name))
            for prop_name in self.base_vars
        }
        computed_vars = (
            {
                # Include the computed vars.
                prop_name: self.get_value(getattr(self, prop_name))
                for prop_name in self.computed_vars
            }
            if include_computed
            else {}
        )
        substate_vars = {
            k: v.dict(include_computed=include_computed, **kwargs)
            for k, v in self.substates.items()
        }
        variables = {**base_vars, **computed_vars, **substate_vars}
        return {k: variables[k] for k in sorted(variables)}


class ImmutableStateError(AttributeError):
    """Raised when a background task attempts to modify state outside of context."""

    pass


class StateProxy:
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

            @rx.background
            async def bg_increment(self):
                await asyncio.sleep(1)
                async with self:
                    self.counter += 1
    """

    __internal_attributes = set(
        ["_actx", "_app", "_mutable", "_state_instance", "_substate_path"],
    )

    def __init__(self, state_instance):
        """Create a proxy for a state instance.

        Args:
            state_instance: The state instance to proxy.
        """
        self._app = getattr(prerequisites.get_app(), constants.APP_VAR)
        self._state_instance = state_instance
        self._substate_path = state_instance.get_full_name().split(".")
        self._actx = None
        self._mutable = False

    async def __aenter__(self) -> StateProxy:
        """Enter the async context manager protocol.

        Sets mutability to True and enters the `App.modify_state` async context,
        which refreshes the state from state_manager and holds the lock for the
        given state token until exiting the context.

        Background tasks should avoid blocking calls while inside the context.

        Returns:
            This StateProxy instance in mutable mode.
        """
        self._actx = self._app.modify_state(self._state_instance.get_token())
        mutable_state = await self._actx.__aenter__()
        self._state_instance = mutable_state.get_substate(self._substate_path)
        self._mutable = True
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Exit the async context manager protocol.

        Sets proxy mutability to False and persists any state changes.

        Args:
            exc_info: The exception info tuple.
        """
        if self._actx is None:
            return
        self._mutable = False
        await self._actx.__aexit__(*exc_info)

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
        """
        return getattr(self._state_instance, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Set the attribute on the underlying state instance.

        If the attribute is internal, set it on the proxy instance instead.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.

        Raises:
            ImmutableStateError: If the state is not in mutable mode.
        """
        if name in self.__internal_attributes:
            # allow proxy internal attributes to be set
            super().__setattr__(name, value)
            return
        if not self._mutable:
            raise ImmutableStateError(
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
        setattr(self._state_instance, name, value)


class DefaultState(State):
    """The default empty state."""

    pass


class StateUpdate(Base):
    """A state update sent to the frontend."""

    # The state delta.
    delta: Delta = {}

    # Events to be added to the event queue.
    events: List[Event] = []

    # Whether this is the final state update for the event.
    final: bool = True


class LockExpiredError(Exception):
    """Raised when the state lock expires while an event is being processed."""


class StateManager(Base):
    """A class to manage many client states."""

    # The state class to use.
    state: Type[State] = DefaultState

    # The mapping of client ids to states.
    states: Dict[str, State] = {}

    # The token expiration time (s).
    token_expiration: int = constants.TOKEN_EXPIRATION

    # The maximum time to hold a lock (s).
    lock_expiration: int = constants.LOCK_EXPIRATION

    # The redis client to use.
    redis: Optional[Redis] = None

    # The keyspace subscription string when redis is waiting for lock to be released
    _redis_notify_keyspace_events: str = (
        "K"  # Enable keyspace notifications (target a particular key)
        "g"  # For generic commands (DEL, EXPIRE, etc)
        "x"  # For expired events
        "e"  # For evicted events (i.e. maxmemory exceeded)
    )

    # These events indicate that a lock is no longer held
    _redis_keyspace_lock_release_events: set[bytes] = {
        b"del",
        b"expire",
        b"expired",
        b"evicted",
    }

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = asyncio.Lock()

    # The dict of mutexes for each client
    _states_locks: Dict[str, asyncio.Lock] = {}

    def setup(self, state: Type[State]):
        """Set up the state manager.

        Args:
            state: The state class to use.
        """
        self.state = state
        self.redis = prerequisites.get_redis()

    async def get_state(self, token: str) -> State:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        if self.redis is not None:
            redis_state = await self.redis.get(token)
            if redis_state is None:
                await self.set_state(token, self.state())
                return await self.get_state(token)
            return cloudpickle.loads(redis_state)

        if token not in self.states:
            self.states[token] = self.state()
        return self.states[token]

    async def set_state(self, token: str, state: State, lock_id: bytes | None = None):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            lock_id: If provided, the lock_key must be set to this value to set the state.

        Raises:
            LockExpiredError: If lock_id is provided and the lock for the token is not held by that ID.
        """
        if self.redis is None:
            return
        if lock_id is not None:
            lock_key = f"{token}_lock".encode()
            # check that we're holding the lock
            if await self.redis.get(lock_key) != lock_id:
                raise LockExpiredError(
                    f"Lock expired for token {token} while processing. Consider increasing "
                    f"`app.state_manager.lock_expiration` (currently {self.lock_expiration}) "
                    "or use `@rx.background` decorator for long-running tasks."
                )
        await self.redis.set(token, cloudpickle.dumps(state), ex=self.token_expiration)

    @contextlib.asynccontextmanager
    async def _redis_lock(self, token: str):
        """Obtain a redis lock for a token.

        Args:
            token: The token to obtain a lock for.

        Yields:
            The ID of the lock (to be passed to set_state).

        Raises:
            RuntimeError: If redis is not configured.
            LockExpiredError: If the lock has expired while processing the event.
        """
        if self.redis is None:
            raise RuntimeError("Redis is not configured")
        lock_key = f"{token}_lock".encode()
        lock_id = uuid.uuid4().hex.encode()
        lock_key_channel = f"__keyspace@0__:{lock_key.decode()}"

        def try_get_lock():
            return self.redis.set(  # pyright: ignore [reportOptionalMemberAccess]
                lock_key,
                lock_id,
                ex=self.lock_expiration,
                nx=True,  # only set if it doesn't exist
            )

        state_is_locked = await try_get_lock()
        while not state_is_locked:
            await self.redis.config_set(
                "notify-keyspace-events", self._redis_notify_keyspace_events
            )
            async with self.redis.pubsub() as pubsub:
                await pubsub.psubscribe(lock_key_channel)
                # wait for the lock to be released
                while True:
                    if not await self.redis.exists(lock_key):
                        break  # key was removed, try to get the lock again
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=self.lock_expiration,
                    )
                    if message is None:
                        continue
                    if message["data"] in self._redis_keyspace_lock_release_events:
                        break
            state_is_locked = await try_get_lock()
        try:
            yield lock_id
        except LockExpiredError:
            state_is_locked = False
            raise
        finally:
            if state_is_locked:
                # only delete our lock
                await self.redis.delete(lock_key)

    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[State]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.

        Yields:
            The state for the token.
        """
        if self.redis is not None:
            async with self._redis_lock(token) as lock_id:
                state = await self.get_state(token)
                yield state
                await self.set_state(token, state, lock_id)
            return

        if token not in self._states_locks:
            async with self._state_manager_lock:
                if token not in self._states_locks:
                    self._states_locks[token] = asyncio.Lock()

        async with self._states_locks[token]:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state)


def _convert_mutable_datatypes(
    field_value: Any, reassign_field: Callable, field_name: str
) -> Any:
    """Recursively convert mutable data to the Rx data types.

    Note: right now only list, dict and set would be handled recursively.

    Args:
        field_value: The target field_value.
        reassign_field:
            The function to reassign the field in the parent state.
        field_name: the name of the field in the parent state

    Returns:
        The converted field_value
    """
    if isinstance(field_value, list):
        field_value = [
            _convert_mutable_datatypes(value, reassign_field, field_name)
            for value in field_value
        ]

        field_value = ReflexList(
            field_value, reassign_field=reassign_field, field_name=field_name
        )

    if isinstance(field_value, dict):
        field_value = {
            key: _convert_mutable_datatypes(value, reassign_field, field_name)
            for key, value in field_value.items()
        }
        field_value = ReflexDict(
            field_value, reassign_field=reassign_field, field_name=field_name
        )

    if isinstance(field_value, set):
        field_value = [
            _convert_mutable_datatypes(value, reassign_field, field_name)
            for value in field_value
        ]

        field_value = ReflexSet(
            field_value, reassign_field=reassign_field, field_name=field_name
        )

    return field_value


class ClientStorageBase:
    """Base class for client-side storage."""

    def options(self) -> dict[str, Any]:
        """Get the options for the storage.

        Returns:
            All set options for the storage (not None).
        """
        return {
            format.to_camel_case(k): v for k, v in vars(self).items() if v is not None
        }


class Cookie(ClientStorageBase, str):
    """Represents a state Var that is stored as a cookie in the browser."""

    name: str | None
    path: str
    max_age: int | None
    domain: str | None
    secure: bool | None
    same_site: str

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
        path: str = "/",
        max_age: int | None = None,
        domain: str | None = None,
        secure: bool | None = None,
        same_site: str = "lax",
    ):
        """Create a client-side Cookie (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use.
            name: The name of the cookie on the client side.
            path: Cookie path. Use / as the path if the cookie should be accessible on all pages.
            max_age: Relative max age of the cookie in seconds from when the client receives it.
            domain: Domain for the cookie (sub.domain.com or .allsubdomains.com).
            secure: Is the cookie only accessible through HTTPS?
            same_site: Whether the cookie is sent with third party requests.
                One of (true|false|none|lax|strict)

        Returns:
            The client-side Cookie object.

        Note: expires (absolute Date) is not supported at this time.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        inst.path = path
        inst.max_age = max_age
        inst.domain = domain
        inst.secure = secure
        inst.same_site = same_site
        return inst


class LocalStorage(ClientStorageBase, str):
    """Represents a state Var that is stored in localStorage in the browser."""

    name: str | None

    def __new__(
        cls,
        object: Any = "",
        encoding: str | None = None,
        errors: str | None = None,
        /,
        name: str | None = None,
    ) -> "LocalStorage":
        """Create a client-side localStorage (str).

        Args:
            object: The initial object.
            encoding: The encoding to use.
            errors: The error handling scheme to use.
            name: The name of the storage key on the client side.

        Returns:
            The client-side localStorage object.
        """
        if encoding or errors:
            inst = super().__new__(cls, object, encoding or "utf-8", errors or "strict")
        else:
            inst = super().__new__(cls, object)
        inst.name = name
        return inst
