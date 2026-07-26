"""hybrid_property decorator which functions like a normal python property but additionally allows (class-level) access from the frontend. You can use the same code for frontend and backend, or implement 2 different methods."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, cast, overload

from typing_extensions import TypeVar

from reflex_base.utils.exceptions import HybridPropertyError

from .base import Var

_T = TypeVar("_T")
_O = TypeVar("_O")
# Without a var function the frontend value is whatever running the getter
# against vars produces, and a var function may declare there is none.
_V = TypeVar("_V", default=Var[Any] | None)
_V2 = TypeVar("_V2", bound="Var[Any] | None")


class _StateBackendVarGuard:
    """Proxy around a state class used while building a hybrid property's frontend var.

    Attribute access is forwarded to the wrapped state class, except for backend
    (underscore-prefixed) vars, which raise :class:`HybridPropertyError`: backend vars
    are server-only and cannot be referenced from a hybrid property's frontend logic.
    """

    def __init__(self, state_cls: Any, property_name: str) -> None:
        """Initialize the guard.

        Args:
            state_cls: The state class the hybrid property is defined on.
            property_name: The name of the hybrid property (for error messages).
        """
        self.__state_cls = state_cls
        self.__property_name = property_name

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the state class, blocking backend vars.

        Args:
            name: The attribute accessed on the state inside the hybrid property.

        Returns:
            The class-level value (e.g. a frontend var) from the state.

        Raises:
            HybridPropertyError: If a backend (underscore-prefixed) var is accessed.
        """
        state_cls = self.__state_cls
        if name in state_cls.backend_vars:
            msg = (
                f"Hybrid property '{self.__property_name}' of state "
                f"'{state_cls.__name__}' accessed backend-only var '{name}' while "
                f"building its frontend value. Backend vars (prefixed with '_') exist "
                f"only on the server and cannot be referenced from a hybrid property's "
                f"frontend logic. Use a regular var, or provide a separate frontend "
                f"implementation with '@{self.__property_name}.var'."
            )
            raise HybridPropertyError(msg)
        return getattr(state_cls, name)


class HybridProperty(Generic[_T, _O, _V]):
    """A hybrid property that can also be used in frontend/as var.

    Deliberately not a `property` subclass: type checkers hard-code class-level
    access on properties to the descriptor itself, which would hide the frontend
    var this descriptor returns there. `_T` is the value the getter returns on an
    instance, `_O` the class the property is defined on, and `_V` the frontend var
    returned when the property is accessed on the class.
    """

    def __init__(
        self,
        fget: Callable[[_O], _T] | None = None,
        fset: Callable[[_O, _T], None] | None = None,
        fdel: Callable[[_O], None] | None = None,
        doc: str | None = None,
    ) -> None:
        """Initialize the hybrid property.

        Args:
            fget: The getter, returning the python value on an instance.
            fset: The optional setter.
            fdel: The optional deleter.
            doc: The docstring, taken from `fget` when not given.
        """
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc if doc is not None else getattr(fget, "__doc__", None)
        # The optional var function for the property.
        self._var: Callable[[Any], Var[Any] | None] | None = None
        # The attribute name the property is bound to, for error messages and
        # for rebinding when the var function is defined under another name.
        self._name: str | None = getattr(fget, "__name__", None)

    def __set_name__(self, owner: type, name: str, /) -> None:
        """Record the attribute name the property is bound to.

        Args:
            owner: The class the property is defined on.
            name: The attribute name the property is bound to.
        """
        self._name = name

    @property
    def _property_name(self) -> str:
        """The name of the property, for error messages.

        Returns:
            The bound attribute name, or a generic placeholder.
        """
        return self._name or "hybrid_property"

    def _derive(self) -> _HybridPropertyBinding[_T, _O, _V]:
        """Copy the property into a binding, so each class gets its own descriptor.

        The copy is a binding rather than a plain property so that whichever
        decorator produced it (`getter`, `setter`, `deleter` or `var`) may be
        defined under a name of its own without losing the property's name.

        Returns:
            A copy of this property that rebinds under the property's name.
        """
        new: _HybridPropertyBinding[_T, _O, _V] = _HybridPropertyBinding(
            self.fget, self.fset, self.fdel, self.__doc__
        )
        new._var = self._var
        new._name = self._name
        return new

    def _get_var(self, owner: Any) -> Var[Any] | None:
        """Get the frontend Var for the property.

        The ``owner`` is the object the property is accessed on at the var level:
        either the class (for class-level access, e.g. ``State.full_name``) or an
        ``ObjectVar`` (for attribute access on an object var, e.g. ``State.info.a_b``).
        Attribute access on ``owner`` inside the getter/var function resolves to Vars.

        Args:
            owner: The class or var the property is accessed on.

        Returns:
            The frontend Var for the property, or None if the var function
            declares that the property has no frontend value on ``owner``.

        Raises:
            AttributeError: If the property has no getter function and no var function is set.
        """
        if self._var is not None:
            # Call custom var function if set
            return self._var(owner)
        # Call the property getter function if no custom var function is set
        if self.fget is None:
            msg = f"Hybrid property '{self._property_name}' has no getter function"
            raise AttributeError(msg)
        # the getter runs against vars here, so it returns the frontend var
        return cast("Var[Any] | None", self.fget(owner))

    @overload
    def __get__(self, instance: None, owner: type, /) -> _V: ...

    @overload
    def __get__(self, instance: _O, owner: type | None = None, /) -> _T: ...

    def __get__(self, instance: Any, owner: type | None = None, /) -> Any:
        """Get the value of the property.

        On an instance, return the getter's value. At the class level, return a
        frontend Var only when accessed on a state (whose class attributes are
        vars); on any other class there is no var context, so return the
        descriptor itself, like a normal property. Note that var access on a
        nested object (e.g. ``State.info.a_b``) does not go through ``__get__`` —
        it is resolved by ``ObjectVar.__getattr__`` via ``_get_var``.

        Args:
            instance: The instance of the class accessing this property.
            owner: The class that this descriptor is attached to.

        Returns:
            The property value, a frontend Var, or the descriptor itself.

        Raises:
            AttributeError: If the property has no getter function.
            HybridPropertyError: If the frontend logic reads a backend-only state var.
        """
        if instance is not None:
            if self.fget is None:
                msg = f"Hybrid property '{self._property_name}' has no getter function"
                raise AttributeError(msg)
            return self.fget(instance)
        if isinstance(owner, type):
            from reflex.state import BaseState

            if issubclass(owner, BaseState):
                if not owner.backend_vars:
                    return self._get_var(owner)
                return self._get_var(_StateBackendVarGuard(owner, self._property_name))
        return self

    def __set__(self, instance: _O, value: _T, /) -> None:
        """Set the value of the property.

        Args:
            instance: The instance to set the value on.
            value: The value to set.

        Raises:
            AttributeError: If the property has no setter function.
        """
        if self.fset is None:
            msg = f"Hybrid property '{self._property_name}' has no setter"
            raise AttributeError(msg)
        self.fset(instance, value)

    def __delete__(self, instance: _O, /) -> None:
        """Delete the value of the property.

        Args:
            instance: The instance to delete the value on.

        Raises:
            AttributeError: If the property has no deleter function.
        """
        if self.fdel is None:
            msg = f"Hybrid property '{self._property_name}' has no deleter"
            raise AttributeError(msg)
        self.fdel(instance)

    def getter(self, fget: Callable[[_O], _T]) -> HybridProperty[_T, _O, _V]:
        """Set the getter function of the property.

        Args:
            fget: The getter function to set.

        Returns:
            A new property instance with the getter function set.
        """
        new = self._derive()
        new.fget = fget
        return new

    def setter(self, fset: Callable[[_O, _T], None]) -> HybridProperty[_T, _O, _V]:
        """Set the setter function of the property.

        Args:
            fset: The setter function to set.

        Returns:
            A new property instance with the setter function set.
        """
        new = self._derive()
        new.fset = fset
        return new

    def deleter(self, fdel: Callable[[_O], None]) -> HybridProperty[_T, _O, _V]:
        """Set the deleter function of the property.

        Args:
            fdel: The deleter function to set.

        Returns:
            A new property instance with the deleter function set.
        """
        new = self._derive()
        new.fdel = fdel
        return new

    @overload
    def var(
        self, func: classmethod[_O, ..., _V2], /
    ) -> HybridProperty[_T, _O, _V2]: ...

    @overload
    def var(self, func: staticmethod[..., _V2], /) -> HybridProperty[_T, _O, _V2]: ...

    @overload
    def var(self, func: Callable[[Any], _V2], /) -> HybridProperty[_T, _O, _V2]: ...

    def var(self, func: Any, /) -> Any:
        """Set the (optional) var function for the property.

        Returns a new HybridProperty with the same getter/setter/deleter so that
        each class gets its own descriptor, preventing shared-mixin mutation
        across subclasses. The var function receives the class (not an instance),
        and may return None to declare that the property has no frontend value on
        that class, e.g. when it depends on configuration the class does not
        enable. Declaring it a `classmethod` types its first parameter as the
        class without repeating the annotation.

        Redeclaring the property's name keeps the frontend var's type visible on
        class-level access:

            @hybrid_property
            def total_pages(self) -> int | None: ...

            @total_pages.var
            @classmethod
            def total_pages(cls) -> Var[int] | None: ...

        The result also binds itself under the name of the property it was
        created from, so the var function may instead be defined under a name of
        its own (at the cost of the frontend var's type on class access).

        Args:
            func: The var function to set.

        Returns:
            A new property instance with the var function set.
        """
        if isinstance(func, (classmethod, staticmethod)):
            func = func.__func__
        new = self._derive()
        new._var = func
        return new


class _HybridPropertyBinding(HybridProperty[_T, _O, _V]):
    """The descriptor the `getter`, `setter`, `deleter` and `var` decorators return.

    Those functions are commonly defined under a name of their own so they do not
    shadow the property's declaration. This descriptor puts the finished property
    back under the property's name when the class body is evaluated, and removes
    itself from the alias name.

    When several of them are used on one property, each must decorate the result of
    the previous one, since a copy carries only what the property it was derived
    from had::

        @value.setter
        def _value_setter(self, new: str) -> None: ...

        @_value_setter.deleter
        def _value_deleter(self) -> None: ...
    """

    def __set_name__(self, owner: type, name: str, /) -> None:
        """Bind the finished property under the name of the property it extends.

        Args:
            owner: The class the decorated function is defined on.
            name: The attribute name the decorated function is bound to.

        Raises:
            HybridPropertyError: If the property it extends has no known name.
        """
        target = self._name
        if target is None:
            msg = (
                f"'{name}' of '{owner.__name__}' extends a hybrid property with no "
                f"name; define the property in a class body or with a named getter "
                f"function."
            )
            raise HybridPropertyError(msg)
        bound = HybridProperty(self.fget, self.fset, self.fdel, self.__doc__)
        bound._var = self._var
        bound._name = target
        setattr(owner, target, bound)
        if name != target:
            delattr(owner, name)


hybrid_property = HybridProperty
