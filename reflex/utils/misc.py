"""Miscellaneous functions for the experimental package."""

import asyncio
import contextlib
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


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
        msg = "func must be a non-async function"
        raise ValueError(msg)
    return await asyncio.get_event_loop().run_in_executor(None, func)


# Global lock for thread-safe sys.path manipulation
_sys_path_lock = threading.RLock()


@contextlib.contextmanager
def with_cwd_in_syspath():
    """Temporarily add current working directory to sys.path in a thread-safe manner.

    This context manager temporarily prepends the current working directory to sys.path,
    ensuring that modules in the current directory can be imported. The original sys.path
    is restored when exiting the context.

    Yields:
        None
    """
    with _sys_path_lock:
        orig_sys_path = sys.path.copy()
        sys.path.insert(0, str(Path.cwd()))
        try:
            yield
        finally:
            sys.path[:] = orig_sys_path
