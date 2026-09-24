"""The core of a state: its place in the state tree, dirty tracking, locking and pickling."""

from __future__ import annotations

import asyncio
import builtins
import functools
import logging
import pickle
import sys
from collections.abc import Callable, Iterable, Sequence
from hashlib import md5
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar, TypeVar

from typing_extensions import Self

from reflex_base import constants
from reflex_base.environment import PerformanceMode, environment
from reflex_base.event.context import EventContext
from reflex_base.registry import RegistrationContext
from reflex_base.state.delta import Delta, build_delta, clean_state, resolve_delta
from reflex_base.state.proxy import MutableProxy
from reflex_base.state.token import BaseStateToken
from reflex_base.utils.exceptions import (
    SetUndefinedStateVarError,
    StateSchemaMismatchError,
    StateSerializationError,
    StateTooLargeError,
)
from reflex_base.utils.format import to_snake_case
from reflex_base.vars.base import (
    ComputedVar,
    EvenMoreBasicBaseState,
    Var,
    _is_tree_state,
    field,
)

if TYPE_CHECKING:
    from reflex.state import BaseState

T_STATE = TypeVar("T_STATE", bound="BaseState")

logger = logging.getLogger(__name__)

# Errors caught during pickling of state
HANDLED_PICKLE_ERRORS = (
    pickle.PicklingError,
    AttributeError,
    IndexError,
    TypeError,
    ValueError,
)

# Entries in each pickle for workers of the previous release, which kept the
# dirty tracking and backend vars in the instance dict. Remove in 1.0.
_PREVIOUS_RELEASE_PICKLE_KEYS: dict[str, Any] = {
    "dirty_vars": set(),
    "dirty_substates": set(),
    "_backend_vars": {},
}

if environment.REFLEX_PERF_MODE.get() != PerformanceMode.OFF:
    # If the state is this large, it's considered a performance issue.
    TOO_LARGE_SERIALIZED_STATE = environment.REFLEX_STATE_SIZE_LIMIT.get() * 1024
    # Only warn about each state class size once.
    _WARNED_ABOUT_STATE_SIZE: set[str] = set()

# Per state class, the names its dev-mode __setattr__ has found declared.
_SETTABLE_NAMES: dict[type, set[str]] = {}


def _is_picklable(obj: Any, dumps: Callable[[object], bytes]) -> bool:
    try:
        dumps(obj)
    except Exception:
        return False
    else:
        return True


def debug_failed_pickles(obj: object, dumps: Callable[[object], bytes]):
    """Recursively check the picklability of an object and its contents.

    Args:
        obj: The object to check.
        dumps: The pickle dump function to use.

    Raises:
        HANDLED_PICKLE_ERRORS: If the object or any of its contents are not picklable.
    """
    if _is_picklable(obj, dumps):
        return
    if sys.version_info < (3, 11):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            try:
                debug_failed_pickles(v, dumps)
            except HANDLED_PICKLE_ERRORS as e:
                e.add_note(f"While pickling dict value for key {k!r}")
                raise
            try:
                debug_failed_pickles(k, dumps)
            except HANDLED_PICKLE_ERRORS as e:
                e.add_note(f"While pickling dict key {k!r}")
                raise
        return
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            try:
                debug_failed_pickles(v, dumps)
            except HANDLED_PICKLE_ERRORS as e:  # noqa: PERF203
                e.add_note(f"While pickling index {i} of {type(obj).__name__}")
                raise
        return
    picklable_thing = obj.__getstate__()
    if picklable_thing is not None:
        debug_failed_pickles(picklable_thing, dumps)
    else:
        try:
            dumps(obj)
        except HANDLED_PICKLE_ERRORS as e:
            e.add_note(f"While pickling object of type {type(obj).__name__}")
            raise


@functools.cache
def _stale_pickle_keys(cls: type) -> frozenset[str]:
    """Get the keys of older pickles that are not restored into the instance dict.

    Args:
        cls: The state class.

    Returns:
        The slot names of the class, now holding bookkeeping, and the RouterData
        entry from before the router split (not `constants.ROUTER`: the name is
        frozen into payloads already on disk).
    """
    return frozenset(
        {"router"}.union(
            *(klass.__dict__.get("__slots__", ()) for klass in cls.__mro__)
        )
    )


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


class CoreState(EvenMoreBasicBaseState):
    """A node of a state tree: dirty tracking, deltas, locking and pickling of its fields.

    Subclasses fill in the class-level var bookkeeping below when they are
    created. The nodes of a tree are typed as the reflex ``BaseState``, the
    root of every state tree.
    """

    # A map from the var name to the var.
    vars: ClassVar[builtins.dict[str, Var]] = {}

    # The base vars of the class.
    base_vars: ClassVar[builtins.dict[str, Var]] = {}

    # The computed vars of the class.
    computed_vars: ClassVar[builtins.dict[str, ComputedVar]] = {}

    # Mapping of var name to set of (state_full_name, var_name) that depend on it.
    _var_dependencies: ClassVar[builtins.dict[str, set[tuple[str, str]]]] = {}

    # Set of vars which always need to be recomputed
    _always_dirty_computed_vars: ClassVar[set[str]] = set()

    # Set of substates which always need to be recomputed
    _always_dirty_substates: ClassVar[set[str]] = set()

    # Vars on this class sent to the client, and computed vars that expire on
    # an interval; recomputed with the dependency dicts, i.e. at class creation
    # and after any var is added.
    _frontend_var_names: ClassVar[frozenset[str]] = frozenset()
    _interval_computed_var_names: ClassVar[frozenset[str]] = frozenset()

    # Instance bookkeeping, kept out of `__dict__`: never a field, never pickled.
    __slots__ = (
        "_event_context",
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
        # On a root state, the event context that last held its lock; None for
        # a state no event context manages, which is always writable.
        _event_context: EventContext | None = field(default=None, is_var=False)

    def __init__(self, parent_state: BaseState | None = None, **kwargs):
        """Initialize the state.

        Args:
            parent_state: The parent state.
            **kwargs: The initial values of fields.
        """
        self._init_bookkeeping(parent_state)
        # Field values are set on first access; only the given ones are stored now.
        super().__init__(**kwargs)

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
        setattr_(self, "_event_context", None)

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

    @classmethod
    @functools.lru_cache
    def get_parent_state(cls) -> type[BaseState] | None:
        """Get the parent state.

        Returns:
            The parent state.

        Raises:
            ValueError: If more than one parent state is found.
        """
        parent_states = [base for base in cls.__bases__ if _is_tree_state(base)]
        if len(parent_states) >= 2:
            msg = f"Only one parent state of is allowed. Found {parent_states} parents of {cls}."
            raise ValueError(msg)
        # The first non-mixin state in the mro is our parent.
        return next(
            (base for base in cls.__mro__[1:] if _is_tree_state(base)),
            None,
        )

    @classmethod
    @functools.lru_cache
    def get_root_state(cls) -> type[BaseState]:
        """Get the root state.

        Returns:
            The root state.
        """
        parent_state = cls.get_parent_state()
        return cls if parent_state is None else parent_state.get_root_state()  # pyright: ignore[reportReturnType]

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
        return to_snake_case(f"{module}___{cls.__name__}")

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
            return cls  # pyright: ignore[reportReturnType]
        if path[0] == cls.get_name():
            if len(path) == 1:
                return cls  # pyright: ignore[reportReturnType]
            path = path[1:]
        for substate in cls.get_substates():
            if path[0] == substate.get_name():
                return substate.get_class_substate(path[1:])
        msg = f"Invalid path: {path}"
        raise ValueError(msg)

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
            return self  # pyright: ignore[reportReturnType]
        if path[0] == self.get_name():
            if len(path) == 1:
                return self  # pyright: ignore[reportReturnType]
            path = path[1:]
        if path[0] not in self.substates:
            msg = f"Invalid path: {path}"
            raise ValueError(msg)
        return self.substates[path[0]].get_substate(path[1:])

    def _get_root_state(self) -> BaseState:
        """Get the root state of the state tree.

        Returns:
            The root state of the state tree.
        """
        parent_state = self
        while parent_state.parent_state is not None:
            parent_state = parent_state.parent_state
        return parent_state  # pyright: ignore[reportReturnType]

    async def get_state(self, state_cls: type[T_STATE]) -> T_STATE:
        """Get the instance of a state class in this state's tree.

        Args:
            state_cls: The class of the state.

        Returns:
            The instance of state_cls in the tree.
        """
        return self._get_root_state().get_substate(state_cls.get_full_name().split("."))  # pyright: ignore[reportReturnType]

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

    def _client_token(self) -> str:
        """Get the token of the client this state belongs to.

        Returns:
            The client token, keying the uncached values it was last sent.
        """
        return ""

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
        pending: list[tuple[CoreState, str]] = [
            (self, name)
            for name in (self.dirty_vars if var_names is None else var_names)
        ]
        seen: set[tuple[str, str]] = set()
        while pending:
            state, name = pending.pop()
            for dependent in state._var_dependencies.get(name, ()):
                if dependent in seen:
                    continue
                seen.add(dependent)
                state_name, cvar_name = dependent
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
        return {
            cvar
            for cvar in type(self)._interval_computed_var_names
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

    def _clean(self):
        """Reset the dirty vars of this state and its dirty substates."""
        clean_state(self)

    async def __aenter__(self) -> Self:
        """Hold the lock on the state tree for the running event, making this state writable.

        Unless the running event context holds the lock already, like in a
        regular event handler, this takes it and reloads the tree, putting this
        state in it if it was reloaded since. A state that no event context
        manages is always writable, so entering it does nothing.

        Returns:
            This state.
        """
        root = self._get_root_state()
        if (bound := root._event_context) is None:
            return self
        current = EventContext._context_var.get(None)
        # A state of another client, or kept past its event (like by a
        # callback), enters under the context it was loaded in.
        ctx = current if current is not None and current.token == bound.token else bound
        entered = ctx.state_locks.entered_states
        if (entry := entered.get(id(self))) is not None:
            entry[0] += 1
            return self
        held = ctx.state_locks.held.get(ctx.token)
        lock = reset = None
        if held is not None and held[1] is asyncio.current_task():
            live_root = held[0]
        else:
            reset = EventContext.set(ctx) if ctx is not current else None
            lock = ctx.modify_state(BaseStateToken(ident=ctx.token, cls=type(self)))  # pyright: ignore[reportArgumentType]
            try:
                live_root = await lock.__aenter__()
            except BaseException:
                if reset is not None:
                    EventContext.reset(reset)
                raise
            ctx.state_locks.entered = True
        live = await live_root.get_state(type(self))
        if live is not self:
            self._take_place_of(live)
        entered[id(self)] = [1, lock, reset, live]
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Release the lock taken by entering the state, emitting the changes made.

        Args:
            exc_info: The exception info tuple.
        """
        if (ctx := EventContext._context_var.get(None)) is None or (
            entry := ctx.state_locks.entered_states.get(id(self))
        ) is None:
            return
        entry[0] -= 1
        if entry[0]:
            return
        del ctx.state_locks.entered_states[id(self)]
        _, lock, reset, live = entry
        if live is not self:
            # Hand the place back to the loaded instance, which the state
            # manager saves; this state keeps the values it had.
            live._take_place_of(self)
        if lock is None:
            return
        try:
            root = live._get_root_state()
            delta = await root._get_resolved_delta()
            root._clean()
            if delta:
                await ctx.emit_delta(delta)
        finally:
            try:
                await lock.__aexit__(*exc_info)
            finally:
                if reset is not None:
                    EventContext.reset(reset)

    def _take_place_of(self, other: CoreState) -> None:
        """Take the place of another instance of this state in its tree, with its values.

        Makes an instance kept from before the state was reloaded live again.

        Args:
            other: The instance of this state in the tree.
        """
        vars(self).clear()
        vars(self).update(vars(other))
        for klass in type(self).__mro__:
            for name in klass.__dict__.get("__slots__", ()):
                object.__setattr__(self, name, getattr(other, name))
        for substate in self.substates.values():
            substate.parent_state = self  # pyright: ignore[reportAttributeAccessIssue]
        if self.parent_state is not None:
            self.parent_state.substates[self.get_name()] = self  # pyright: ignore[reportArgumentType]
        elif (ctx := self._event_context) is not None:
            # The lock held on the tree covers its new root.
            held = ctx.state_locks.held
            for token, (root, task) in held.items():
                if root is other:
                    held[token] = (self, task)

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
        cls = type(self)
        fields = vars(self)
        # A field not read yet gets its default saved, so a generated one (like
        # a uuid) is the same when the state is loaded again.
        for name, f in cls.__fields__.items():
            if f._owner is cls and name not in fields:
                fields[name] = f.default_value()
        # Empty entries that let workers of the previous release load it.
        return {**fields, **_PREVIOUS_RELEASE_PICKLE_KEYS}

    def __setstate__(self, state: builtins.dict[str, Any]):
        """Set the state from redis deserialization.

        This method is called by pickle to deserialize the object.

        Args:
            state: The state dict for deserialization.
        """
        self._init_bookkeeping()
        cls = type(self)
        # Older pickles kept the backend vars in a dict of their own.
        state.update(state.pop("_backend_vars", {}))
        stale = _stale_pickle_keys(cls)
        fields = cls.__fields__
        vars(self).update(
            (key, value)
            for key, value in state.items()
            if key not in stale and ((f := fields.get(key)) is None or f._owner is cls)
        )

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
    ) -> Self:
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
