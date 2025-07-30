"""Decorator utilities."""

import functools
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar, cast

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


def _write_cached_procedure_file(payload: str, cache_file: Path, value: object):
    import pickle

    cache_file.write_bytes(pickle.dumps((payload, value)))


def _read_cached_procedure_file(cache_file: Path) -> tuple[str | None, object]:
    import pickle

    if cache_file.exists():
        with cache_file.open("rb") as f:
            return pickle.loads(f.read())

    return None, None


P = ParamSpec("P")
Picklable = TypeVar("Picklable")


def cached_procedure(
    cache_file_path: Callable[[], Path],
    payload_fn: Callable[P, str],
) -> Callable[[Callable[P, Picklable]], Callable[P, Picklable]]:
    """Decorator to cache the result of a function based on its arguments.

    Args:
        cache_file_path: Function that computes the cache file path.
        payload_fn: Function that computes cache payload from function args.

    Returns:
        The decorated function.
    """

    def _inner_decorator(func: Callable[P, Picklable]) -> Callable[P, Picklable]:
        def _inner(*args: P.args, **kwargs: P.kwargs) -> Picklable:
            _cache_file = cache_file_path()

            payload, value = _read_cached_procedure_file(_cache_file)
            new_payload = payload_fn(*args, **kwargs)

            if payload != new_payload:
                new_value = func(*args, **kwargs)
                _write_cached_procedure_file(new_payload, _cache_file, new_value)
                return new_value

            from reflex.utils import console

            console.debug(
                f"Using cached value for {func.__name__} with payload: {new_payload}"
            )
            return cast("Picklable", value)

        return _inner

    return _inner_decorator


def cache_result_in_disk(
    cache_file_path: Callable[[], Path],
) -> Callable[[Callable[[], Picklable]], Callable[[], Picklable]]:
    """Decorator to cache the result of a function on disk.

    Args:
        cache_file_path: Function that computes the cache file path.

    Returns:
        The decorated function.
    """
    return cached_procedure(
        cache_file_path=cache_file_path, payload_fn=lambda: "constant"
    )
