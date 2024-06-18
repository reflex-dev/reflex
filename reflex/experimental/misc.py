"""Miscellaneous functions for the experimental package."""

import asyncio
from typing import Any


async def run_in_thread(func) -> Any:
    """Run a function in a separate thread.

    To not block the UI event queue, run_in_thread must be inside inside a rx.background() decorated method.

    Args:
        func (callable): The non-async function to run.

    Returns:
        Any: The return value of the function.
    """
    assert not asyncio.coroutines.iscoroutinefunction(
        func
    ), "func must be a non-async function"
    return await asyncio.get_event_loop().run_in_executor(None, func)
