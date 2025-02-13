"""Decorator utilities."""

from typing import Callable, TypeVar

T = TypeVar("T")


def once(f: Callable[[], T]) -> Callable[[], T]:
    """A decorator that calls the function once and caches the result.

    Args:
        f: The function to call.

    Returns:
        A function that calls the function once and caches the result.
    """
    unset = object()
    value: object | T = unset

    def wrapper() -> T:
        nonlocal value
        value = f() if value is unset else value
        return value  # pyright: ignore[reportReturnType]

    return wrapper
