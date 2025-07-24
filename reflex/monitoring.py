"""PyLeak integration for monitoring event loop blocking and resource leaks in Reflex applications."""

import asyncio
import contextlib
import functools
from collections.abc import Callable

from reflex.config import get_config

try:
    from pyleak import no_event_loop_blocking, no_task_leaks, no_thread_leaks
    from pyleak.base import LeakAction

    PYLEAK_AVAILABLE = True
except ImportError:
    PYLEAK_AVAILABLE = False
    no_event_loop_blocking = no_task_leaks = no_thread_leaks = None  # pyright: ignore[reportAssignmentType]
    LeakAction = None  # pyright: ignore[reportAssignmentType]


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

    config = get_config()
    action = config.pyleak_action or LeakAction.WARN  # pyright: ignore[reportOptionalMemberAccess]

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            no_thread_leaks(  # pyright: ignore[reportOptionalCall]
                action=action,
                grace_period=config.pyleak_thread_grace_period,
            )
        )
        stack.enter_context(
            no_event_loop_blocking(  # pyright: ignore[reportOptionalCall]
                action=action,
                threshold=config.pyleak_blocking_threshold,
            )
        )
        yield


@contextlib.asynccontextmanager
async def monitor_async():
    """Async context manager for PyLeak monitoring.

    Yields:
        None: Context for monitoring async operations.
    """
    if not is_pyleak_enabled():
        yield
        return

    config = get_config()
    action = config.pyleak_action or LeakAction.WARN  # pyright: ignore[reportOptionalMemberAccess]

    async with contextlib.AsyncExitStack() as stack:
        stack.enter_context(
            no_thread_leaks(  # pyright: ignore[reportOptionalCall]
                action=action,
                grace_period=config.pyleak_thread_grace_period,
            )
        )
        stack.enter_context(
            no_event_loop_blocking(  # pyright: ignore[reportOptionalCall]
                action=action,
                threshold=config.pyleak_blocking_threshold,
            )
        )
        await stack.enter_async_context(no_task_leaks(action=action))  # pyright: ignore[reportOptionalCall]
        yield


def monitor_leaks():
    """Framework decorator using the monitoring module's context manager.

    Returns:
        Decorator function that applies PyLeak monitoring to sync/async functions.
    """

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with monitor_async():
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with monitor_sync():
                return func(*args, **kwargs)

        return sync_wrapper  # pyright: ignore[reportReturnType]

    return decorator
