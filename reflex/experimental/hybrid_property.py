"""hybrid_property decorator which functions like a normal python property but additionally allows (class-level) access from the frontend. You can use the same code for frontend and backend, or implement 2 different methods."""

from collections.abc import Callable
from typing import Any

from reflex.utils.types import Self, override
from reflex.vars.base import Var


class HybridProperty(property):
    """A hybrid property that can also be used in frontend/as var."""

    # The optional var function for the property.
    _var: Callable[[Any], Var] | None = None

    @override
    def __get__(self, instance: Any, owner: type | None = None, /) -> Any:
        """Get the value of the property. If the property is not bound to an instance return a frontend Var.

        Args:
            instance: The instance of the class accessing this property.
            owner: The class that this descriptor is attached to.

        Returns:
            The value of the property or a frontend Var.
        """
        if instance is not None:
            return super().__get__(instance, owner)
        if self._var is not None:
            # Call custom var function if set
            return self._var(owner)
        # Call the property getter function if no custom var function is set
        if self.fget is None:
            raise AttributeError("HybridProperty has no getter function")
        return self.fget(owner)

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
