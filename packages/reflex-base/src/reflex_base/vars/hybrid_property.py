"""hybrid_property decorator which functions like a normal python property but additionally allows (class-level) access from the frontend. You can use the same code for frontend and backend, or implement 2 different methods."""

from collections.abc import Callable
from typing import Any

from reflex_base.utils.exceptions import HybridPropertyError
from reflex_base.utils.format import callable_name
from reflex_base.utils.types import Self, override

from .base import Var


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


class HybridProperty(property):
    """A hybrid property that can also be used in frontend/as var."""

    # The optional var function for the property.
    _var: Callable[[Any], Var] | None = None

    def _get_var(self, owner: Any) -> Var:
        """Get the frontend Var for the property.

        The ``owner`` is the object the property is accessed on at the var level:
        either the class (for class-level access, e.g. ``State.full_name``) or an
        ``ObjectVar`` (for attribute access on an object var, e.g. ``State.info.a_b``).
        Attribute access on ``owner`` inside the getter/var function resolves to Vars.

        Args:
            owner: The class or var the property is accessed on.

        Returns:
            The frontend Var for the property.

        Raises:
            AttributeError: If the property has no getter function and no var function is set.
        """
        if self._var is not None:
            # Call custom var function if set
            return self._var(owner)
        # Call the property getter function if no custom var function is set
        if self.fget is None:
            msg = "HybridProperty has no getter function"
            raise AttributeError(msg)
        return self.fget(owner)

    @override
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
            HybridPropertyError: If the frontend logic reads a backend-only state var.
        """
        if instance is not None:
            return super().__get__(instance, owner)
        if isinstance(owner, type):
            from reflex.state import BaseState

            if issubclass(owner, BaseState):
                if not owner.backend_vars:
                    return self._get_var(owner)
                property_name = (
                    callable_name(self.fget)
                    if self.fget is not None
                    else "hybrid_property"
                )
                return self._get_var(_StateBackendVarGuard(owner, property_name))
        return self

    def var(self, func: Callable[[Any], Var]) -> Self:
        """Set the (optional) var function for the property.

        Returns a new HybridProperty with the same getter/setter/deleter so
        that each class gets its own descriptor — matching how property.setter
        behaves and preventing shared-mixin mutation across subclasses.

        Args:
            func: The var function to set.

        Returns:
            A new property instance with the var function set.
        """
        new = type(self)(self.fget, self.fset, self.fdel, self.__doc__)
        new._var = func
        return new


hybrid_property = HybridProperty
