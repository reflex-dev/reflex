"""Miscellaneous utility functions."""

import asyncio
import contextlib
import inspect
import sys
import threading
from collections.abc import Callable, Sequence
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

    Returns:
        Any: The return value of the function.

    Raises:
        ValueError: If the function is an async function.
    """
    if inspect.iscoroutinefunction(func):
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


def preload_color_theme():
    """Create a script component that preloads the color theme to prevent FOUC.

    This script runs immediately in the document head before React hydration,
    reading the saved theme from localStorage and applying the correct CSS classes
    to prevent flash of unstyled content.

    Returns:
        Script: A script component to add to App.head_components
    """
    from reflex_components_core.el.elements.scripts import Script

    # Create direct inline script content (like next-themes dangerouslySetInnerHTML)
    script_content = """
// Only run in browser environment, not during SSR
if (typeof document !== 'undefined') {
    try {
        const theme = localStorage.getItem("theme") || "system";
        const systemPreference = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        const resolvedTheme = theme === "system" ? systemPreference : theme;

        // Apply theme immediately - blocks until complete
        // Use classList to avoid overwriting other classes
        document.documentElement.classList.remove("light", "dark");
        document.documentElement.classList.add(resolvedTheme);
        document.documentElement.style.colorScheme = resolvedTheme;

    } catch (e) {
        // Fallback to system preference on any error (resolve "system" to actual theme)
        const fallbackTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        document.documentElement.classList.remove("light", "dark");
        document.documentElement.classList.add(fallbackTheme);
        document.documentElement.style.colorScheme = fallbackTheme;
    }
}
"""

    return Script.create(script_content)


def google_font(
    family: str,
    *,
    weights: Sequence[int] = (400,),
    italic: bool = False,
    display: str = "swap",
):
    """Create the components that load a Google Font from the document head.

    Adding these to ``head_components`` (instead of ``rx.App(stylesheets=...)``, which chains
    fonts behind an ``@import`` in the global stylesheet) lets the browser discover the font
    during the initial HTML parse and fetch it in parallel, with ``display=swap`` so text paints
    immediately using a fallback face::

        app = rx.App(head_components=rx.google_font("Inter", weights=[400, 700]))

    Args:
        family: The font family name, e.g. ``"Open Sans"``.
        weights: The font weights to request.
        italic: Whether to also request italic styles for each weight.
        display: The CSS ``font-display`` strategy.

    Returns:
        The preconnect and stylesheet components to add to ``head_components``.
    """
    from reflex_components_core.el.elements.metadata import Link

    if not weights:
        msg = "weights must not be empty"
        raise ValueError(msg)
    family_param = family.replace(" ", "+")
    sorted_weights = sorted(weights)
    if italic:
        axis = "ital,wght@" + ";".join(
            f"{style},{weight}" for style in (0, 1) for weight in sorted_weights
        )
    else:
        axis = "wght@" + ";".join(str(weight) for weight in sorted_weights)
    href = f"https://fonts.googleapis.com/css2?family={family_param}:{axis}&display={display}"
    return [
        Link.create(rel="preconnect", href="https://fonts.googleapis.com"),
        Link.create(
            rel="preconnect", href="https://fonts.gstatic.com", cross_origin="anonymous"
        ),
        Link.create(rel="stylesheet", href=href),
    ]
