"""Helpers for managing asyncio tasks."""

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any

from reflex.utils import console


async def _run_forever(
    coro_function: Callable[..., Coroutine],
    *args: Any,
    suppress_exceptions: list[type[BaseException]],
    exception_delay: float,
    exception_limit: int,
    exception_limit_window: float,
    **kwargs: Any,
):
    """Wrapper to continuously run a coroutine function, suppressing certain exceptions.

    Args:
        coro_function: The coroutine function to run.
        *args: The arguments to pass to the coroutine function.
        suppress_exceptions: The exceptions to suppress.
        exception_delay: The delay between retries when an exception is suppressed.
        exception_limit: The maximum number of suppressed exceptions within the limit window before raising.
        exception_limit_window: The time window in seconds for counting suppressed exceptions.
        **kwargs: The keyword arguments to pass to the coroutine function.
    """
    last_regular_loop_start = 0
    exception_count = 0

    while True:
        # Reset the exception count when the limit window has elapsed since the last non-exception loop started.
        if last_regular_loop_start + exception_limit_window < time.monotonic():
            exception_count = 0
        if not exception_count:
            last_regular_loop_start = time.monotonic()
        try:
            await coro_function(*args, **kwargs)
        except (asyncio.CancelledError, RuntimeError):
            raise
        except Exception as e:
            if any(isinstance(e, ex) for ex in suppress_exceptions):
                exception_count += 1
                if exception_count >= exception_limit:
                    console.error(
                        f"{coro_function.__name__}: task exceeded exception limit {exception_limit} within {exception_limit_window}s: {e}"
                    )
                    raise
                console.error(f"{coro_function.__name__}: task error suppressed: {e}")
                await asyncio.sleep(exception_delay)
                continue
            raise


def ensure_task(
    owner: Any,
    task_attribute: str,
    coro_function: Callable[..., Coroutine],
    *args: Any,
    suppress_exceptions: list[type[BaseException]] | None = None,
    exception_delay: float = 1.0,
    exception_limit: int = 5,
    exception_limit_window: float = 60.0,
    **kwargs: Any,
) -> asyncio.Task:
    """Ensure that a task is running for the given coroutine function.

    Note: if the task is already running, args and kwargs are ignored.

    Args:
        owner: The owner of the task.
        task_attribute: The attribute name to store/retrieve the task from the owner object.
        coro_function: The coroutine function to run as a task.
        suppress_exceptions: The exceptions to log and continue when running the coroutine.
        exception_delay: The delay between retries when an exception is suppressed.
        exception_limit: The maximum number of suppressed exceptions within the limit window before raising.
        exception_limit_window: The time window in seconds for counting suppressed exceptions.
        *args: The arguments to pass to the coroutine function.
        **kwargs: The keyword arguments to pass to the coroutine function.

    Returns:
        The asyncio task running the coroutine function.
    """
    if suppress_exceptions is None:
        suppress_exceptions = []
    if RuntimeError in suppress_exceptions:
        msg = "Cannot suppress RuntimeError exceptions which may be raised by asyncio machinery."
        raise RuntimeError(msg)

    task = getattr(owner, task_attribute, None)
    if task is None or task.done():
        asyncio.get_running_loop()  # Ensure we're in an event loop.
        task = asyncio.create_task(
            _run_forever(
                coro_function,
                *args,
                suppress_exceptions=suppress_exceptions,
                exception_delay=exception_delay,
                exception_limit=exception_limit,
                exception_limit_window=exception_limit_window,
                **kwargs,
            ),
            name=f"reflex_ensure_task|{type(owner).__name__}.{task_attribute}={coro_function.__name__}|{time.time()}",
        )
        setattr(owner, task_attribute, task)
    return task
