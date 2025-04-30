"""Miscellaneous functions for the experimental package."""

import asyncio
from collections.abc import Callable
from typing import Any


async def run_in_thread(func: Callable, *, timeout: float | None = None) -> Any:
    """Run a function in a separate thread.

    To not block the UI event queue, run_in_thread must be inside inside a rx.event(background=True) decorated method.

    Args:
        func: The non-async function to run.
        timeout: Maximum number of seconds to wait for the function to complete.
                If None (default), wait indefinitely.

    Raises:
        ValueError: If the function is an async function.
        asyncio.TimeoutError: If the function execution exceeds the specified timeout.

    Returns:
        Any: The return value of the function.
    """
    if asyncio.coroutines.iscoroutinefunction(func):
        raise ValueError("func must be a non-async function")

    task = asyncio.get_event_loop().run_in_executor(None, func)
    if timeout is not None:
        return await asyncio.wait_for(task, timeout=timeout)
    return await task
