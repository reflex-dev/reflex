"""Decorator utilities."""

import functools
import logging
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar, cast

logger = logging.getLogger(__name__)

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
    import contextlib
    import pickle
    import uuid

    if cache_file.is_symlink():
        cache_file = cache_file.resolve()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    mode = cache_file.stat().st_mode if cache_file.exists() else None
    temporary_path = cache_file.with_name(f".{cache_file.name}.{uuid.uuid4().hex}.tmp")
    created = False
    try:
        with temporary_path.open("xb") as temporary_file:
            created = True
            temporary_file.write(pickle.dumps((payload, value)))
        if mode is not None:
            temporary_path.chmod(mode & 0o7777)
        temporary_path.replace(cache_file)
    except BaseException:
        if created:
            with contextlib.suppress(OSError):
                temporary_path.unlink(missing_ok=True)
        raise


def _read_cached_procedure_file(cache_file: Path) -> tuple[str | None, object]:
    import pickle

    if cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                payload, value = pickle.loads(f.read())
            if not isinstance(payload, str):
                return None, None
        except (pickle.UnpicklingError, EOFError, TypeError, ValueError) as err:
            logger.debug(f"Ignoring invalid procedure cache {cache_file}: {err}")
        else:
            return payload, value

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
            cache_file = cache_file_path()

            payload, value = _read_cached_procedure_file(cache_file)
            new_payload = payload_fn(*args, **kwargs)

            if payload != new_payload:
                new_value = func(*args, **kwargs)
                _write_cached_procedure_file(new_payload, cache_file, new_value)
                return new_value

            logger.debug(
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
