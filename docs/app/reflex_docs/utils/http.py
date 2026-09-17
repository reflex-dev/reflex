"""HTTP client utilities."""

from collections.abc import Callable
from functools import wraps
from typing import TypeVar

import aiohttp
import orjson

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

    @wraps(f)
    def wrapper() -> T:
        nonlocal value
        value = f() if value is unset else value
        return value  # pyright: ignore[reportReturnType]

    return wrapper


def json_dumps(obj: object) -> str:
    return orjson.dumps(obj).decode("utf-8")


def one_client() -> aiohttp.ClientSession:
    """Create a single aiohttp client session."""
    return aiohttp.ClientSession(
        json_serialize=json_dumps,
    )


@once
def default_client() -> aiohttp.ClientSession:
    """Create a default aiohttp client session."""
    return one_client()
