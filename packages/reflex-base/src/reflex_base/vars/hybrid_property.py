"""hybrid_property decorator which functions like a normal python property but additionally allows (class-level) access from the frontend. You can use the same code for frontend and backend, or implement 2 different methods."""

from collections.abc import Callable
from typing import Any

from reflex_base.utils.types import Self, override

from .base import Var


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
        """
        if instance is not None:
            return super().__get__(instance, owner)
        if isinstance(owner, type):
            from reflex.state import BaseState

            if issubclass(owner, BaseState):
                return self._get_var(owner)
        return self

    def var(self, func: Callable[[Any], Var]) -> Self:
        """Set the (optional) var function for the property.

        Args:
            func: The var function to set.

        Returns:
            The property instance with the var function set.
        """
        self._var = func
        return self


hybrid_property = HybridProperty
