"""Miscellaneous functions for the experimental package."""

import asyncio
import contextlib
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


def get_module_path(module_name: str) -> Path | None:
    """Check if a module exists and return its path.

    This function searches for a module by navigating through the module hierarchy
    in each path of sys.path, checking for both .py files and packages with __init__.py.

    Args:
        module_name: The name of the module to search for (e.g., "package.submodule").

    Returns:
        The path to the module file if found, None otherwise.
    """
    parts = module_name.split(".")

    # Check each path in sys.path
    for path in sys.path:
        current_path = Path(path)

        # Navigate through the module hierarchy
        for i, part in enumerate(parts):
            potential_file = current_path / (part + ".py")
            potential_dir = current_path / part

            if potential_file.is_file():
                # We encountered a file, but we can't continue deeper
                if i == len(parts) - 1:
                    return potential_file
                return None  # Can't continue deeper
            if potential_dir.is_dir():
                # It's a package, so we can continue deeper
                current_path = potential_dir
            else:
                break  # Path doesn't exist, break out of the loop
        else:
            return current_path / "__init__.py"  # Made it through all parts

    return None


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
