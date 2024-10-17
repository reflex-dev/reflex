"""Utility functions for constants."""

from typing import Any, Callable, Generic, Type

from typing_extensions import TypeVar

T = TypeVar("T")
V = TypeVar("V")


class classproperty(Generic[T, V]):
    """A class property decorator."""

    def __init__(self, getter: Callable[[Type[T]], V]) -> None:
        """Initialize the class property.

        Args:
            getter: The getter function.
        """
        self.getter = getattr(getter, "__func__", getter)

    def __get__(self, instance: Any, owner: Type[T]) -> V:
        """Get the value of the class property.

        Args:
            instance: The instance of the class.
            owner: The class itself.

        Returns:
            The value of the class property.
        """
        return self.getter(owner)
