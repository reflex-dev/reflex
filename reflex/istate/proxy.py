"""A module to hold state proxy classes."""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import functools
import inspect
import json
from collections.abc import Callable, Sequence
from importlib.util import find_spec
from types import MethodType
from typing import TYPE_CHECKING, Any, SupportsIndex, TypeVar

import wrapt

from reflex.base import Base
from reflex.utils import prerequisites
from reflex.utils.exceptions import ImmutableStateError
from reflex.utils.serializers import can_serialize, serialize, serializer
from reflex.vars.base import Var

if TYPE_CHECKING:
    from reflex.state import BaseState, StateUpdate

T_STATE = TypeVar("T_STATE", bound="BaseState")


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
        parent_state_proxy: StateProxy | None = None,
    ):
        """Create a proxy for a state instance.

        If `get_state` is used on a StateProxy, the resulting state will be
        linked to the given state via parent_state_proxy. The first state in the
        chain is the state that initiated the background task.

        Args:
            state_instance: The state instance to proxy.
            parent_state_proxy: The parent state proxy, for linked mutability and context tracking.
        """
        from reflex.state import _substate_key

        super().__init__(state_instance)
        self._self_app = prerequisites.get_and_validate_app().app
        self._self_substate_path = tuple(state_instance.get_full_name().split("."))
        self._self_substate_token = _substate_key(
            state_instance.router.session.client_token,
            self._self_substate_path,
        )
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
            from reflex.state import State

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
            msg = "The state is already mutable. Do not nest `async with self` blocks."
            raise ImmutableStateError(msg)

        await self._self_actx_lock.acquire()
        self._self_actx_lock_holder = current_task
        self._self_actx = self._self_app.modify_state(
            token=self._self_substate_token, background=True
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
        msg = "Background task must use `async with self` to modify state."
        raise TypeError(msg)

    def __exit__(self, *exc_info: Any) -> None:
        """Exit the regular context manager protocol.

        Args:
            exc_info: The exception info tuple.
        """

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
            msg = (
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
            raise ImmutableStateError(msg)

        value = super().__getattr__(name)  # pyright: ignore[reportAttributeAccessIssue]
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

        msg = (
            "Background task StateProxy is immutable outside of a context "
            "manager. Use `async with self` to modify state."
        )
        raise ImmutableStateError(msg)

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
            msg = (
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
            raise ImmutableStateError(msg)
        return self.__wrapped__.get_substate(path)

    async def get_state(self, state_cls: type[T_STATE]) -> T_STATE:
        """Get an instance of the state associated with this token.

        Args:
            state_cls: The class of the state.

        Returns:
            The state.

        Raises:
            ImmutableStateError: If the state is not in mutable mode.
        """
        if not self._is_mutable():
            msg = (
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
            raise ImmutableStateError(msg)
        return type(self)(
            await self.__wrapped__.get_state(state_cls), parent_state_proxy=self
        )  # pyright: ignore [reportReturnType]

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


class ReadOnlyStateProxy(StateProxy):
    """A read-only proxy for a state."""

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent setting attributes on the state for read-only proxy.

        Args:
            name: The attribute name.
            value: The attribute value.

        Raises:
            NotImplementedError: Always raised when trying to set an attribute on proxied state.
        """
        if name.startswith("_self_"):
            # Special case attributes of the proxy itself, not applied to the wrapped object.
            super().__setattr__(name, value)
            return
        msg = "This is a read-only state proxy."
        raise NotImplementedError(msg)

    def mark_dirty(self):
        """Mark the state as dirty.

        Raises:
            NotImplementedError: Always raised when trying to mark the proxied state as dirty.
        """
        msg = "This is a read-only state proxy."
        raise NotImplementedError(msg)


if find_spec("pydantic"):
    import pydantic

    NEVER_WRAP_BASE_ATTRS = set(Base.__dict__) - {"set"} | set(
        pydantic.BaseModel.__dict__
    )
else:
    NEVER_WRAP_BASE_ATTRS = {}

MUTABLE_TYPES = (
    list,
    dict,
    set,
    Base,
)

if find_spec("sqlalchemy"):
    from sqlalchemy.orm import DeclarativeBase

    MUTABLE_TYPES += (DeclarativeBase,)

if find_spec("pydantic"):
    from pydantic import BaseModel as BaseModelV2
    from pydantic.v1 import BaseModel as BaseModelV1

    MUTABLE_TYPES += (BaseModelV1, BaseModelV2)


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

    # Dynamically generated classes for tracking dataclass mutations.
    __dataclass_proxies__: dict[str, type] = {}

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
        return super().__new__(cls)  # pyright: ignore[reportArgumentType]

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
        return None

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
        if is_mutable_type(type(value)) and not isinstance(value, MutableProxy):
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
        value = super().__getattr__(__name)  # pyright: ignore[reportAttributeAccessIssue]

        if callable(value):
            if __name in self.__mark_dirty_attrs__:
                # Wrap special callables, like "append", which should mark state dirty.
                value = wrapt.FunctionWrapper(value, self._mark_dirty)

            if __name in self.__wrap_mutable_attrs__:
                # Wrap special methods that may return mutable objects tied to the state.
                value = wrapt.FunctionWrapper(
                    value,
                    self._wrap_recursive_decorator,  # pyright: ignore[reportArgumentType]
                )

            if (
                not isinstance(self.__wrapped__, Base)
                or __name not in NEVER_WRAP_BASE_ATTRS
            ) and hasattr(value, "__func__"):
                # Rebind `self` to the proxy on methods to capture nested mutations.
                return functools.partial(value.__func__, self)  # pyright: ignore [reportFunctionMemberAccess, reportAttributeAccessIssue]

        if is_mutable_type(type(value)) and __name not in (
            "__wrapped__",
            "_self_state",
            "__dict__",
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
        value = super().__getitem__(key)  # pyright: ignore[reportAttributeAccessIssue]
        if isinstance(key, slice) and isinstance(value, list):
            return [self._wrap_recursive(item) for item in value]
        # Recursively wrap mutable items retrieved through this proxy.
        return self._wrap_recursive(value)

    def __iter__(self) -> Any:
        """Iterate over the proxied object and return a proxy if mutable.

        Yields:
            Each item value (possibly wrapped in MutableProxy).
        """
        for value in super().__iter__():  # pyright: ignore[reportAttributeAccessIssue]
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
        self._mark_dirty(super().__delitem__, args=(key,))  # pyright: ignore[reportAttributeAccessIssue]

    def __setitem__(self, key: str, value: Any):
        """Set the item on the proxied object and mark state dirty.

        Args:
            key: The key of the item.
            value: The value of the item.
        """
        self._mark_dirty(super().__setitem__, args=(key, value))  # pyright: ignore[reportAttributeAccessIssue]

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
    obj = mp.__wrapped__
    if can_serialize(type(obj)):
        return serialize(obj)
    return obj


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
            msg = (
                "Background task StateProxy is immutable outside of a context "
                "manager. Use `async with self` to modify state."
            )
            raise ImmutableStateError(msg)
        return super()._mark_dirty(
            wrapped=wrapped, instance=instance, args=args, kwargs=kwargs
        )


@functools.lru_cache(maxsize=1024)
def is_mutable_type(type_: type) -> bool:
    """Check if a type is mutable and should be wrapped.

    Args:
        type_: The type to check.

    Returns:
        Whether the type is mutable and should be wrapped.
    """
    return issubclass(type_, MUTABLE_TYPES) or (
        dataclasses.is_dataclass(type_) and not issubclass(type_, Var)
    )
