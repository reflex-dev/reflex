"""A module to hold state proxy classes."""

from typing import Any

from reflex.state import StateProxy


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
        raise NotImplementedError("This is a read-only state proxy.")

    def mark_dirty(self):
        """Mark the state as dirty.

        Raises:
            NotImplementedError: Always raised when trying to mark the proxied state as dirty.
        """
        raise NotImplementedError("This is a read-only state proxy.")
