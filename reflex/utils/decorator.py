"""Decorator utilities."""

import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar

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

    @functools.wraps(f)
    def wrapper() -> T:
        nonlocal value
        value = f() if value is unset else value
        return value  # pyright: ignore[reportReturnType]

    return wrapper


def once_unless_none(f: Callable[[], T | None]) -> Callable[[], T | None]:
    """A decorator that calls the function once and caches the result unless it is None.

    Args:
        f: The function to call.

    Returns:
        A function that calls the function once and caches the result unless it is None.
    """
    value: T | None = None

    @functools.wraps(f)
    def wrapper() -> T | None:
        nonlocal value
        value = f() if value is None else value
        return value

    return wrapper


P = ParamSpec("P")


def debug(f: Callable[P, T]) -> Callable[P, T]:
    """A decorator that prints the function name, arguments, and result.

    Args:
        f: The function to call.

    Returns:
        A function that prints the function name, arguments, and result.
    """

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        result = f(*args, **kwargs)
        print(  # noqa: T201
            f"Calling {f.__name__} with args: {args} and kwargs: {kwargs}, result: {result}"
        )
        return result

    return wrapper
