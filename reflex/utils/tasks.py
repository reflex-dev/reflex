"""Helpers for managing asyncio tasks."""

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from contextvars import Context
from typing import Any

logger = logging.getLogger(__name__)


async def _run_forever(
    coro_function: Callable[..., Coroutine],
    *args: Any,
    suppress_exceptions: list[type[BaseException]],
    exception_delay: float,
    exception_limit: int | None,
    exception_limit_window: float,
    exception_delay_max: float,
    **kwargs: Any,
):
    """Wrapper to continuously run a coroutine function, suppressing certain exceptions.

    Args:
        coro_function: The coroutine function to run.
        *args: The arguments to pass to the coroutine function.
        suppress_exceptions: The exceptions to suppress.
        exception_delay: The delay between retries when an exception is suppressed.
        exception_limit: The maximum number of suppressed exceptions within the limit window before raising.
            Without a limit (None), the delay doubles after each exception in a row, only the first of them
            is logged, and the coroutine function is passed a `recovered` callable to call once it works again.
        exception_limit_window: The time window in seconds for counting suppressed exceptions.
        exception_delay_max: The longest delay between retries when there is no exception limit.
        **kwargs: The keyword arguments to pass to the coroutine function.
    """
    last_regular_loop_start = 0
    exception_count = 0
    first_retry_delay = min(exception_delay, exception_delay_max)
    retry_delay = first_retry_delay

    def recovered() -> None:
        """End a run of suppressed exceptions: log it and start over from the first delay."""
        nonlocal exception_count, retry_delay
        if exception_count:
            logger.info(f"{coro_function.__name__}: task recovered")
            exception_count = 0
            retry_delay = first_retry_delay

    if exception_limit is None:
        kwargs["recovered"] = recovered

    while True:
        # Reset the exception count when the limit window has elapsed since the last non-exception loop started.
        if (
            exception_limit is not None
            and last_regular_loop_start + exception_limit_window < time.monotonic()
        ):
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
                if exception_limit is None:
                    if exception_count == 1:
                        logger.error(
                            f"{coro_function.__name__}: task error, retrying until it recovers: {e}"
                        )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, exception_delay_max)
                    continue
                if exception_count >= exception_limit:
                    logger.error(
                        f"{coro_function.__name__}: task exceeded exception limit {exception_limit} within {exception_limit_window}s: {e}"
                    )
                    raise
                logger.error(f"{coro_function.__name__}: task error suppressed: {e}")
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
    exception_limit: int | None = 5,
    exception_limit_window: float = 60.0,
    exception_delay_max: float = 30.0,
    task_context: Context | None = None,
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
            Without a limit (None), the delay doubles after each exception in a row, only the first of them
            is logged, and the coroutine function is passed a `recovered` callable to call once it works again.
        exception_limit_window: The time window in seconds for counting suppressed exceptions.
        exception_delay_max: The longest delay between retries when there is no exception limit.
        task_context: The context to use for the task.
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
        rf_coro = _run_forever(
            coro_function,
            *args,
            suppress_exceptions=suppress_exceptions,
            exception_delay=exception_delay,
            exception_limit=exception_limit,
            exception_limit_window=exception_limit_window,
            exception_delay_max=exception_delay_max,
            **kwargs,
        )
        task_name = f"reflex_ensure_task|{type(owner).__name__}.{task_attribute}={coro_function.__name__}|{time.time()}"
        if task_context is not None:
            # Run the task in the given context (not needed after Python 3.11+ which supports passing context to create_task directly).
            task = task_context.run(asyncio.create_task, rf_coro, name=task_name)
        else:
            task = asyncio.create_task(rf_coro, name=task_name)
        setattr(owner, task_attribute, task)
    return task
