"""hybrid_property decorator which functions like a normal python property but additionally allows (class-level) access from the frontend. You can use the same code for frontend and backend, or implement 2 different methods."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Generic, cast, overload

from typing_extensions import Self, TypeVar

from reflex_base.utils.exceptions import HybridPropertyError

from .base import Var

if TYPE_CHECKING:
    from reflex.state import BaseState

    from .number import BooleanVar, NumberVar
    from .object import ObjectVar
    from .sequence import ArrayVar, StringVar

_T = TypeVar("_T")
# the new value type when `getter` replaces the getter
_T2 = TypeVar("_T2")
_O = TypeVar("_O")
# the getter's return type, for resolving class-level access to a var type
_INT = TypeVar("_INT", bound=int)
_FLOAT = TypeVar("_FLOAT", bound=float)
_STR = TypeVar("_STR", bound=str)
_SEQUENCE = TypeVar("_SEQUENCE", bound=Sequence[Any])
_MAPPING = TypeVar("_MAPPING", bound=Mapping[Any, Any])
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
        self._state_cls = state_cls
        self._property_name = property_name

    def __getattribute__(self, name: str) -> Any:
        """Forward attribute access to the state class, blocking backend vars.

        Overrides `__getattribute__` rather than `__getattr__` so that names the
        guard itself carries (`__doc__`, `__module__`, `__class__`, ...) resolve
        on the state class too.

        Args:
            name: The attribute accessed on the state inside the hybrid property.

        Returns:
            The class-level value (e.g. a frontend var) from the state.

        Raises:
            HybridPropertyError: If a backend (underscore-prefixed) var is accessed.
        """
        state_cls = object.__getattribute__(self, "_state_cls")
        if name in state_cls.backend_vars:
            property_name = object.__getattribute__(self, "_property_name")
            msg = (
                f"Hybrid property '{property_name}' of state "
                f"'{state_cls.__name__}' accessed backend-only var '{name}' while "
                f"building its frontend value. Backend vars (prefixed with '_') exist "
                f"only on the server and cannot be referenced from a hybrid property's "
                f"frontend logic. Use a regular var, or provide a separate frontend "
                f"implementation with '@{property_name}.var'."
            )
            raise HybridPropertyError(msg)
        return getattr(state_cls, name)


if TYPE_CHECKING:

    class _PropertyBase:
        """Typing stand-in for `property`, see `HybridProperty` docstring."""

        fget: Callable[[Any], Any] | None
        fset: Callable[[Any, Any], None] | None
        fdel: Callable[[Any], None] | None
        __isabstractmethod__: bool

        def __init__(
            self,
            fget: Callable[[Any], Any] | None = None,
            fset: Callable[[Any, Any], None] | None = None,
            fdel: Callable[[Any], None] | None = None,
            doc: str | None = None,
        ) -> None: ...

else:
    _PropertyBase = property


class HybridProperty(_PropertyBase, Generic[_T, _O, _V]):
    """A hybrid property that can also be used in frontend/as var.

    A `property` subclass at runtime (so pydantic, `abc` and friends treat it
    like one), but typed independently: type checkers hard-code class-level
    access on properties to the descriptor itself, hiding the frontend var.
    `_T` is the instance value, `_O` the owning class, `_V` the frontend var
    returned on class access.

    Without a var function, class-level access is typed as the var equivalent of
    `_T`, which holds as long as the getter builds a Var when it runs against
    vars. A getter that collapses them to a plain Python value (e.g. `str(...)`,
    `len(...)`) needs a var function to say what the frontend value really is.
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
        super().__init__(fget, fset, fdel, doc)
        # The optional var function for the property.
        self._var: Callable[[Any], Var[Any] | None] | None = None
        # The attribute name the property is bound to.
        self._name: str | None = getattr(fget, "__name__", None)
        # Whether __set_name__ has made `_name` authoritative.
        self._bound: bool = False
        # Derivation source and decorated-function name, set by `_derive`.
        self._origin: HybridProperty[Any, Any, Any] | None = None
        self._decl_name: str | None = None

    def __set_name__(self, owner: type, name: str, /) -> None:
        """Bind the property under its final attribute name.

        A derived copy still carrying the name its decorated function was
        declared under rebinds itself to its origin's name, dropping that
        declaration and merging in accessors an earlier copy bound there.
        Assigning a copy to a name of its own (``b = a.setter(f)``) forks it.

        Args:
            owner: The class the property is defined on.
            name: The attribute name the property is assigned to.
        """
        decl_name, self._decl_name = self._decl_name, None
        if decl_name is None or name != decl_name:
            self._name = name
            self._bound = True
            return
        # Resolve the target name only now: the origin learns its final name
        # in its own __set_name__, which by class-body order has already run.
        origin = self._origin
        if origin is not None and not origin._bound:
            # An unbound origin was replaced by a redeclaration; its
            # replacement carries the name. No replacement means it is self.
            target = self._find_replacement_name(owner, origin) or name
        else:
            target = (origin._name or name) if origin is not None else name
        self._name = target
        self._bound = True
        if target == name:
            return
        bound = self
        existing = owner.__dict__.get(target)
        if isinstance(existing, HybridProperty):
            # Decorators derived from the same property instead of chained:
            # keep the accessors and var function this copy does not carry.
            bound = type(self)(
                self.fget or existing.fget,
                self.fset or existing.fset,
                self.fdel or existing.fdel,
                self.__doc__ or existing.__doc__,
            )
            bound._var = self._var if self._var is not None else existing._var
            bound._name = target
            bound._bound = True
            # Keep the chain so later copies still find this one.
            bound._origin = self._origin
        setattr(owner, target, bound)
        delattr(owner, name)

    def _find_replacement_name(
        self, owner: type, origin: HybridProperty[Any, Any, Any]
    ) -> str | None:
        """Find the name of the bound copy that replaced ``origin`` in the class body.

        The redeclared name keeps the origin's class-body position, so the
        replacement has already bound when this runs.

        Args:
            owner: The class the property is defined on.
            origin: The unbound origin this property derives from.

        Returns:
            The replacing copy's attribute name, or None if this copy itself
            is the replacement.
        """
        for attr, existing in owner.__dict__.items():
            if (
                existing is self
                or not isinstance(existing, HybridProperty)
                # A copy that has not bound yet rebinds itself later.
                or not existing._bound
                or existing._name != attr
            ):
                continue
            node = existing._origin
            while node is not None:
                if node is origin:
                    return attr
                node = node._origin
        return None

    @property
    def _property_name(self) -> str:
        """The name of the property, for error messages.

        Returns:
            The bound attribute name, or a generic placeholder.
        """
        return self._name or "hybrid_property"

    def _derive(
        self,
        func: Callable[..., Any],
        fget: Callable[[_O], Any] | None = None,
        fset: Callable[[_O, _T], None] | None = None,
        fdel: Callable[[_O], None] | None = None,
    ) -> Self:
        """Copy the property, so each class gets its own descriptor.

        The copy records its origin and ``func``'s name for `__set_name__`. A
        replacement getter may retype the value, so `getter` types its result.

        Args:
            func: The function the deriving decorator was applied to.
            fget: Replacement getter, keeping the current one when None.
            fset: Replacement setter, keeping the current one when None.
            fdel: Replacement deleter, keeping the current one when None.

        Returns:
            A copy of this property with the given accessors replaced.
        """
        new = type(self)(
            fget or self.fget, fset or self.fset, fdel or self.fdel, self.__doc__
        )
        new._var = self._var
        new._name = self._name
        new._origin = self
        new._decl_name = getattr(func, "__name__", None)
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

    # Without an explicitly typed var function, class-level access resolves to the
    # var equivalent of the getter's return type, the way `Field` does for base
    # vars. The `_V` default in the `self` annotations keeps these from matching
    # once a var function has declared a type of its own. Only access on a state
    # produces a var; on any other class the descriptor itself is returned.
    @overload
    def __get__(
        self: HybridProperty[bool, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> BooleanVar: ...

    @overload
    def __get__(
        self: HybridProperty[bool | None, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> BooleanVar | None: ...

    @overload
    def __get__(
        self: HybridProperty[_INT, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> NumberVar[_INT]: ...

    @overload
    def __get__(
        self: HybridProperty[_INT | None, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> NumberVar[_INT] | None: ...

    @overload
    def __get__(
        self: HybridProperty[_FLOAT, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> NumberVar[_FLOAT]: ...

    @overload
    def __get__(
        self: HybridProperty[_FLOAT | None, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> NumberVar[_FLOAT] | None: ...

    @overload
    def __get__(
        self: HybridProperty[_STR, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> StringVar: ...

    @overload
    def __get__(
        self: HybridProperty[_STR | None, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> StringVar | None: ...

    @overload
    def __get__(
        self: HybridProperty[_MAPPING, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> ObjectVar[_MAPPING]: ...

    @overload
    def __get__(
        self: HybridProperty[_MAPPING | None, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> ObjectVar[_MAPPING] | None: ...

    @overload
    def __get__(
        self: HybridProperty[_SEQUENCE, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> ArrayVar[_SEQUENCE]: ...

    @overload
    def __get__(
        self: HybridProperty[_SEQUENCE | None, Any, Var[Any] | None],
        instance: None,
        owner: type[BaseState],
        /,
    ) -> ArrayVar[_SEQUENCE] | None: ...

    @overload
    def __get__(self, instance: None, owner: type[BaseState], /) -> _V: ...

    @overload
    def __get__(self, instance: None, owner: type, /) -> Self: ...

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

    def getter(self, fget: Callable[[_O], _T2]) -> HybridProperty[_T2, _O, _V]:
        """Set the getter function of the property.

        The new getter's return type becomes the property's value type, so a
        getter-less property gets its type from the getter added here.

        Args:
            fget: The getter function to set.

        Returns:
            A new property instance with the getter function set.
        """
        new = self._derive(fget, fget=fget)
        if new._name is None:
            new._name = new._decl_name
        return cast("HybridProperty[_T2, _O, _V]", new)

    def setter(self, fset: Callable[[_O, _T], None]) -> HybridProperty[_T, _O, _V]:
        """Set the setter function of the property.

        Args:
            fset: The setter function to set.

        Returns:
            A new property instance with the setter function set.
        """
        return self._derive(fset, fset=fset)

    def deleter(self, fdel: Callable[[_O], None]) -> HybridProperty[_T, _O, _V]:
        """Set the deleter function of the property.

        Args:
            fdel: The deleter function to set.

        Returns:
            A new property instance with the deleter function set.
        """
        return self._derive(fdel, fdel=fdel)

    @overload
    def var(
        self, func: classmethod[_O, ..., _V2], /
    ) -> HybridProperty[_T, _O, _V2]: ...

    @overload
    def var(self, func: staticmethod[[Any], _V2], /) -> HybridProperty[_T, _O, _V2]: ...

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
        new = self._derive(func)
        new._var = func
        return new


hybrid_property = HybridProperty
