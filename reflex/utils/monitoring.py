"""PyLeak integration for monitoring event loop blocking and resource leaks in Reflex applications."""

import contextlib
import functools
import inspect
import threading
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from typing import TypeVar, overload

from reflex.config import get_config

try:
    from pyleak import no_event_loop_blocking, no_task_leaks, no_thread_leaks
    from pyleak.base import LeakAction

    PYLEAK_AVAILABLE = True
except ImportError:
    PYLEAK_AVAILABLE = False
    no_event_loop_blocking = no_task_leaks = no_thread_leaks = None  # pyright: ignore[reportAssignmentType]
    LeakAction = None  # pyright: ignore[reportAssignmentType]


# Thread-local storage to track if monitoring is already active
_thread_local = threading.local()


def is_pyleak_enabled() -> bool:
    """Check if PyLeak monitoring is enabled and available.

    Returns:
        True if PyLeak monitoring is enabled in config and PyLeak is available.
    """
    if not PYLEAK_AVAILABLE:
        return False
    config = get_config()
    return config.enable_pyleak_monitoring


@contextlib.contextmanager
def monitor_sync():
    """Sync context manager for PyLeak monitoring.

    Yields:
        None: Context for monitoring sync operations.
    """
    if not is_pyleak_enabled():
        yield
        return

    # Check if monitoring is already active in this thread
    if getattr(_thread_local, "monitoring_active", False):
        yield
        return

    config = get_config()
    action = config.pyleak_action or LeakAction.WARN  # pyright: ignore[reportOptionalMemberAccess]

    # Mark monitoring as active
    _thread_local.monitoring_active = True
    try:
        with contextlib.ExitStack() as stack:
            # Thread leak detection has issues with background tasks (no_thread_leaks)
            stack.enter_context(
                no_event_loop_blocking(  # pyright: ignore[reportOptionalCall]
                    action=action,
                    threshold=config.pyleak_blocking_threshold,
                )
            )
            yield
    finally:
        _thread_local.monitoring_active = False


@contextlib.asynccontextmanager
async def monitor_async():
    """Async context manager for PyLeak monitoring.

    Yields:
        None: Context for monitoring async operations.
    """
    if not is_pyleak_enabled():
        yield
        return

    # Check if monitoring is already active in this thread
    if getattr(_thread_local, "monitoring_active", False):
        yield
        return

    config = get_config()
    action = config.pyleak_action or LeakAction.WARN  # pyright: ignore[reportOptionalMemberAccess]

    # Mark monitoring as active
    _thread_local.monitoring_active = True
    try:
        async with contextlib.AsyncExitStack() as stack:
            # Thread leak detection has issues with background tasks (no_thread_leaks)
            # Re-add thread leak later.

            # Block detection for event loops
            stack.enter_context(
                no_event_loop_blocking(  # pyright: ignore[reportOptionalCall]
                    action=action,
                    threshold=config.pyleak_blocking_threshold,
                )
            )
            # Task leak detection has issues with background tasks (no_task_leaks)

            yield
    finally:
        _thread_local.monitoring_active = False


YieldType = TypeVar("YieldType")
SendType = TypeVar("SendType")
ReturnType = TypeVar("ReturnType")


@overload
def monitor_loopblocks(
    func: Callable[..., AsyncGenerator[YieldType, ReturnType]],
) -> Callable[..., AsyncGenerator[YieldType, ReturnType]]: ...


@overload
def monitor_loopblocks(
    func: Callable[..., Generator[YieldType, SendType, ReturnType]],
) -> Callable[..., Generator[YieldType, SendType, ReturnType]]: ...


@overload
def monitor_loopblocks(
    func: Callable[..., Awaitable[ReturnType]],
) -> Callable[..., Awaitable[ReturnType]]: ...


def monitor_loopblocks(func: Callable) -> Callable:
    """Framework decorator using the monitoring module's context manager.

    Args:
        func: The function to be monitored for leaks.

    Returns:
        Decorator function that applies PyLeak monitoring to sync/async functions.
    """
    if inspect.isasyncgenfunction(func):

        @functools.wraps(func)
        async def async_gen_wrapper(*args, **kwargs):
            async with monitor_async():
                async for item in func(*args, **kwargs):
                    yield item

        return async_gen_wrapper

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with monitor_async():
                return await func(*args, **kwargs)

        return async_wrapper

    if inspect.isgeneratorfunction(func):

        @functools.wraps(func)
        def gen_wrapper(*args, **kwargs):
            with monitor_sync():
                yield from func(*args, **kwargs)

        return gen_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        with monitor_sync():
            return func(*args, **kwargs)

    return sync_wrapper  # pyright: ignore[reportReturnType]
