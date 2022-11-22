"""Define the pynecone state specification."""
from __future__ import annotations

import asyncio
import functools
import pickle
import traceback
from abc import ABC
from typing import Any, Callable, ClassVar, Dict, List, Optional, Sequence, Set, Type

from pynecone import constants, utils
from pynecone.base import Base
from pynecone.event import Event, EventHandler, EventSpec, window_alert
from pynecone.var import BaseVar, ComputedVar, Var

Delta = Dict[str, Any]


class State(Base, ABC):
    """The state of the app."""

    # A map from the var name to the var.
    vars: ClassVar[Dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[Dict[str, BaseVar]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[Dict[str, ComputedVar]] = {}

    # vars inherited by the parent state.
    inherited_vars: ClassVar[Dict[str, Var]] = {}

    # The parent state.
    parent_state: Optional[State] = None

    # The substates of the state.
    substates: Dict[str, State] = {}

    # The set of dirty vars.
    dirty_vars: Set[str] = set()

    # The set of dirty substates.
    dirty_substates: Set[str] = set()

    def __init__(self, *args, **kwargs):
        """Initialize the state.

        Args:
            *args: The args to pass to the Pydantic init method.
            **kwargs: The kwargs to pass to the Pydantic init method.
        """
        super().__init__(*args, **kwargs)

        # Setup the substates.
        for substate in self.get_substates():
            self.substates[substate.get_name()] = substate().set(parent_state=self)

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

        # Get the parent vars.
        parent_state = cls.get_parent_state()
        if parent_state is not None:
            cls.inherited_vars = parent_state.vars

        # Set the base and computed vars.
        skip_vars = set(cls.inherited_vars) | {
            "parent_state",
            "substates",
            "dirty_vars",
            "dirty_substates",
        }
        cls.base_vars = {
            f.name: BaseVar(name=f.name, type_=f.outer_type_).set_state(cls)
            for f in cls.get_fields().values()
            if f.name not in skip_vars
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

        # Setup the base vars at the class level.
        for prop in cls.base_vars.values():
            cls._set_var(prop)
            cls._create_setter(prop)
            cls._set_default_value(prop)

        # Set up the event handlers.
        events = {
            name: fn
            for name, fn in cls.__dict__.items()
            if not name.startswith("_") and isinstance(fn, Callable)
        }
        for name, fn in events.items():
            event_handler = EventHandler(fn=fn)
            setattr(cls, name, event_handler)

    @classmethod
    @functools.lru_cache()
    def get_parent_state(cls) -> Optional[Type[State]]:
        """Get the parent state.

        Returns:
            The parent state.
        """
        parent_states = [
            base
            for base in cls.__bases__
            if utils._issubclass(base, State) and base is not State
        ]
        assert len(parent_states) < 2, "Only one parent state is allowed."
        return parent_states[0] if len(parent_states) == 1 else None  # type: ignore

    @classmethod
    @functools.lru_cache()
    def get_substates(cls) -> Set[Type[State]]:
        """Get the substates of the state.

        Returns:
            The substates of the state.
        """
        return {subclass for subclass in cls.__subclasses__()}

    @classmethod
    @functools.lru_cache()
    def get_name(cls) -> str:
        """Get the name of the state.

        Returns:
            The name of the state.
        """
        return utils.to_snake_case(cls.__name__)

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
            setattr(cls, setter_name, prop.get_setter())

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

    def __getattribute__(self, name: str) -> Any:
        """Get the attribute.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute.

        Raises:
            Exception: If the attribute is not found.
        """
        # If it is an inherited var, return from the parent state.
        if name != "inherited_vars" and name in self.inherited_vars:
            return getattr(self.parent_state, name)
        try:
            return super().__getattribute__(name)
        except Exception as e:
            # Check if the attribute is a substate.
            if name in self.substates:
                return self.substates[name]
            raise e

    def __setattr__(self, name: str, value: Any):
        """Set the attribute.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.
        """
        if name != "inherited_vars" and name in self.inherited_vars:
            setattr(self.parent_state, name, value)
            return

        # Set the attribute.
        super().__setattr__(name, value)

        # Add the var to the dirty list.
        if name in self.vars:
            self.dirty_vars.add(name)
            self.mark_dirty()

    def reset(self):
        """Reset all the base vars to their default values."""
        # Reset the base vars.
        fields = self.get_fields()
        for prop_name in self.base_vars:
            setattr(self, prop_name, fields[prop_name].default)

        # Recursively reset the substates.
        for substate in self.substates.values():
            substate.reset()

        # Clean the state.
        self.clean()

    def get_substate(self, path: Sequence[str]) -> Optional[State]:
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

    async def process(self, event: Event) -> StateUpdate:
        """Process an event.

        Args:
            event: The event to process.

        Returns:
            The state update after processing the event.
        """
        # Get the event handler.
        path = event.name.split(".")
        path, name = path[:-1], path[-1]
        substate = self.get_substate(path)
        handler = getattr(substate, name)

        # Process the event.
        fn = functools.partial(handler.fn, substate)
        try:
            if asyncio.iscoroutinefunction(fn.func):
                events = await fn(**event.payload)
            else:
                events = fn(**event.payload)
        except:
            error = traceback.format_exc()
            print(error)
            return StateUpdate(events=[window_alert(error)])

        # Fix the returned events.
        events = utils.fix_events(events, event.token)

        # Get the delta after processing the event.
        delta = self.get_delta()

        # Reset the dirty vars.
        self.clean()

        # Return the state update.
        return StateUpdate(delta=delta, events=events)

    def get_delta(self) -> Delta:
        """Get the delta for the state.

        Returns:
            The delta for the state.
        """
        delta = {}

        # Return the dirty vars, as well as all computed vars.
        subdelta = {
            prop: getattr(self, prop)
            for prop in self.dirty_vars | set(self.computed_vars.keys())
        }
        if len(subdelta) > 0:
            delta[self.get_full_name()] = subdelta

        # Recursively find the substate deltas.
        for substate in self.dirty_substates:
            delta.update(self.substates[substate].get_delta())

        # Format the delta.
        delta = utils.format_state(delta)

        # Return the delta.
        return delta

    def mark_dirty(self):
        """Mark the substate and all parent states as dirty."""
        if self.parent_state is not None:
            self.parent_state.dirty_substates.add(self.get_name())
            self.parent_state.mark_dirty()

    def clean(self):
        """Reset the dirty vars."""
        # Recursively clean the substates.
        for substate in self.dirty_substates:
            self.substates[substate].clean()

        # Clean this state.
        self.dirty_vars = set()
        self.dirty_substates = set()

    def dict(self, include_computed: bool = True, **kwargs) -> Dict[str, Any]:
        """Convert the object to a dictionary.

        Args:
            include_computed: Whether to include computed vars.
            **kwargs: Kwargs to pass to the pydantic dict method.

        Returns:
            The object as a dictionary.
        """
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
        vars = {**base_vars, **computed_vars, **substate_vars}
        return {k: vars[k] for k in sorted(vars)}


class DefaultState(State):
    """The default empty state."""

    pass


class StateUpdate(Base):
    """A state update sent to the frontend."""

    # The state delta.
    delta: Delta = {}

    # Events to be added to the event queue.
    events: List[Event] = []


class StateManager(Base):
    """A class to manage many client states."""

    # The state class to use.
    state: Type[State] = DefaultState

    # The mapping of client ids to states.
    states: Dict[str, State] = {}

    # The token expiration time (s).
    token_expiration: int = constants.TOKEN_EXPIRATION

    # The redis client to use.
    redis: Any = None

    def setup(self, state: Type[State]):
        """Set up the state manager.

        Args:
            state: The state class to use.
        """
        self.state = state
        self.redis = utils.get_redis()

    def get_state(self, token: str) -> State:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        if self.redis is not None:
            redis_state = self.redis.get(token)
            if redis_state is None:
                self.set_state(token, self.state())
                return self.get_state(token)
            return pickle.loads(redis_state)

        if token not in self.states:
            self.states[token] = self.state()
        return self.states[token]

    def set_state(self, token: str, state: State):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        if self.redis is None:
            return
        self.redis.set(token, pickle.dumps(state), ex=self.token_expiration)
