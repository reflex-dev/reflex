"""Miscellaneous functions for the experimental package."""

import asyncio
from typing import Any, Callable


async def run_in_thread(func: Callable) -> Any:
    """Run a function in a separate thread.

    To not block the UI event queue, run_in_thread must be inside inside a rx.event(background=True) decorated method.

    Args:
        func: The non-async function to run.

    Raises:
        ValueError: If the function is an async function.

    Returns:
        Any: The return value of the function.
    """
    if asyncio.coroutines.iscoroutinefunction(func):
        raise ValueError("func must be a non-async function")
    return await asyncio.get_event_loop().run_in_executor(None, func)
